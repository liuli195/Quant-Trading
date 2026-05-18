from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance.branch_protection import check_pre_push_input
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
        "docs/rules",
        "docs/adr",
        "docs/exceptions",
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
        "docs/guides/research-workflow.md",
        "docs/architecture/research-platform-architecture.md",
        "docs/rules/index.md",
        "docs/rules/ai-agents.md",
        "docs/rules/governance.md",
        "docs/rules/research-workflow.md",
        "docs/rules/code-style.md",
        "docs/rules/docs-and-pathref.md",
        "docs/adr/0001-rule-source-and-governance-model.md",
        "docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md",
        "docs/adr/0003-governance-gate-and-main-branch-protection.md",
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
        "scripts.research.governance scripts.research.governance gate scripts.research.registry "
        "docs/rules/index.md docs/adr/",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text(
        "所有 AI 编码助手统一以 CLAUDE.md 为权威规则源。\n",
        encoding="utf-8",
    )
    (root / ".githooks/pre-commit").write_text(
        "python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    (root / ".githooks/pre-push").write_text(
        "python -m scripts.research.governance.branch_protection pre-push\n",
        encoding="utf-8",
    )
    (root / ".github/workflows/research-governance.yml").write_text(
        "on:\n  schedule:\n    - cron: '0 2 * * 1'\nsteps:\n  - run: python -m scripts.research.governance gate\n",
        encoding="utf-8",
    )
    (root / "scripts/research/governance/README.md").write_text(
        "docs/rules/index.md docs/adr scripts.research.governance gate\n",
        encoding="utf-8",
    )
    (root / "CODEOWNERS").write_text(
        "\n".join(
            [
                "CLAUDE.md @research-platform",
                "AGENTS.md @research-platform",
                "docs/rules/** @research-platform",
                "docs/adr/** @research-platform",
                ".claude/skills/** @research-platform",
                ".github/workflows/** @research-platform",
                ".githooks/** @research-platform",
                "scripts/research/governance/** @research-platform",
                "scripts/research/registry/** @research-platform",
                "path_aliases.json @research-platform",
                "strategies/** @research-platform",
            ]
        ),
        encoding="utf-8",
    )
    (root / ".github/pull_request_template.md").write_text(
        "改动目标\n影响范围\n规则同步\n已运行检查\nwaiver\n证据\n",
        encoding="utf-8",
    )
    (root / "docs/exceptions/active-waivers.yaml").write_text(
        "schema_version: 1\nwaivers: []\n",
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


def test_governance_audit_flags_missing_codeowners_coverage(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "CODEOWNERS").write_text("CLAUDE.md @research-platform\n", encoding="utf-8")
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "codeowners" and "docs/rules/**" in finding.message for finding in report.findings)


def test_governance_audit_flags_invalid_pr_template(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".github/pull_request_template.md").write_text("改动目标\n", encoding="utf-8")
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "pr_template" and "规则同步" in finding.message for finding in report.findings)


def test_governance_audit_flags_expired_waiver(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/exceptions/active-waivers.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "waivers:",
                "  - id: WAIVER-2000-001",
                "    rule_id: test-rule",
                "    path: docs/**",
                "    reason: test",
                "    owner: research-platform",
                "    approved_by: research-platform",
                "    expires_at: 2000-01-01",
                "    migration_plan: docs/migration.md",
            ]
        ),
        encoding="utf-8",
    )
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "waiver" and "expired" in finding.message for finding in report.findings)


def test_governance_audit_flags_adr_number_gap(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "docs/adr/0002-ai-agent-parallel-work-uses-git-branches.md").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "adr" and "continuous" in finding.message for finding in report.findings)


def test_governance_audit_flags_missing_pre_push_branch_protection(tmp_path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / ".githooks/pre-push").unlink()
    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)
    assert not report.ok
    assert any(finding.rule_id == "governance_gate" and "pre-push" in finding.message for finding in report.findings)


def test_pre_push_branch_protection_blocks_main() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/main def456\n",
        environ={},
    )
    assert violations == ["main"]


def test_pre_push_branch_protection_allows_feature_branch() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/feature/topic def456\n",
        environ={},
    )
    assert violations == []


def test_pre_push_branch_protection_allows_explicit_bypass() -> None:
    violations = check_pre_push_input(
        "refs/heads/topic abc123 refs/heads/main def456\n",
        environ={"ALLOW_PROTECTED_BRANCH_PUSH": "1"},
    )
    assert violations == []
