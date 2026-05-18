"""Governance audit rules."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.research.registry import default_tool_registry
from scripts.research.governance.schemas import AuditFinding, AuditReport
from scripts.research.platform.datasets import DatasetRegistry
from scripts.research.platform.docs_index import DocsIndexer
from scripts.research.platform.engine import DEFAULT_TEMPLATES
from scripts.research.platform.engine import validate_project_config
from scripts.research.platform.strategy_variants import StrategyManifestReader, VariantError
from scripts.research.platform.workflows import WorkflowTemplateError, load_workflow_templates
from scripts.tools.path_tools.aliases import validate_config_file as validate_path_alias_config


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
    findings.extend(_audit_governance_gate(root))
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


def _audit_governance_gate(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    hook = root / ".githooks" / "pre-commit"
    if not hook.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".githooks/pre-commit missing"))
    else:
        text = hook.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance gate" not in text:
            findings.append(AuditFinding("governance_gate", "error", "pre-commit hook missing governance gate"))

    workflow = root / ".github" / "workflows" / "research-governance.yml"
    if not workflow.is_file():
        findings.append(AuditFinding("governance_gate", "error", ".github/workflows/research-governance.yml missing"))
    else:
        text = workflow.read_text(encoding="utf-8", errors="ignore")
        if "scripts.research.governance gate" not in text:
            findings.append(AuditFinding("governance_gate", "error", "CI workflow missing governance gate"))

    claude = root / "CLAUDE.md"
    if claude.is_file() and "scripts.research.governance gate" not in claude.read_text(encoding="utf-8", errors="ignore"):
        findings.append(AuditFinding("governance_gate", "error", "CLAUDE.md missing governance gate entry"))
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
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)
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


def _audit_pathrefs(root: Path) -> list[AuditFinding]:
    result = subprocess.run(
        [sys.executable, "-m", "scripts.tools.path_tools.refactor", "check"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode == 0:
        return []
    message = result.stderr.strip() or result.stdout.strip() or "pathref check failed"
    return [AuditFinding("pathref", "error", message)]
