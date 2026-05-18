from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance.rules import run_audit
from scripts.research.registry import default_tool_registry


def _write_minimal_repo(root: Path) -> None:
    for path in (
        "scripts/research",
        "scripts/research/platform",
        "scripts/research/registry",
        "scripts/research/registry/tests",
        "scripts/research/governance",
        "scripts/research/governance/tests",
        "scripts/research/research_core",
        "scripts/research/research_core/tests",
        "scripts/research/etf_window_research/tests",
        "scripts/research/momentum_tilt_research/tests",
        "scripts/research/execution_timing_research/tests",
        "scripts/research/portfolio_volatility_research/tests",
        "scripts/research/cash_decomposition",
        "scripts/research/workflows/templates",
        "scripts/tools/jq_automation/tests",
        "scripts/tools/path_tools",
        "docs/indexes",
        "research_datasets/demo/snap",
        "research_datasets",
        ".github/workflows",
        ".githooks",
        ".claude/skills/jq-research",
        ".claude/skills/jq-ab-test",
        "research_datasets/demo/snap/raw",
        "research_datasets/demo/snap/data",
    ):
        (root / path).mkdir(parents=True, exist_ok=True)

    for path in (
        "scripts/research/README.md",
        "scripts/research/platform/README.md",
        "scripts/research/registry/README.md",
        "scripts/research/governance/README.md",
        "scripts/research/research_core/README.md",
        "scripts/research/etf_window_research/README.md",
        "scripts/research/momentum_tilt_research/README.md",
        "scripts/research/execution_timing_research/README.md",
        "scripts/research/portfolio_volatility_research/README.md",
        "scripts/research/cash_decomposition/README.md",
        "scripts/research/workflows/README.md",
        "scripts/tools/jq_automation/README.md",
        "scripts/tools/path_tools/README.md",
        "docs/research-workflow.md",
        "docs/research-platform-architecture.md",
        "research_datasets/README.md",
        "scripts/research/platform/tests/test_platform.py",
        "scripts/research/registry/tests/test_registry.py",
        "scripts/research/governance/tests/test_governance.py",
        "scripts/research/research_core/tests/test_research_core.py",
        "scripts/research/etf_window_research/tests/test_analysis.py",
        "scripts/research/momentum_tilt_research/tests/test_analysis.py",
        "scripts/research/execution_timing_research/tests/test_analysis.py",
        "scripts/research/portfolio_volatility_research/tests/test_domain_builder.py",
        "scripts/tools/jq_automation/tests/test_core.py",
        "scripts/tools/jq_automation/tests/test_ab.py",
    ):
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("placeholder\n", encoding="utf-8")

    (root / "CLAUDE.md").write_text(
        "scripts.research.cli scripts.research.datasets scripts.research.variants "
        "scripts.research.governance scripts.research.governance gate scripts.research.registry",
        encoding="utf-8",
    )
    (root / ".githooks/pre-commit").write_text(
        "python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    (root / ".github/workflows/research-governance.yml").write_text(
        "run: python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    (root / ".claude/skills/jq-research/SKILL.md").write_text(
        "scripts.research.cli scripts.research.governance variant",
        encoding="utf-8",
    )
    (root / ".claude/skills/jq-ab-test/SKILL.md").write_text(
        "variant_id 参数变体 结构变体 scripts.research.variants",
        encoding="utf-8",
    )
    (root / "path_aliases.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "owner": "research-platform",
                "lifecycle": "active",
                "roots": {"repo": ".", "strategies": "strategies", "research_datasets": "research_datasets"},
                "aliases": {"strategy_dir": "{strategies}/{strategy}"},
            }
        ),
        encoding="utf-8",
    )

    dataset = {
        "schema_version": 1,
        "dataset_id": "demo",
        "snapshot_id": "snap",
        "fingerprint": "sha256:x",
        "created_at": "2026-01-01T00:00:00+00:00",
        "owner": "research-platform",
        "lifecycle": "active",
        "row_count": 1,
        "date_range": ["2026-01-01", "2026-01-01"],
        "source": {"kind": "test"},
        "files": {"raw": "raw/source.json.gz", "canonical": "data/data.parquet"},
    }
    (root / "research_datasets/demo/snap/raw/source.json.gz").write_bytes(b"demo")
    (root / "research_datasets/demo/snap/data/data.parquet").write_bytes(b"demo")
    (root / "research_datasets/demo/snap/dataset.json").write_text(
        json.dumps(dataset),
        encoding="utf-8",
    )
    (root / "research_datasets/catalog.json").write_text(
        json.dumps(
            [
                {
                    "dataset_id": "demo",
                    "snapshot_id": "snap",
                    "fingerprint": "sha256:x",
                    "row_count": 1,
                    "date_range": ["2026-01-01", "2026-01-01"],
                    "source_kind": "test",
                    "owner": "research-platform",
                    "lifecycle": "active",
                }
            ]
        ),
        encoding="utf-8",
    )
    for name in (
        "docs_catalog.json",
        "reports_catalog.json",
        "datasets_catalog.json",
        "variants_catalog.json",
    ):
        (root / "docs/indexes" / name).write_text(json.dumps({"reports": []}), encoding="utf-8")

    for template in (
        "factor_scan",
        "parameter_followup",
        "robustness_check",
        "generic",
        "portfolio_volatility",
        "cloud_confirmation",
    ):
        (root / "scripts/research/workflows/templates" / f"{template}.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "template": template,
                    "inputs": ["dataset"],
                    "stages": ["init", "fast"],
                    "outputs": ["manifest"],
                    "gates": ["documented"],
                }
            ),
            encoding="utf-8",
        )

    default_tool_registry().write_layer_docs(root / "scripts/research/layers")


def test_governance_audit_passes_minimal_repo_without_expensive_checks(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert report.ok
    assert report.findings == ()


def test_governance_audit_flags_catalog_drift(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "research_datasets/catalog.json").write_text("[]", encoding="utf-8")
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "dataset_catalog" for finding in report.findings)


def test_governance_audit_flags_unregistered_cli_module(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    tool = tmp_path / "scripts/research/new_tool.py"
    tool.write_text(
        "\n".join(
            [
                "import argparse",
                "",
                "def main(argv=None):",
                "    parser = argparse.ArgumentParser()",
                "    parser.parse_args(argv)",
                "    return 0",
                "",
                "if __name__ == '__main__':",
                "    raise SystemExit(main())",
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(
        "CLI module not registered: scripts.research.new_tool" in finding.message
        for finding in report.findings
    )


def test_governance_audit_flags_stale_layer_docs(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "scripts/research/layers/strategy_library.md").write_text("stale\n", encoding="utf-8")
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "layer_docs" for finding in report.findings)


def test_governance_audit_flags_invalid_path_aliases(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "path_aliases.json").write_text(
        json.dumps({"schema_version": 1, "owner": "", "lifecycle": "active", "roots": {}, "aliases": {}}),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "path_aliases" for finding in report.findings)


def test_governance_audit_flags_project_config_without_owner(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    project = tmp_path / "strategies/demo/reports/research/topic/project.json"
    project.parent.mkdir(parents=True, exist_ok=True)
    project.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "strategy": "demo",
                "project": "topic",
                "template": "generic",
                "plugin": "generic",
                "datasets": [],
                "inputs": {},
                "runtime": {
                    "fast_top_k": 1,
                    "cloud_top_k": 0,
                    "fast_mode_slo_seconds": 1.0,
                    "full_mode_slo_seconds": 1.0,
                },
            }
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "project_config" and "owner is required" in finding.message for finding in report.findings)
