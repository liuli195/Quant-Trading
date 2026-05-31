"""Governance audit rules."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import yaml

from scripts.research.registry import default_tool_registry
from scripts.research.governance.skill_ownership import validate_ownerships
from scripts.research.governance.schemas import AuditFinding, AuditReport
from scripts.research.platform.datasets import DatasetRegistry
from scripts.research.platform.docs_index import DocsIndexer, render_adr_index
from scripts.research.platform.engine import DEFAULT_TEMPLATES
from scripts.research.platform.engine import validate_project_config
from scripts.research.platform.strategy_variants import (
    StrategyManifestReader,
    VariantError,
)
from scripts.research.platform.workflows import (
    WorkflowTemplateError,
    load_workflow_templates,
)
from scripts.tools.path_tools.aliases import (
    validate_config_file as validate_path_alias_config,
)


REQUIRED_RULE_DOCS = (
    "docs/rules/index.md",
    "docs/rules/pr-workflow.md",
    "docs/rules/governance.md",
    "docs/rules/skills.md",
    "docs/rules/review-guidelines.md",
    "docs/rules/commands.md",
    "docs/rules/environments.md",
    "docs/rules/research-workflow.md",
    "docs/rules/collaboration.md",
    "docs/rules/code-style.md",
    "docs/rules/docs-and-pathref.md",
)
REQUIRED_CODEOWNER_PATTERNS = (
    "CLAUDE.md",
    "AGENTS.md",
    "docs/agents/**",
    "docs/rules/**",
    "docs/adr/**",
    ".codex/skills/**",
    ".claude/skills/**",
    ".github/workflows/**",
    ".githooks/**",
    "scripts/research/governance/**",
    "scripts/research/registry/**",
    "path_aliases.json",
    "strategies/**",
)
LEGACY_FAST_GATE_SURFACES = (
    "Makefile",
    ".githooks/pre-commit",
    ".githooks/pre-push",
    ".github/workflows/research-governance.yml",
)
_OLD_PR_TEMPLATE_TOKENS = (
    "改动目标",
    "影响范围",
    "规则同步",
    "已运行检查",
    "子 agent 交叉评审",
    "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
    "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
    "reviewers:",
    "任务分发说明",
    "high/unknown PR label",
    "官方 Codex Review 跳过授权",
    "本地 AI review 模式",
    "本地安全 review",
    "codex-security",
    "security-guidance",
    "不完全 Review 模式授权",
    "Codex Code Review 结论",
    "Codex",
    "pr-flow:start",
    ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full",
    "waiver",
    "证据",
)
_SIMPLIFIED_PR_TEMPLATE_TOKENS = (
    "改动目标",
    "影响范围",
    "pr-flow:start",
    "pr-flow:end",
    "make pr-ready",
    "人工补充",
    "额外证据链接",
    "waiver",
)
PR_TEMPLATE_TOKENS = _SIMPLIFIED_PR_TEMPLATE_TOKENS
REQUIRED_REVIEW_GUIDELINES_TOKENS = (
    "Codex Code Review",
    "@codex review",
    "AGENTS.md",
    "docs/rules/review-guidelines.md",
    "P0/P1",
    ".\\.venv\\Scripts\\python.exe -m scripts.research.governance verify full",
    "Codex Review Monitor",
    "至少两个独立 reviewer",
    "子 agent 交叉评审",
    "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
    "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
    "reviewers:",
    "review_mode=complete",
    "review_mode=partial",
    "security_review",
    "本地安全 review",
    "codex-security",
    "security-guidance",
    "官方 Codex Review 跳过授权",
    "Codex Code Review 结论",
    "结论: 通过",
    "阻断问题: 无",
)
REQUIRED_COMMAND_RULE_TOKENS = (
    "scripts.research.cli",
    "scripts.research.datasets",
    "scripts.research.variants",
    "scripts.research.governance",
    "scripts.research.registry",
    "scripts.tools.path_tools.refactor",
    ".\\.githooks\\setup-python.ps1",
    ".githooks/setup-python.sh",
    ".\\.venv\\Scripts\\python.exe",
    ".venv/bin/python",
    "Python 命令默认必须提权使用项目 `.venv`，不改用系统 Python",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "gh pr checks",
    "`gh` CLI 默认提权执行",
)
REQUIRED_AGENT_ENTRY_TOKENS = (
    "docs/rules/review-guidelines.md",
    "简体中文，简洁直白",
    "聚宽云端",
    "默认必须提权使用项目 `.venv`，不改用系统 Python",
    "docs/rules/commands.md",
    "`gh` CLI 默认提权执行",
    "进入主干须通过 PR",
    "直写主干",
    "禁止把功能分支本地合入",
    "docs/rules/pr-workflow.md",
    "分支名使用 ASCII",
    "优先派发子 agent",
    "主会话负责编排",
    "可点击链接",
    "pathref",
    "任务后清理临时产物",
)
FORBIDDEN_AGENT_DETAIL_TOKENS = (
    "scripts.research.cli",
    "scripts.research.datasets",
    "scripts.research.variants",
    "git fetch origin main",
    "git merge --ff-only origin/main",
    "git branch -d <branch>",
    "git push origin --delete <branch>",
    ".\\.venv\\Scripts\\python.exe",
    ".venv/bin/python",
)
FORBIDDEN_CLAUDE_TOKENS = (
    "遇到沙箱/权限阻断",
    "Codex Code Review",
    "自审",
    "docs/rules/review-guidelines.md",
)
WAIVER_REQUIRED_FIELDS = (
    "id",
    "rule_id",
    "path",
    "reason",
    "owner",
    "approved_by",
    "expires_at",
    "migration_plan",
)


def _workflow_event_types_include(
    text: str, event: str, required_types: Sequence[str]
) -> bool:
    match = re.search(rf"{re.escape(event)}:\s*\n\s*types:\s*\[([^\]]*)\]", text)
    if not match:
        return False
    declared = match.group(1)
    return all(required_type in declared for required_type in required_types)


def run_audit(
    repo_root: str | Path = ".",
    *,
    check_cli_help: bool = True,
    check_pathrefs: bool = True,
) -> AuditReport:
    """Run the governance audit and return structured findings."""

    root = Path(repo_root).resolve()
    findings: list[AuditFinding] = []
    findings.extend(_audit_tool_registry(root))
    findings.extend(_audit_layer_docs(root))
    findings.extend(_audit_claude_and_skills(root))
    findings.extend(
        AuditFinding("skill_ownership", "error", message)
        for message in validate_ownerships(root)
    )
    findings.extend(_audit_review_guidelines(root))
    findings.extend(_audit_governance_gate(root))
    findings.extend(_audit_local_review_entrypoints(root))
    findings.extend(_audit_legacy_fast_gate_references(root))
    findings.extend(_audit_rule_sources(root))
    findings.extend(_audit_codeowners(root))
    findings.extend(_audit_pr_template(root))
    findings.extend(_audit_waivers(root))
    findings.extend(_audit_path_aliases(root))
    findings.extend(_audit_strategy_manifests(root))
    findings.extend(_audit_project_configs(root))
    findings.extend(_audit_gitignore_patterns(root))
    findings.extend(_audit_catalogs(root))
    findings.extend(_audit_workflow_templates(root))
    if check_cli_help:
        findings.extend(_audit_cli_help(root))
    if check_pathrefs:
        findings.extend(_audit_pathrefs(root))
    return AuditReport(
        ok=not any(item.severity == "error" for item in findings),
        findings=tuple(findings),
    )


def _audit_tool_registry(root: Path) -> list[AuditFinding]:
    errors = default_tool_registry().validate(root)
    findings = [AuditFinding("tool_registry", "error", message) for message in errors]
    findings.extend(_audit_unregistered_cli_modules(root))
    return findings


def _audit_layer_docs(root: Path) -> list[AuditFinding]:
    registry = default_tool_registry()
    layer_root = root / "scripts" / "research" / "layers"
    findings: list[AuditFinding] = []
    for filename, expected in registry.render_layer_docs().items():
        path = layer_root / filename
        rel_path = path.relative_to(root).as_posix()
        if not path.is_file():
            findings.append(
                AuditFinding("layer_docs", "error", f"layer doc missing: {rel_path}")
            )
            continue
        actual = path.read_text(encoding="utf-8", errors="ignore")
        if actual != expected:
            findings.append(
                AuditFinding(
                    "layer_docs",
                    "error",
                    f"layer doc stale: {rel_path}; regenerate with scripts.research.registry.tool_registry write-layers",
                )
            )
    return findings


def _audit_claude_and_skills(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append(AuditFinding("agent_entry_sync", "error", "AGENTS.md missing"))
    else:
        text = agents.read_text(encoding="utf-8", errors="ignore")
        for token in REQUIRED_AGENT_ENTRY_TOKENS:
            if token not in text:
                findings.append(
                    AuditFinding(
                        "agent_entry_sync", "error", f"AGENTS.md missing {token}"
                    )
                )
        for token in FORBIDDEN_AGENT_DETAIL_TOKENS:
            if token in text:
                findings.append(
                    AuditFinding(
                        "agent_entry_sync",
                        "error",
                        f"AGENTS.md should not duplicate detailed rules: {token}",
                    )
                )

    claude = root / "CLAUDE.md"
    if not claude.is_file():
        findings.append(AuditFinding("claude_sync", "error", "CLAUDE.md missing"))
    else:
        text = claude.read_text(encoding="utf-8", errors="ignore")
        for token in ("AGENTS.md",):
            if token not in text:
                findings.append(
                    AuditFinding("claude_sync", "error", f"CLAUDE.md missing {token}")
                )
        for token in FORBIDDEN_CLAUDE_TOKENS:
            if token in text:
                findings.append(
                    AuditFinding(
                        "claude_sync",
                        "error",
                        f"CLAUDE.md contains Codex-only or standard review rules: {token}",
                    )
                )

    commands = root / "docs" / "rules" / "commands.md"
    if not commands.is_file():
        findings.append(
            AuditFinding("command_rules", "error", "docs/rules/commands.md missing")
        )
    else:
        text = commands.read_text(encoding="utf-8", errors="ignore")
        for token in REQUIRED_COMMAND_RULE_TOKENS:
            if token not in text:
                findings.append(
                    AuditFinding(
                        "command_rules", "error", f"commands.md missing {token}"
                    )
                )

    local_env = root / "docs" / "guides" / "local-python-env.md"
    if not local_env.is_file():
        findings.append(
            AuditFinding(
                "command_rules", "error", "docs/guides/local-python-env.md missing"
            )
        )
    else:
        text = local_env.read_text(encoding="utf-8", errors="ignore")
        setup_doc_tokens = (
            (
                "git worktree add",
                "local-python-env.md missing worktree setup example",
            ),
            (
                ".\\.githooks\\setup-python.ps1",
                "local-python-env.md missing Windows setup script",
            ),
            (
                ".githooks/setup-python.sh",
                "local-python-env.md missing POSIX setup script",
            ),
            (
                "Codex Cloud Environment setup script",
                "local-python-env.md missing Codex Cloud setup example",
            ),
            (
                "Codex App Local Environment",
                "local-python-env.md missing Codex App setup example",
            ),
            (
                "requirements-dev.txt",
                "local-python-env.md missing requirements-dev.txt",
            ),
        )
        for token, message in setup_doc_tokens:
            if token not in text:
                findings.append(AuditFinding("command_rules", "error", message))

    return findings


def _audit_review_guidelines(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    path = root / "docs" / "rules" / "review-guidelines.md"
    if not path.is_file():
        return [
            AuditFinding(
                "review_guidelines", "error", "docs/rules/review-guidelines.md missing"
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings.extend(
        AuditFinding(
            "review_guidelines", "error", f"review-guidelines.md missing {token}"
        )
        for token in REQUIRED_REVIEW_GUIDELINES_TOKENS
        if token not in text
    )

    agents = root / "AGENTS.md"
    if agents.is_file():
        agents_text = agents.read_text(encoding="utf-8", errors="ignore")
        if not any(
            token in agents_text
            for token in (
                "## Review guidelines",
                "## Review 指南",
                "**review 指南**",
            )
        ):
            findings.append(
                AuditFinding(
                    "review_guidelines",
                    "error",
                    "AGENTS.md missing Review guidelines heading",
                )
            )
        if "docs/rules/review-guidelines.md" not in agents_text:
            findings.append(
                AuditFinding(
                    "review_guidelines",
                    "error",
                    "AGENTS.md missing docs/rules/review-guidelines.md",
                )
            )
    return findings


def _audit_governance_gate(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    hook_python_sh = root / ".githooks" / "run-python.sh"
    if not hook_python_sh.is_file():
        findings.append(
            AuditFinding("governance_gate", "error", ".githooks/run-python.sh missing")
        )
    else:
        text = hook_python_sh.read_text(encoding="utf-8", errors="ignore")
        for token in (".venv/bin/python", ".venv/Scripts/python.exe", '"$@"'):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate", "error", f"run-python.sh missing {token}"
                    )
                )
        if "uname" not in text or not any(
            token in text for token in ("MINGW", "MSYS", "CYGWIN")
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "run-python.sh must choose venv by platform",
                )
            )
        if re.search(r'PYTHON=["\']?python["\']?', text) or re.search(
            r"exec\s+python(\s|$)", text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "run-python.sh must not fall back to system Python",
                )
            )

    hook_python = root / ".githooks" / "run-python.ps1"
    if not hook_python.is_file():
        findings.append(
            AuditFinding("governance_gate", "error", ".githooks/run-python.ps1 missing")
        )
    else:
        text = hook_python.read_text(encoding="utf-8", errors="ignore")
        if ".venv\\Scripts\\python.exe" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "run-python.ps1 missing .venv\\Scripts\\python.exe",
                )
            )
        if re.search(r"\$Python\s*=\s*['\"]python['\"]", text) or re.search(
            r"&\s+python(\s|$)", text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "run-python.ps1 must not fall back to system Python",
                )
            )

    setup_python = root / ".githooks" / "setup-python.ps1"
    if not setup_python.is_file():
        findings.append(
            AuditFinding(
                "governance_gate", "error", ".githooks/setup-python.ps1 missing"
            )
        )
    else:
        text = setup_python.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "requirements-dev.txt",
            "git config core.hooksPath .githooks",
            "PYTHONUTF8",
            "PYTHONIOENCODING",
            "3.12",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"setup-python.ps1 missing {token}",
                    )
                )

    setup_sh = root / ".githooks" / "setup-python.sh"
    if not setup_sh.is_file():
        findings.append(
            AuditFinding(
                "governance_gate", "error", ".githooks/setup-python.sh missing"
            )
        )
    else:
        text = setup_sh.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "requirements-dev.txt",
            "git config core.hooksPath .githooks",
            "PYTHONUTF8",
            "PYTHONIOENCODING",
            "python3.12",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"setup-python.sh missing {token}",
                    )
                )

    hook = root / ".githooks" / "pre-commit"
    if not hook.is_file():
        findings.append(
            AuditFinding("governance_gate", "error", ".githooks/pre-commit missing")
        )
    else:
        text = hook.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance verify fast --staged" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-commit hook must use verify fast --staged",
                )
            )
        if "powershell.exe" in text or ".githooks/run-python.sh" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate", "error", "pre-commit hook must use run-python.sh"
                )
            )
        if "scripts.research.governance gate --fast" in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-commit hook must use verify fast --staged",
                )
            )

    pre_push = root / ".githooks" / "pre-push"
    if not pre_push.is_file():
        findings.append(
            AuditFinding("governance_gate", "error", ".githooks/pre-push missing")
        )
    else:
        text = pre_push.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance.branch_protection pre-push" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-push hook missing branch protection gate",
                )
            )
        if "scripts.research.governance verify full" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate", "error", "pre-push hook missing full governance verification"
                )
            )
        if "scripts.research.governance gate" in text or (
            "scripts.research.governance verify fast" in text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-push hook must use verify full",
                )
            )
        if "git lfs pre-push" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate", "error", "pre-push hook missing Git LFS handoff"
                )
            )
        if "powershell.exe" in text or ".githooks/run-python.sh" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate", "error", "pre-push hook must use run-python.sh"
                )
            )

    reference_transaction = root / ".githooks" / "reference-transaction"
    if not reference_transaction.is_file():
        findings.append(
            AuditFinding(
                "governance_gate", "error", ".githooks/reference-transaction missing"
            )
        )
    else:
        text = reference_transaction.read_text(encoding="utf-8", errors="ignore")
        if (
            "scripts.research.governance.branch_protection reference-transaction"
            not in text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "reference-transaction hook missing local branch protection gate",
                )
            )
        if "prepared" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "reference-transaction hook must validate the prepared phase",
                )
            )
        if "powershell.exe" in text or ".githooks/run-python.sh" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "reference-transaction hook must use run-python.sh",
                )
            )
        pre_setup_tokens = (
            ".venv/bin/python",
            ".venv/Scripts/python.exe",
            "refs/heads/main",
            "refs/heads/master",
            "Project virtualenv Python not found",
        )
        if not all(token in text for token in pre_setup_tokens):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "reference-transaction hook missing pre-setup worktree guard",
                )
            )

    workflow = root / ".github" / "workflows" / "research-governance.yml"
    if not workflow.is_file():
        findings.append(
            AuditFinding(
                "governance_gate",
                "error",
                ".github/workflows/research-governance.yml missing",
            )
        )
    else:
        text = workflow.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance verify full" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate", "error", "CI workflow missing verify full entrypoint"
                )
            )
        if "scripts.research.governance verify fast" in text:
            findings.append(
                AuditFinding(
                    "governance_gate", "error", "CI workflow must not use verify fast"
                )
            )
        if "scripts.research.governance gate" in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow must use verify full as the single governance entrypoint",
                )
            )
        if "scripts.research.governance.pr_review_evidence" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow missing PR review evidence gate",
                )
            )
        if re.search(r"pr-review-evidence:\s*\n\s*if:", text):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "required PR review evidence job must not use job-level if",
                )
            )
        for token in (
            "python -m ruff check",
            "python -m bandit",
            "python -m mypy",
            "python -m pip_audit",
            "python -m pytest",
        ):
            if token in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"CI workflow must use verify full instead of split command {token}",
                    )
                )
        if "schedule:" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow missing scheduled drift audit",
                )
            )
        if not re.search(
            r"pull_request_review_comment:\s*\n\s*types:\s*\[[^\]]*deleted", text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR review evidence workflow must listen to deleted inline review comments",
                )
            )
        if not _workflow_event_types_include(
            text, "pull_request_review", ("submitted", "edited", "dismissed")
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR review evidence workflow must listen to Codex review submitted, edited, and dismissed events",
                )
            )
        if not _workflow_event_types_include(
            text,
            "pull_request",
            (
                "opened",
                "synchronize",
                "reopened",
                "edited",
                "ready_for_review",
                "labeled",
                "unlabeled",
            ),
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR review evidence workflow must listen to pull_request labeled and unlabeled events",
                )
            )

    monitor_workflow = root / ".github" / "workflows" / "codex-review-monitor.yml"
    if not monitor_workflow.is_file():
        findings.append(
            AuditFinding(
                "codex_review_monitor",
                "error",
                ".github/workflows/codex-review-monitor.yml missing",
            )
        )
    else:
        text = monitor_workflow.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "pull_request",
            "synchronize",
            "issue_comment",
            "pull_request_review",
            "pull_request_review_comment",
            "statuses: write",
            "scripts.research.governance.codex_review_monitor",
            "--sync-comment",
            "--sync-status",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "codex_review_monitor",
                        "error",
                        f"monitor workflow missing {token}",
                    )
                )
        if not re.search(
            r"pull_request_review_comment:\s*\n\s*types:\s*\[[^\]]*deleted", text
        ):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must listen to deleted inline review comments",
                )
            )
        if not _workflow_event_types_include(
            text, "pull_request_review", ("submitted", "edited", "dismissed")
        ):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must listen to Codex review submitted, edited, and dismissed events",
                )
            )
        if not _workflow_event_types_include(
            text, "pull_request", ("labeled", "unlabeled")
        ):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must listen to pull_request labeled and unlabeled events",
                )
            )

    pr_workflow = root / "docs" / "rules" / "pr-workflow.md"
    if pr_workflow.is_file():
        text = pr_workflow.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "所有进入主干的改动必须通过 PR",
            "直写主干",
            "ALLOW_DIRECT_MAIN_WRITE",
            "DIRECT_MAIN_WRITE_REASON",
            "禁止把功能分支本地合入",
            "git fetch origin main",
            "git merge --ff-only origin/main",
            "git branch -d <branch>",
            "git push origin --delete <branch>",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate", "error", f"pr-workflow.md missing {token}"
                    )
                )

    collaboration = root / "docs" / "rules" / "collaboration.md"
    if collaboration.is_file():
        text = collaboration.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "多个 AI agent",
            "分支名使用 ASCII",
            "本地共享工作区",
            "只读分析不要求创建分支",
            "有可用子 agent 能力",
            "无能力时记录原因",
            "不采用任务登记",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"collaboration.md missing {token}",
                    )
                )

    governance = root / "docs" / "rules" / "governance.md"
    if governance.is_file():
        text = governance.read_text(encoding="utf-8", errors="ignore")
        for token in (
            ".githooks/reference-transaction",
            "ALLOW_MAIN_REF_UPDATE",
            "MAIN_REF_UPDATE_REASON",
            "ALLOW_DIRECT_MAIN_WRITE",
            "DIRECT_MAIN_WRITE_REASON",
            "Codex Review Monitor",
            "review_mode=complete",
            "security_review",
            "codex-security",
            "security-guidance",
            "官方 Codex Review 跳过授权",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate", "error", f"governance.md missing {token}"
                    )
                )
    return findings


def _audit_local_review_entrypoints(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    makefile = root / "Makefile"
    if not makefile.is_file():
        return [AuditFinding("local_review", "error", "Makefile missing")]
    make_text = makefile.read_text(encoding="utf-8", errors="ignore")
    for token in (
        "pre-pr",
        "verify-fast",
        "verify-full",
        "ai-review",
        "risk-check",
        "pr-ready",
        "scripts.research.governance verify fast --staged",
        "scripts.research.governance verify full",
        "scripts.research.governance.ai_review_gate",
        "scripts.research.governance.pr_flow",
    ):
        if token not in make_text:
            findings.append(
                AuditFinding("local_review", "error", f"Makefile missing {token}")
            )
    if "powershell.exe" in make_text or "run-python" in make_text:
        findings.append(
            AuditFinding(
                "local_review",
                "error",
                "Makefile must use direct project .venv Python",
            )
        )
    for token in (".venv/Scripts/python.exe", ".venv/bin/python"):
        if token not in make_text:
            findings.append(
                AuditFinding("local_review", "error", f"Makefile missing {token}")
            )

    pre_commit = root / ".pre-commit-config.yaml"
    if not pre_commit.is_file():
        findings.append(
            AuditFinding("local_review", "error", ".pre-commit-config.yaml missing")
        )
    else:
        text = pre_commit.read_text(encoding="utf-8", errors="ignore")
        for token in ("ruff-pre-commit", "bandit", "gitleaks"):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "local_review", "error", f"pre-commit config missing {token}"
                    )
                )

    requirements_dev = root / "requirements-dev.txt"
    if not requirements_dev.is_file():
        findings.append(
            AuditFinding("local_review", "error", "requirements-dev.txt missing")
        )
    else:
        text = requirements_dev.read_text(encoding="utf-8", errors="ignore")
        for token in ("pre-commit", "ruff", "bandit", "mypy", "pip-audit"):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "local_review", "error", f"requirements-dev.txt missing {token}"
                    )
                )

    hook = root / ".githooks" / "pre-commit"
    if hook.is_file():
        text = hook.read_text(encoding="utf-8", errors="ignore")
        if "pre-commit run" not in text:
            findings.append(
                AuditFinding(
                    "local_review", "error", "pre-commit hook missing pre-commit run"
                )
            )

    return findings


def _audit_legacy_fast_gate_references(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    candidates = [root / rel_path for rel_path in LEGACY_FAST_GATE_SURFACES]
    docs_root = root / "docs"
    if docs_root.is_dir():
        candidates.extend(sorted(docs_root.rglob("*.md")))

    seen: set[Path] = set()
    for path in candidates:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "gate --fast" not in text:
            continue
        rel = path.relative_to(root).as_posix()
        findings.append(
            AuditFinding(
                "legacy_fast_gate",
                "error",
                f"{rel} references removed gate --fast entrypoint",
            )
        )
    return findings


def _audit_rule_sources(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for rel_path in REQUIRED_RULE_DOCS:
        if not (root / rel_path).is_file():
            findings.append(
                AuditFinding("rule_source", "error", f"rule doc missing: {rel_path}")
            )

    adr_root = root / "docs" / "adr"
    if not adr_root.is_dir():
        findings.append(AuditFinding("adr", "error", "docs/adr missing"))
    else:
        adr_index = adr_root / "index.md"
        if not adr_index.is_file():
            findings.append(AuditFinding("adr", "error", "docs/adr/index.md missing"))
        elif adr_index.read_text(encoding="utf-8", errors="ignore") != render_adr_index(root):
            findings.append(
                AuditFinding(
                    "adr",
                    "error",
                    "docs/adr/index.md stale; regenerate with scripts.research.docs index",
                )
            )
        adr_files = sorted(
            path for path in adr_root.glob("*.md") if re.match(r"^\d{4}-", path.name)
        )
        if not adr_files:
            findings.append(
                AuditFinding("adr", "error", "docs/adr has no numbered ADR files")
            )
        else:
            numbers = [int(path.name[:4]) for path in adr_files]
            expected = list(range(1, max(numbers) + 1))
            if numbers != expected:
                findings.append(
                    AuditFinding(
                        "adr",
                        "error",
                        f"ADR numbers must be continuous from 0001: found {numbers}",
                    )
                )

    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append(AuditFinding("agent_rule_source", "error", "AGENTS.md missing"))
    else:
        text = agents.read_text(encoding="utf-8", errors="ignore")
        for token in ("AGENTS.md", "通用入口"):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "agent_rule_source", "error", f"AGENTS.md missing {token}"
                    )
                )

    governance_readme = root / "scripts" / "research" / "governance" / "README.md"
    if governance_readme.is_file():
        text = governance_readme.read_text(encoding="utf-8", errors="ignore")
        for token in ("docs/rules/index.md", "docs/adr/index.md", "Codex Review Monitor"):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_docs", "error", f"governance README missing {token}"
                    )
                )
    return findings


def _audit_codeowners(root: Path) -> list[AuditFinding]:
    path = root / "CODEOWNERS"
    if not path.is_file():
        return [AuditFinding("codeowners", "error", "CODEOWNERS missing")]

    findings: list[AuditFinding] = []
    patterns: set[str] = set()
    for lineno, line in enumerate(
        path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1
    ):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            findings.append(
                AuditFinding(
                    "codeowners", "error", f"CODEOWNERS line {lineno} missing owner"
                )
            )
            continue
        patterns.add(_normalize_codeowner_pattern(parts[0]))

    for pattern in REQUIRED_CODEOWNER_PATTERNS:
        if _normalize_codeowner_pattern(pattern) not in patterns:
            findings.append(
                AuditFinding("codeowners", "error", f"CODEOWNERS missing {pattern}")
            )
    return findings


def _audit_pr_template(root: Path) -> list[AuditFinding]:
    path = root / ".github" / "pull_request_template.md"
    if not path.is_file():
        return [
            AuditFinding(
                "pr_template", "error", ".github/pull_request_template.md missing"
            )
        ]
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [
        AuditFinding("pr_template", "error", f"PR template missing {token}")
        for token in PR_TEMPLATE_TOKENS
        if token not in text
    ]


def _audit_waivers(root: Path) -> list[AuditFinding]:
    path = root / "docs" / "exceptions" / "active-waivers.yaml"
    if not path.is_file():
        return [
            AuditFinding(
                "waiver", "error", "docs/exceptions/active-waivers.yaml missing"
            )
        ]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [AuditFinding("waiver", "error", f"invalid waiver YAML: {exc}")]
    if not isinstance(payload, dict):
        return [AuditFinding("waiver", "error", "waiver registry must be a mapping")]

    findings: list[AuditFinding] = []
    if payload.get("schema_version") != 1:
        findings.append(
            AuditFinding("waiver", "error", "waiver registry schema_version must be 1")
        )
    waivers = payload.get("waivers", [])
    if not isinstance(waivers, list):
        findings.append(AuditFinding("waiver", "error", "waivers must be a list"))
        return findings

    today = date.today()
    for index, waiver in enumerate(waivers, start=1):
        if not isinstance(waiver, dict):
            findings.append(
                AuditFinding("waiver", "error", f"waiver #{index} must be a mapping")
            )
            continue
        waiver_id = str(waiver.get("id") or f"#{index}")
        for field in WAIVER_REQUIRED_FIELDS:
            if not str(waiver.get(field, "")).strip():
                findings.append(
                    AuditFinding("waiver", "error", f"{waiver_id}: {field} is required")
                )
        expires_at = _parse_date(waiver.get("expires_at"))
        if expires_at is None:
            findings.append(
                AuditFinding(
                    "waiver", "error", f"{waiver_id}: expires_at must be YYYY-MM-DD"
                )
            )
        elif expires_at < today:
            findings.append(
                AuditFinding(
                    "waiver",
                    "error",
                    f"{waiver_id}: waiver expired at {expires_at.isoformat()}",
                )
            )
    return findings


def _audit_catalogs(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    dataset_root = root / "research_datasets"
    catalog_path = dataset_root / "catalog.json"
    if not catalog_path.is_file():
        findings.append(
            AuditFinding(
                "dataset_catalog", "error", "research_datasets/catalog.json missing"
            )
        )
    else:
        for error in DatasetRegistry(dataset_root).validate():
            findings.append(AuditFinding("dataset_catalog", "error", error))

    index_root = root / "docs" / "indexes"
    for name in (
        "docs_catalog.json",
        "reports_catalog.json",
        "datasets_catalog.json",
        "variants_catalog.json",
    ):
        if not (index_root / name).is_file():
            findings.append(
                AuditFinding("report_catalog", "error", f"docs/indexes/{name} missing")
            )
    reports_index = index_root / "reports_catalog.json"
    if reports_index.is_file():
        payload = json.loads(reports_index.read_text(encoding="utf-8"))
        indexed = {row["path"] for row in payload.get("reports", [])}
        actual = {
            record.path
            for record in DocsIndexer(root).scan()
            if record.category != "docs"
        }
        for path in sorted(actual - indexed):
            findings.append(
                AuditFinding(
                    "report_catalog", "error", f"report catalog missing {path}"
                )
            )
        for path in sorted(indexed - actual):
            findings.append(
                AuditFinding("report_catalog", "error", f"report catalog stale {path}")
            )
    return findings


def _audit_path_aliases(root: Path) -> list[AuditFinding]:
    path = root / "path_aliases.json"
    if not path.is_file():
        return [AuditFinding("path_aliases", "error", "path_aliases.json missing")]
    return [
        AuditFinding("path_aliases", "error", message)
        for message in validate_path_alias_config(root)
    ]


def _audit_project_configs(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for path in sorted(root.glob("strategies/*/reports/research/*/project.json")):
        rel = path.relative_to(root).as_posix()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append(
                AuditFinding("project_config", "error", f"{rel}: invalid JSON: {exc}")
            )
            continue
        for error in validate_project_config(payload):
            findings.append(AuditFinding("project_config", "error", f"{rel}: {error}"))
    return findings


def _audit_gitignore_patterns(root: Path) -> list[AuditFinding]:
    path = root / ".gitignore"
    if not path.is_file():
        return []
    broad_patterns = {"data", "data/", "**/data", "**/data/"}
    findings: list[AuditFinding] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8", errors="ignore").splitlines(),
        start=1,
    ):
        pattern = raw_line.split("#", 1)[0].strip()
        if pattern in broad_patterns:
            findings.append(
                AuditFinding(
                    "gitignore",
                    "error",
                    f".gitignore line {line_number} forbids broad data ignore pattern: {pattern}; use /data/ for repo-root data only",
                )
            )
    return findings


def _audit_strategy_manifests(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    reader = StrategyManifestReader(root / "strategies")
    for strategy_root in sorted(
        path for path in (root / "strategies").glob("*") if path.is_dir()
    ):
        if strategy_root.name.startswith(".") or strategy_root.name == "__pycache__":
            continue
        try:
            reader.read(strategy_root)
        except VariantError as exc:
            rel = strategy_root.relative_to(root).as_posix()
            findings.append(AuditFinding("strategy_manifest", "error", f"{rel}: {exc}"))
    return findings


def _audit_workflow_templates(root: Path) -> list[AuditFinding]:
    try:
        templates = load_workflow_templates(
            root / "scripts" / "research" / "workflows" / "templates"
        )
    except WorkflowTemplateError as exc:
        return [AuditFinding("workflow_template", "error", str(exc))]
    expected = set(DEFAULT_TEMPLATES) | {"cloud_confirmation"}
    actual = {template.template for template in templates}
    findings: list[AuditFinding] = []
    for name in sorted(expected - actual):
        findings.append(
            AuditFinding(
                "workflow_template", "error", f"workflow template missing {name}"
            )
        )
    return findings


def _audit_cli_help(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    commands = [
        [sys.executable, "-m", tool.entry_module, "--help"]
        for tool in default_tool_registry().tools
        if tool.kind == "cli"
    ]
    for command in commands:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if result.returncode != 0:
            findings.append(
                AuditFinding(
                    "cli_help",
                    "error",
                    f"{' '.join(command[2:])} --help failed: {result.stderr.strip() or result.stdout.strip()}",
                )
            )
    return findings


def _audit_unregistered_cli_modules(root: Path) -> list[AuditFinding]:
    registered = {
        tool.entry_module
        for tool in default_tool_registry().tools
        if tool.kind == "cli"
    }
    findings: list[AuditFinding] = []
    for module in _discover_cli_modules(root):
        if not _module_is_registered(module, registered):
            findings.append(
                AuditFinding(
                    "tool_registry", "error", f"CLI module not registered: {module}"
                )
            )
    return findings


def _discover_cli_modules(root: Path) -> list[str]:
    modules: list[str] = []
    for package_root in (root / "scripts" / "research", root / "scripts" / "tools"):
        if not package_root.is_dir():
            continue
        for path in sorted(package_root.rglob("*.py")):
            rel_parts = path.relative_to(root).parts
            if any(
                part in {"__pycache__", "tests", "snippets", "utils", "archive"}
                for part in rel_parts
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "argparse.ArgumentParser" not in text or "def main(" not in text:
                continue
            modules.append(".".join(path.with_suffix("").relative_to(root).parts))
    return modules


def _module_is_registered(module: str, registered: set[str]) -> bool:
    if module in registered:
        return True
    if module.endswith(".cli") and module.removesuffix(".cli") in registered:
        return True
    if module.endswith(".__main__") and module.removesuffix(".__main__") in registered:
        return True
    if (
        module.startswith("scripts.research.governance.")
        and "scripts.research.governance" in registered
    ):
        return True
    if (
        module == "scripts.tools.jq_automation.cli"
        and "scripts.tools.jq_automation" in registered
    ):
        return True
    return False


def _normalize_codeowner_pattern(pattern: str) -> str:
    return pattern.strip().lstrip("/")


def _parse_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _audit_pathrefs(root: Path) -> list[AuditFinding]:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.tools.path_tools.refactor", "check"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode == 0:
        return []
    message = result.stderr.strip() or result.stdout.strip() or "pathref check failed"
    return [AuditFinding("pathref", "error", message)]
