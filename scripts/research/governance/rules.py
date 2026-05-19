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
from scripts.research.governance.schemas import AuditFinding, AuditReport
from scripts.research.platform.datasets import DatasetRegistry
from scripts.research.platform.docs_index import DocsIndexer
from scripts.research.platform.engine import DEFAULT_TEMPLATES
from scripts.research.platform.engine import validate_project_config
from scripts.research.platform.strategy_variants import StrategyManifestReader, VariantError
from scripts.research.platform.workflows import WorkflowTemplateError, load_workflow_templates
from scripts.tools.path_tools.aliases import validate_config_file as validate_path_alias_config


REQUIRED_RULE_DOCS = (
    "docs/rules/index.md",
    "docs/rules/ai-agents.md",
    "docs/rules/governance.md",
    "docs/rules/review-guidelines.md",
    "docs/rules/research-workflow.md",
    "docs/rules/code-style.md",
    "docs/rules/docs-and-pathref.md",
)
REQUIRED_CODEOWNER_PATTERNS = (
    "CLAUDE.md",
    "AGENTS.md",
    "docs/rules/**",
    "docs/adr/**",
    ".claude/skills/**",
    ".github/workflows/**",
    ".githooks/**",
    "scripts/research/governance/**",
    "scripts/research/registry/**",
    "path_aliases.json",
    "strategies/**",
)
PR_TEMPLATE_TOKENS = (
    "改动目标",
    "影响范围",
    "规则同步",
    "已运行检查",
    "Codex Code Review 结论",
    "Codex",
    "scripts.research.governance gate",
    "waiver",
    "证据",
)
REQUIRED_REVIEW_GUIDELINES_TOKENS = (
    "Codex Code Review",
    "@codex review",
    "AGENTS.md",
    "docs/rules/review-guidelines.md",
    "逐条检查",
    "docs/rules/*.md",
    "P0/P1",
    "scripts.research.governance gate",
    "Codex Review Monitor",
    "Codex Code Review 结论",
    "结论: 通过",
    "阻断问题: 无",
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


def _workflow_event_types_include(text: str, event: str, required_types: Sequence[str]) -> bool:
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
    findings.extend(_audit_review_guidelines(root))
    findings.extend(_audit_governance_gate(root))
    findings.extend(_audit_rule_sources(root))
    findings.extend(_audit_codeowners(root))
    findings.extend(_audit_pr_template(root))
    findings.extend(_audit_waivers(root))
    findings.extend(_audit_path_aliases(root))
    findings.extend(_audit_strategy_manifests(root))
    findings.extend(_audit_project_configs(root))
    findings.extend(_audit_catalogs(root))
    findings.extend(_audit_workflow_templates(root))
    if check_cli_help:
        findings.extend(_audit_cli_help(root))
    if check_pathrefs:
        findings.extend(_audit_pathrefs(root))
    return AuditReport(ok=not any(item.severity == "error" for item in findings), findings=tuple(findings))


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
            findings.append(AuditFinding("layer_docs", "error", f"layer doc missing: {rel_path}"))
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
    claude = root / "CLAUDE.md"
    if not claude.is_file():
        findings.append(AuditFinding("claude_sync", "error", "CLAUDE.md missing"))
    else:
        text = claude.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "scripts.research.cli",
            "scripts.research.datasets",
            "scripts.research.variants",
            "scripts.research.governance",
            "scripts.research.registry",
            "docs/rules/index.md",
            "docs/rules/review-guidelines.md",
            "docs/adr",
            "Codex Code Review",
        ):
            if token not in text:
                findings.append(AuditFinding("claude_sync", "error", f"CLAUDE.md missing {token}"))

    skill = root / ".claude" / "skills" / "jq-research" / "SKILL.md"
    if not skill.is_file():
        findings.append(AuditFinding("skill_sync", "error", "jq-research skill missing"))
    else:
        text = skill.read_text(encoding="utf-8", errors="ignore")
        for token in ("scripts.research.cli", "scripts.research.governance", "variant"):
            if token not in text:
                findings.append(AuditFinding("skill_sync", "error", f"jq-research skill missing {token}"))

    ab_skill = root / ".claude" / "skills" / "jq-ab-test" / "SKILL.md"
    if not ab_skill.is_file():
        findings.append(AuditFinding("skill_sync", "error", "jq-ab-test skill missing"))
    else:
        text = ab_skill.read_text(encoding="utf-8", errors="ignore")
        for token in ("variant_id", "参数变体", "结构变体", "scripts.research.variants"):
            if token not in text:
                findings.append(AuditFinding("skill_sync", "error", f"jq-ab-test skill missing {token}"))
    return findings


