"""Governance audit rules."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import yaml

from scripts.research.registry import default_tool_registry
from scripts.research.governance.skill_ownership import validate_ownerships
from scripts.research.governance import pr_flow_contract
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
    "docs/rules/pr-flow-interface-contract.yaml",
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
    ".agents/skills/**",
    ".claude/skills",
    ".codex/environments/**",
    ".claude/settings.json",
    ".claude/settings.local.json",
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
PR_TEMPLATE_TOKENS = (
    "pr-flow:start",
    "```json",
    "pr-flow:end",
)
REQUIRED_REVIEW_GUIDELINES_TOKENS = (
    "Codex Code Review",
    "@codex review",
    "AGENTS.md",
    "docs/rules/review-guidelines.md",
    "P0/P1",
    "PR Flow / review-status",
    "PR Flow / evidence",
    "PR Evidence JSON",
    "至少两个独立 reviewer",
    "子 agent 交叉评审",
    "superpowers:subagent-driven-development/spec-reviewer-prompt.md",
    "superpowers:subagent-driven-development/code-quality-reviewer-prompt.md",
    "reviewers:",
    "review_mode=complete",
    "review_mode=partial",
    "codex-security",
    "security-guidance",
    "retained",
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
    "authorize-main",
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
    "sub-agents",
    "delegation",
    "parallel agent work",
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


def _workflow_event_types_exact(
    text: str, event: str, expected_types: Sequence[str]
) -> bool:
    match = re.search(rf"{re.escape(event)}:\s*\n\s*types:\s*\[([^\]]*)\]", text)
    if not match:
        return False
    declared = tuple(item.strip() for item in match.group(1).split(",") if item.strip())
    return declared == tuple(expected_types)


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
    findings.extend(_audit_pr_flow_contract(root))
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


def _audit_pr_flow_contract(root: Path) -> list[AuditFinding]:
    try:
        pr_flow_contract.load_contract(root)
    except ValueError as exc:
        return [AuditFinding("pr_flow_contract", "error", str(exc))]
    return []


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
    # CLAUDE.md is now a File Symlink to AGENTS.md — content audit is
    # redundant since both resolve to the same file. Symlink validity is
    # checked by skill_ownership.

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
            "git config core.symlinks true",
            "CLAUDE.md",
            ".claude/skills",
            "git checkout --",
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
            ".githooks/post-commit",
            "git config core.symlinks true",
            "CLAUDE.md",
            ".claude/skills",
            "git checkout --",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"setup-python.sh missing {token}",
                    )
                )

    codex_environment = root / ".codex" / "environments" / "environment.toml"
    if not codex_environment.is_file():
        findings.append(
            AuditFinding(
                "governance_gate",
                "error",
                ".codex/environments/environment.toml missing",
            )
        )
    else:
        text = codex_environment.read_text(encoding="utf-8", errors="ignore")
        for token in (
            ".\\.githooks\\setup-python.ps1",
            "git config core.symlinks true",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"environment.toml missing {token}",
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
        if "scripts.research.governance.pr_flow intent pre-commit" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-commit hook missing intent pre-commit gate",
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

    post_commit = root / ".githooks" / "post-commit"
    if not post_commit.is_file():
        findings.append(
            AuditFinding("governance_gate", "error", ".githooks/post-commit missing")
        )
    else:
        text = post_commit.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance.pr_flow intent post-commit" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "post-commit hook missing intent post-commit gate",
                )
            )
        if "powershell.exe" in text or ".githooks/run-python.sh" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "post-commit hook must use run-python.sh",
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
        if "scripts.research.governance.pr_flow pre-push-review-fragments" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-push hook missing local review fragments freshness reminder",
                )
            )
        if (
            "scripts.research.governance gate" in text
            or "scripts.research.governance verify fast" in text
            or "scripts.research.governance verify full" in text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "pre-push hook must not run local governance verification",
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
            "refs/heads/",
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
                    "governance_gate",
                    "error",
                    "CI workflow missing verify full entrypoint",
                )
            )
        if "git config core.symlinks true" not in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow must configure core.symlinks true before verify full",
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
        if not re.search(r"push:\s*\n\s*branches:\s*\[\s*main\s*\]", text):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow push trigger must be limited to main",
                )
            )
        if not _workflow_event_types_exact(
            text, "pull_request", ("opened", "synchronize", "reopened")
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow pull_request events must be head-only: opened, synchronize, reopened",
                )
            )
        if "pull_request_review:" in text or "pull_request_review_comment:" in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "CI workflow must not listen to review or thread events",
                )
            )
    pr_flow_workflow = root / ".github" / "workflows" / "pr-flow.yml"
    if not pr_flow_workflow.is_file():
        findings.append(
            AuditFinding(
                "governance_gate", "error", ".github/workflows/pr-flow.yml missing"
            )
        )
    else:
        text = pr_flow_workflow.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "name: PR Flow",
            "evidence:",
            "scripts.research.governance.pr_review_evidence",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"PR Flow evidence workflow missing {token}",
                    )
                )
        workflow_tokens = (
            (
                "actions/checkout@v4",
                "PR Flow evidence workflow must checkout the PR head",
            ),
            (
                "github.event.pull_request.head.sha",
                "PR Flow evidence workflow must checkout the current PR head",
            ),
            ("fetch-depth: 0", "PR Flow evidence workflow must fetch full history"),
            (
                "refs/remotes/origin/${{ github.event.pull_request.base.ref }}",
                "PR Flow evidence workflow must fetch the PR base branch",
            ),
        )
        for token, message in workflow_tokens:
            if token not in text:
                findings.append(AuditFinding("governance_gate", "error", message))
        if (
            "Publish PR Flow evidence status" in text
            and "github.event.pull_request.state == 'open'" not in text
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR Flow evidence workflow must verify open PR before publishing evidence status",
                )
            )
        if re.search(r"evidence:\s*\n\s*if:", text):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "required PR Flow evidence job must not use job-level if",
                )
            )
        if not _workflow_event_types_exact(
            text, "pull_request", ("opened", "synchronize", "reopened", "edited")
        ):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR Flow evidence workflow pull_request events must be opened, synchronize, reopened, edited only",
                )
            )
        if "pull_request_review:" in text or "pull_request_review_comment:" in text:
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR Flow evidence workflow must not listen to review or thread events",
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
            "pull_request_review",
            "pull_request_review_comment",
            "workflow_dispatch",
            "expected_head_sha",
            "trigger_event",
            "trigger_run_id",
            "statuses: write",
            "python -m pip install -r requirements-dev.txt",
            "scripts.research.governance.codex_review_monitor",
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
        if "issue_comment" in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor worker workflow must not listen to issue_comment; use codex-review-router.yml",
                )
            )
        if "actions: write" in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor worker workflow must not have actions: write permission",
                )
            )
        if "--sync-comment" in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must not sync PR Flow status comments",
                )
            )
        if "github.event.repository.default_branch" in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must checkout PR head instead of default branch for issue_comment events",
                )
            )
        if "ref: ${{ steps.pr-head.outputs.sha }}" not in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must checkout PR head with steps.pr-head.outputs.sha",
                )
            )
        if "Publish pending status" not in text or "pending" not in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor worker workflow must publish pending for PR Flow / review-status",
                )
            )
        if "github.event_name != 'workflow_dispatch'" in text:
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor worker workflow_dispatch must be covered by pending and failure finalizer",
                )
            )
        if (
            "PR head changed before monitor completed" not in text
            or 'state="error"' not in text
        ):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor worker workflow must write error when expected_head_sha does not match current PR head",
                )
            )
        if (
            "Publish monitor failure status" not in text
            or "failure()" not in text
            or "cancelled()" not in text
            or "PR Flow / review-status" not in text
        ):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must include a failure status finalizer for PR Flow / review-status",
                )
            )
        if not _workflow_event_types_exact(
            text, "pull_request", ("opened", "synchronize", "reopened")
        ):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow pull_request events must be head-only: opened, synchronize, reopened",
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

    router_workflow = root / ".github" / "workflows" / "codex-review-router.yml"
    if not router_workflow.is_file():
        findings.append(
            AuditFinding(
                "codex_review_router",
                "error",
                ".github/workflows/codex-review-router.yml missing",
            )
        )
    else:
        text = router_workflow.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "issue_comment",
            "created",
            "edited",
            "deleted",
            "actions: write",
            "pull-requests: read",
            "statuses: write",
            "github.event.issue.pull_request",
            "@codex review",
            "Codex Review:",
            "PR Flow / review-status",
            'state="pending"',
            "actions/workflows/codex-review-monitor.yml/dispatches",
            'ref="$env:PR_HEAD_REF"',
            "inputs[pr_number]",
            "inputs[expected_head_sha]",
            "inputs[trigger_event]=issue_comment",
            "inputs[trigger_run_id]",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "codex_review_router",
                        "error",
                        f"review-status router workflow missing {token}",
                    )
                )
        if "actions/checkout" in text:
            findings.append(
                AuditFinding(
                    "codex_review_router",
                    "error",
                    "review-status router workflow must not checkout PR branch code",
                )
            )
        if 'state="success"' in text:
            findings.append(
                AuditFinding(
                    "codex_review_router",
                    "error",
                    "review-status router workflow must not publish success after dispatch",
                )
            )

    pr_workflow = root / "docs" / "rules" / "pr-workflow.md"
    if pr_workflow.is_file():
        text = pr_workflow.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "所有进入主干的改动必须通过 PR",
            "直写主干",
            "authorize-main",
            "ALLOW_DIRECT_MAIN_WRITE",
            "DIRECT_MAIN_WRITE_REASON",
            "禁止把功能分支本地合入",
            "git fetch origin main",
            "git merge --ff-only origin/main",
            "git push -u origin HEAD:<branch>",
            "delegation_attempt",
            "spawn_agent",
            "git branch -d <branch>",
            "远端分支删除交给 GitHub",
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
            "authorize-main",
            "git push -u origin HEAD:<branch>",
            "PR Flow / review-status",
            "Research Governance / verify-full",
            "PR Flow / evidence",
            "PR Evidence JSON issues",
            "no-Issue PR Evidence minimum",
        ):
            if token not in text:
                findings.append(
                    AuditFinding(
                        "governance_gate", "error", f"governance.md missing {token}"
                    )
                )
    for rel_path in (
        "docs/rules/pr-workflow.md",
        "docs/rules/governance.md",
        "docs/rules/commands.md",
        "scripts/research/governance/README.md",
    ):
        path = root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in ("$env:ALLOW_MAIN_REF_UPDATE", "$env:ALLOW_DIRECT_MAIN_WRITE"):
            if token in text:
                findings.append(
                    AuditFinding(
                        "governance_gate",
                        "error",
                        f"{rel_path} must use authorize-main instead of {token}",
                    )
                )
    if (root / ".git").exists() and not os.environ.get("GITHUB_ACTIONS"):
        hooks_path = _read_git_hooks_path(root)
        if hooks_path != ".githooks":
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    f"core.hooksPath must be set to .githooks (current: {hooks_path or 'not set'})",
                )
            )
    return findings


def _read_git_hooks_path(root: Path) -> str | None:
    """Read the current core.hooksPath git config value.

    Returns the trimmed config value or None if not set / not a git repo.
    """
    result = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


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
        "pr-submit",
        "scripts.research.governance verify fast --staged",
        "scripts.research.governance verify full",
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
        elif adr_index.read_text(encoding="utf-8", errors="ignore") != render_adr_index(
            root
        ):
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
        for token in (
            "docs/rules/index.md",
            "docs/adr/index.md",
            "PR Flow / review-status",
        ):
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