def _audit_review_guidelines(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    path = root / "docs" / "rules" / "review-guidelines.md"
    if not path.is_file():
        return [AuditFinding("review_guidelines", "error", "docs/rules/review-guidelines.md missing")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    findings.extend(
        AuditFinding("review_guidelines", "error", f"review-guidelines.md missing {token}")
        for token in REQUIRED_REVIEW_GUIDELINES_TOKENS
        if token not in text
    )

    agents = root / "AGENTS.md"
    if agents.is_file():
        agents_text = agents.read_text(encoding="utf-8", errors="ignore")
        for token in ("## Review guidelines", "docs/rules/review-guidelines.md"):
            if token not in agents_text:
                findings.append(AuditFinding("review_guidelines", "error", f"AGENTS.md missing {token}"))
    return findings


def _audit_governance_gate(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    hook_python_sh = root / ".githooks" / "run-python.sh"
    if not hook_python_sh.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".githooks/run-python.sh missing"))
    else:
        text = hook_python_sh.read_text(encoding="utf-8", errors="ignore")
        for token in (".venv/bin/python", ".venv/Scripts/python.exe", '"$@"'):
            if token not in text:
                findings.append(AuditFinding("governance_gate", "error", f"run-python.sh missing {token}"))
        if "uname" not in text or not any(token in text for token in ("MINGW", "MSYS", "CYGWIN")):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "run-python.sh must choose venv by platform",
                )
            )
        if re.search(r'PYTHON=["\']?python["\']?', text) or re.search(r"exec\s+python(\s|$)", text):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "run-python.sh must not fall back to system Python",
                )
            )

    hook_python = root / ".githooks" / "run-python.ps1"
    if not hook_python.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".githooks/run-python.ps1 missing"))

    hook = root / ".githooks" / "pre-commit"
    if not hook.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".githooks/pre-commit missing"))
    else:
        text = hook.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance gate" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-commit hook missing governance gate"))
        if "powershell.exe" in text or ".githooks/run-python.sh" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-commit hook must use run-python.sh"))

    pre_push = root / ".githooks" / "pre-push"
    if not pre_push.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".githooks/pre-push missing"))
    else:
        text = pre_push.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance.branch_protection pre-push" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-push hook missing branch protection gate"))
        if "scripts.research.governance gate" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-push hook missing governance gate"))
        if "git lfs pre-push" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-push hook missing Git LFS handoff"))
        if "powershell.exe" in text or ".githooks/run-python.sh" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-push hook must use run-python.sh"))

    reference_transaction = root / ".githooks" / "reference-transaction"
    if not reference_transaction.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".githooks/reference-transaction missing"))
    else:
        text = reference_transaction.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance.branch_protection reference-transaction" not in text:
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
                AuditFinding("governance_gate", "error", "reference-transaction hook must use run-python.sh")
            )

    workflow = root / ".github" / "workflows" / "research-governance.yml"
    if not workflow.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".github/workflows/research-governance.yml missing"))
    else:
        text = workflow.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance gate" not in text:
            findings.append(AuditFinding("governance_gate", "error", "CI workflow missing governance gate"))
        if "scripts.research.governance.pr_review_evidence" not in text:
            findings.append(AuditFinding("governance_gate", "error", "CI workflow missing PR review evidence gate"))
        if "schedule:" not in text:
            findings.append(AuditFinding("governance_gate", "error", "CI workflow missing scheduled drift audit"))
        if not re.search(r"pull_request_review_comment:\s*\n\s*types:\s*\[[^\]]*deleted", text):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR review evidence workflow must listen to deleted inline review comments",
                )
            )
        if not _workflow_event_types_include(text, "pull_request_review", ("submitted", "edited", "dismissed")):
            findings.append(
                AuditFinding(
                    "governance_gate",
                    "error",
                    "PR review evidence workflow must listen to Codex review submitted, edited, and dismissed events",
                )
            )

    monitor_workflow = root / ".github" / "workflows" / "codex-review-monitor.yml"
    if not monitor_workflow.is_file():
        findings.append(AuditFinding("codex_review_monitor", "error", ".github/workflows/codex-review-monitor.yml missing"))
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
                findings.append(AuditFinding("codex_review_monitor", "error", f"monitor workflow missing {token}"))
        if not re.search(r"pull_request_review_comment:\s*\n\s*types:\s*\[[^\]]*deleted", text):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must listen to deleted inline review comments",
                )
            )
        if not _workflow_event_types_include(text, "pull_request_review", ("submitted", "edited", "dismissed")):
            findings.append(
                AuditFinding(
                    "codex_review_monitor",
                    "error",
                    "monitor workflow must listen to Codex review submitted, edited, and dismissed events",
                )
            )

    claude = root / "CLAUDE.md"
    if claude.is_file():
        text = claude.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "scripts.research.governance gate",
            "所有进入主干的改动必须通过 PR",
            "禁止本地合并主干",
        ):
            if token not in text:
                findings.append(AuditFinding("governance_gate", "error", f"CLAUDE.md missing {token}"))

    ai_agents = root / "docs" / "rules" / "ai-agents.md"
    if ai_agents.is_file():
        text = ai_agents.read_text(encoding="utf-8", errors="ignore")
        for token in (
            "所有进入主干的改动必须通过 PR",
            "禁止本地合并主干",
            "git fetch origin main",
            "git merge --ff-only origin/main",
            "git branch -d <branch>",
            "git push origin --delete <branch>",
        ):
            if token not in text:
                findings.append(AuditFinding("governance_gate", "error", f"ai-agents.md missing {token}"))

    governance = root / "docs" / "rules" / "governance.md"
    if governance.is_file():
        text = governance.read_text(encoding="utf-8", errors="ignore")
        for token in (
            ".githooks/reference-transaction",
            "ALLOW_MAIN_REF_UPDATE",
            "MAIN_REF_UPDATE_REASON",
            "Codex Review Monitor",
        ):
            if token not in text:
                findings.append(AuditFinding("governance_gate", "error", f"governance.md missing {token}"))
    return findings


def _audit_rule_sources(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for rel_path in REQUIRED_RULE_DOCS:
        if not (root / rel_path).is_file():
            findings.append(AuditFinding("rule_source", "error", f"rule doc missing: {rel_path}"))

    adr_root = root / "docs" / "adr"
    if not adr_root.is_dir():
        findings.append(AuditFinding("adr", "error", "docs/adr missing"))
    else:
        adr_files = sorted(path for path in adr_root.glob("*.md") if re.match(r"^\d{4}-", path.name))
        if not adr_files:
            findings.append(AuditFinding("adr", "error", "docs/adr has no numbered ADR files"))
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
        for token in ("CLAUDE.md", "权威规则源"):
            if token not in text:
                findings.append(AuditFinding("agent_rule_source", "error", f"AGENTS.md missing {token}"))

    governance_readme = root / "scripts" / "research" / "governance" / "README.md"
    if governance_readme.is_file():
        text = governance_readme.read_text(encoding="utf-8", errors="ignore")
        for token in ("docs/rules/index.md", "docs/adr", "Codex Review Monitor"):
            if token not in text:
                findings.append(AuditFinding("governance_docs", "error", f"governance README missing {token}"))
    return findings


def _audit_codeowners(root: Path) -> list[AuditFinding]:
    path = root / "CODEOWNERS"
    if not path.is_file():
        return [AuditFinding("codeowners", "error", "CODEOWNERS missing")]

    findings: list[AuditFinding] = []
    patterns: set[str] = set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        if len(parts) < 2:
            findings.append(AuditFinding("codeowners", "error", f"CODEOWNERS line {lineno} missing owner"))
            continue
        patterns.add(_normalize_codeowner_pattern(parts[0]))

    for pattern in REQUIRED_CODEOWNER_PATTERNS:
        if _normalize_codeowner_pattern(pattern) not in patterns:
            findings.append(AuditFinding("codeowners", "error", f"CODEOWNERS missing {pattern}"))
    return findings


def _audit_pr_template(root: Path) -> list[AuditFinding]:
    path = root / ".github" / "pull_request_template.md"
    if not path.is_file():
        return [AuditFinding("pr_template", "error", ".github/pull_request_template.md missing")]
    text = path.read_text(encoding="utf-8", errors="ignore")
    return [
        AuditFinding("pr_template", "error", f"PR template missing {token}")
        for token in PR_TEMPLATE_TOKENS
        if token not in text
    ]


def _audit_waivers(root: Path) -> list[AuditFinding]:
    path = root / "docs" / "exceptions" / "active-waivers.yaml"
    if not path.is_file():
        return [AuditFinding("waiver", "error", "docs/exceptions/active-waivers.yaml missing")]
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [AuditFinding("waiver", "error", f"invalid waiver YAML: {exc}")]
    if not isinstance(payload, dict):
        return [AuditFinding("waiver", "error", "waiver registry must be a mapping")]

    findings: list[AuditFinding] = []
    if payload.get("schema_version") != 1:
        findings.append(AuditFinding("waiver", "error", "waiver registry schema_version must be 1"))
    waivers = payload.get("waivers", [])
    if not isinstance(waivers, list):
        findings.append(AuditFinding("waiver", "error", "waivers must be a list"))
        return findings

    today = date.today()
    for index, waiver in enumerate(waivers, start=1):
        if not isinstance(waiver, dict):
            findings.append(AuditFinding("waiver", "error", f"waiver #{index} must be a mapping"))
            continue
        waiver_id = str(waiver.get("id") or f"#{index}")
        for field in WAIVER_REQUIRED_FIELDS:
            if not str(waiver.get(field, "")).strip():
                findings.append(AuditFinding("waiver", "error", f"{waiver_id}: {field} is required"))
        expires_at = _parse_date(waiver.get("expires_at"))
        if expires_at is None:
            findings.append(AuditFinding("waiver", "error", f"{waiver_id}: expires_at must be YYYY-MM-DD"))
        elif expires_at < today:
            findings.append(AuditFinding("waiver", "error", f"{waiver_id}: waiver expired at {expires_at.isoformat()}"))
    return findings


def _audit_catalogs(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    dataset_root = root / "research_datasets"
    catalog_path = dataset_root / "catalog.json"
    if not catalog_path.is_file():
        findings.append(AuditFinding("dataset_catalog", "error", "research_datasets/catalog.json missing"))
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
            findings.append(AuditFinding("report_catalog", "error", f"docs/indexes/{name} missing"))
    reports_index = index_root / "reports_catalog.json"
    if reports_index.is_file():
        payload = json.loads(reports_index.read_text(encoding="utf-8"))
        indexed = {row["path"] for row in payload.get("reports", [])}
        actual = {record.path for record in DocsIndexer(root).scan() if record.category != "docs"}
        for path in sorted(actual - indexed):
            findings.append(AuditFinding("report_catalog", "error", f"report catalog missing {path}"))
        for path in sorted(indexed - actual):
            findings.append(AuditFinding("report_catalog", "error", f"report catalog stale {path}"))
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
            findings.append(AuditFinding("project_config", "error", f"{rel}: invalid JSON: {exc}"))
            continue
        for error in validate_project_config(payload):
            findings.append(AuditFinding("project_config", "error", f"{rel}: {error}"))
    return findings


def _audit_strategy_manifests(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    reader = StrategyManifestReader(root / "strategies")
    for strategy_root in sorted(path for path in (root / "strategies").glob("*") if path.is_dir()):
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
        templates = load_workflow_templates(root / "scripts" / "research" / "workflows" / "templates")
    except WorkflowTemplateError as exc:
        return [AuditFinding("workflow_template", "error", str(exc))]
    expected = set(DEFAULT_TEMPLATES) | {"cloud_confirmation"}
    actual = {template.template for template in templates}
    findings: list[AuditFinding] = []
    for name in sorted(expected - actual):
        findings.append(AuditFinding("workflow_template", "error", f"workflow template missing {name}"))
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
            findings.append(AuditFinding("tool_registry", "error", f"CLI module not registered: {module}"))
    return findings


def _discover_cli_modules(root: Path) -> list[str]:
    modules: list[str] = []
    for package_root in (root / "scripts" / "research", root / "scripts" / "tools"):
        if not package_root.is_dir():
            continue
        for path in sorted(package_root.rglob("*.py")):
            rel_parts = path.relative_to(root).parts
            if any(part in {"__pycache__", "tests", "snippets", "utils", "archive"} for part in rel_parts):
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
    if module.startswith("scripts.research.governance.") and "scripts.research.governance" in registered:
        return True
    if module == "scripts.tools.jq_automation.cli" and "scripts.tools.jq_automation" in registered:
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
