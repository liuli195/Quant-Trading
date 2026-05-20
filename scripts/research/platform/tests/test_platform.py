from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research import datasets as datasets_cli
from scripts.research.platform.contracts import FidelityLevel, validate_baseline_exports
from scripts.research.platform.batch_executor import execute_batch
from scripts.research.platform.benchmark_runner import run_smoke_benchmark
from scripts.research.platform.coverage_audit import (
    ScanCoverageSlice,
    audit_scan_coverage,
    coverage_is_complete,
)
from scripts.research.platform.datasets import (
    BacktestRunImporter,
    DataViewLoader,
    DatasetError,
    DatasetRegistry,
    import_backtest_run,
    import_joinquant_price_json,
    load_price_frames,
    migrate_backtest_runs_to_datasets,
)
from scripts.research.platform.docs_index import DocsIndexer, EvidenceLinker, ReportRegistry
from scripts.research.platform.engine import create_project, load_project, promote_run, resume_run, run_project
from scripts.research.platform.features import FeatureStore
from scripts.research.platform.funnel import build_fast_funnel, promote_full_funnel
from scripts.research.platform.plugins import (
    BUILTIN_PLUGINS,
    PARAMETER_REPLAY_ADAPTERS,
    ParameterReplayAdapter,
    PortfolioVolatilityPlugin,
)
from scripts.research.platform.strategy_variants import (
    GitAuthorizationError,
    VariantError,
    StrategyManifestReader,
    StrategyMaterializer,
    StructuralBranchManager,
    VariantMergeManager,
    VariantRegistry,
)
from scripts.research.platform.workflows import WorkflowTemplateError, load_workflow_templates
from scripts.research.research_core.metrics import MetricToolkit
from scripts.research.research_core.metrics import parse_cumulative_returns_md
from scripts.research.research_core.audit import load_rebalance_events
from scripts.research.research_core.replay import ReplayResult
from scripts.research.research_core.robustness import RobustnessToolkit
from scripts.research.etf_window_research.spec import ETF_CODES


def _write_price_bundle(path: Path) -> None:
    dates = pd.bdate_range("2018-01-01", periods=800)
    payload = {
        "metadata": {"fields": ["open", "close", "high", "low", "money"]},
        "calendar": [day.date().isoformat() for day in dates],
        "prices": {},
    }
    for idx, code in enumerate(ETF_CODES):
        close = np.linspace(1.0 + idx, 2.0 + idx, len(dates))
        payload["prices"][code] = [
            {
                "date": day.date().isoformat(),
                "open": float(value * 0.995),
                "close": float(value),
                "high": float(value * 1.01),
                "low": float(value * 0.99),
                "money": float(1_000_000 + idx),
            }
            for day, value in zip(dates, close, strict=True)
        ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_daily_returns(path: Path, cumulative: list[float]) -> None:
    dates = pd.bdate_range("2021-01-01", periods=len(cumulative))
    lines = ["| date | cumulative_return |", "| --- | ---: |"]
    lines.extend(f"| {day.date().isoformat()} | {value:.6f} |" for day, value in zip(dates, cumulative, strict=True))
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_backtest_run(root: Path) -> None:
    tabs = root / "tabs_raw"
    report = root / "report"
    tabs.mkdir(parents=True)
    report.mkdir()
    (root / "summary_metrics.json").write_text(json.dumps({"sharpe": 1.2}), encoding="utf-8")
    (root / "metadata.json").write_text(json.dumps({"backtest_id": "abc"}), encoding="utf-8")
    (root / "api_export.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
    (tabs / "daily_returns.md").write_text(
        "\n".join(
            [
                "| date | cumulative_return |",
                "| --- | ---: |",
                "| 2026-01-01 | 0.010000 |",
                "| 2026-01-02 | 0.030000 |",
            ]
        ),
        encoding="utf-8",
    )
    events = [
        {
            "seq": 1,
            "event": "run_start",
            "current_dt": "2026-01-01 09:30:00",
            "params": {"etf_pool": ["510300.XSHG", "159915.XSHE"]},
        },
        {
            "seq": 2,
            "event": "rebalance_signals",
            "current_dt": "2026-01-02 09:30:00",
            "trend_gates": [1, 0],
        },
    ]
    (tabs / "audit_log.jsonl").write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )
    (report / "backtest_report.md").write_text("# 回测报告\n", encoding="utf-8")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    _git(repo, "branch", "-M", "main")


def test_feature_store_reuses_payload(tmp_path) -> None:
    store = FeatureStore(tmp_path)
    key = store.cache_key(dataset_fingerprint="sha256:x", feature_spec={"a": 1}, code_version="v1")
    first = store.load_or_build(key, lambda: {"value": 1})
    second = store.load_or_build(key, lambda: {"value": 2})
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.payload == {"value": 1}


def test_dataset_snapshot_writes_parquet_and_human_views(tmp_path) -> None:
    raw = tmp_path / "prices.json"
    _write_price_bundle(raw)
    snapshot = import_joinquant_price_json(
        raw,
        dataset_id="demo_prices",
        snapshot_id="snap-1",
        datasets_root=tmp_path / "research_datasets",
    )
    assert snapshot.raw_path.exists()
    assert snapshot.parquet_path.exists()
    assert (snapshot.root / "views" / "profile.md").exists()
    assert (tmp_path / "research_datasets" / "catalog.md").exists()
    frames = load_price_frames(snapshot)
    assert not frames.open.empty
    assert not frames.close.empty


def test_backtest_run_importer_preserves_run_and_views(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)

    snapshot = BacktestRunImporter(tmp_path / "research_datasets").import_run(
        run_dir,
        dataset_id="demo_run",
        snapshot_id="snap-1",
    )
    loader = DataViewLoader(snapshot)
    assert (snapshot.root / "raw" / "api_export.json.gz").is_file()
    assert not (snapshot.root / "raw" / "backtest_run").exists()
    assert (snapshot.root / "raw" / "audit_log.jsonl.gz").is_file()
    assert (snapshot.root / "data" / "data.parquet").is_file()
    assert not (snapshot.root / "data" / "daily_returns.parquet").exists()
    assert (snapshot.root / "data" / "audit_events.parquet").is_file()
    assert loader.summary_metrics()["sharpe"] == 1.2
    assert loader.daily_returns()["cumulative_return"].tolist() == [0.01, 0.03]
    assert loader.audit_events()[0]["event"] == "run_start"
    assert snapshot.metadata["audit_line_count"] == 2
    assert snapshot.metadata["audit_date_range"] == ["2026-01-01", "2026-01-02"]
    assert snapshot.metadata["etf_pool"] == ["510300.XSHG", "159915.XSHE"]
    catalog = json.loads((tmp_path / "research_datasets" / "catalog.json").read_text(encoding="utf-8"))
    assert catalog[0]["source_kind"] == "joinquant_backtest_run"
    assert catalog[0]["owner"] == "research-platform"
    assert DatasetRegistry(tmp_path / "research_datasets").validate() == []


def test_backtest_run_importer_compresses_large_sources_and_keeps_views(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    (run_dir / "detail_api_export.json").write_text(json.dumps({"detail": ["x"] * 200}), encoding="utf-8")

    snapshot = import_backtest_run(
        run_dir,
        dataset_id="demo_run",
        snapshot_id="snap-1",
        datasets_root=tmp_path / "research_datasets",
    )
    loader = DataViewLoader(snapshot)

    assert not (snapshot.root / "raw" / "backtest_run").exists()
    assert (snapshot.root / "raw" / "api_export.json.gz").is_file()
    assert (snapshot.root / "raw" / "detail_api_export.json.gz").is_file()
    assert (snapshot.root / "raw" / "audit_log.jsonl.gz").is_file()
    assert snapshot.metadata["files"]["api_export_source"] == "raw/api_export.json.gz"
    assert snapshot.metadata["files"]["detail_api_export_source"] == "raw/detail_api_export.json.gz"
    assert snapshot.metadata["files"]["audit_log_source"] == "raw/audit_log.jsonl.gz"
    assert loader.summary_metrics()["sharpe"] == 1.2
    assert loader.daily_returns()["cumulative_return"].tolist() == [0.01, 0.03]
    assert loader.audit_events()[0]["event"] == "run_start"


def test_backtest_run_importer_compacts_three_redundancy_classes(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    tabs = run_dir / "tabs_raw"
    (tabs / "positioninfo.md").write_text("| date | code | value |\n| 2026-01-01 | 510300.XSHG | 1 |\n", encoding="utf-8")
    (tabs / "transactioninfo.md").write_text("| date | code | value |\n| 2026-01-01 | 510300.XSHG | 1 |\n", encoding="utf-8")
    (tabs / "balances.md").write_text("| date | total |\n| 2026-01-01 | 100000 |\n", encoding="utf-8")
    (tabs / "period_risks.md").write_text("| period | sharpe |\n| all | 1.2 |\n", encoding="utf-8")
    (tabs / "logs.md").write_text("2026-01-01 hello\n", encoding="utf-8")

    snapshot = import_backtest_run(
        run_dir,
        dataset_id="demo_run",
        snapshot_id="snap-1",
        datasets_root=tmp_path / "research_datasets",
    )
    loader = DataViewLoader(snapshot)

    assert (snapshot.root / "raw" / "summary_metrics.json.gz").is_file()
    assert (snapshot.root / "raw" / "daily_returns.md.gz").is_file()
    assert (snapshot.root / "raw" / "positioninfo.md.gz").is_file()
    assert not (snapshot.root / "raw" / "summary_metrics.json").exists()
    assert not (snapshot.root / "raw" / "daily_returns.md").exists()
    assert not (snapshot.root / "data" / "daily_returns.parquet").exists()
    assert not (snapshot.root / "views" / "daily_returns.csv").exists()
    assert snapshot.metadata["files"]["daily_returns"] == "data/data.parquet"
    assert snapshot.metadata["files"]["canonical"] == "data/data.parquet"
    assert "daily_returns_sample" not in snapshot.metadata["files"]
    assert snapshot.metadata["files"]["summary_metrics"] == "raw/summary_metrics.json.gz"
    assert snapshot.metadata["files"]["positioninfo_source"] == "raw/positioninfo.md.gz"
    assert snapshot.metadata["raw_file_integrity"]["tabs_raw/positioninfo.md"]["dataset_file"] == "raw/positioninfo.md.gz"
    assert loader.summary_metrics()["sharpe"] == 1.2
    assert "510300.XSHG" in loader.raw_text("positioninfo_source")
    assert DatasetRegistry(tmp_path / "research_datasets").validate() == []


def test_dataset_registry_flags_missing_declared_raw_gzip(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    snapshot = import_backtest_run(
        run_dir,
        dataset_id="demo_run",
        snapshot_id="snap-1",
        datasets_root=tmp_path / "research_datasets",
    )
    missing = snapshot.root / "raw" / "summary_metrics.json.gz"
    missing.unlink()

    errors = DatasetRegistry(tmp_path / "research_datasets").validate()

    assert any("missing raw_file_integrity dataset_file: summary_metrics.json" in error for error in errors)


def test_dataset_registry_allows_repo_ignored_raw_gzip_but_flags_tracked_snapshot_files(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / ".gitignore").write_text(
        "\n".join(
            [
                "research_datasets/**/raw/summary_metrics.json.gz",
                "research_datasets/**/raw/daily_returns.md.gz",
                "",
            ]
        ),
        encoding="utf-8",
    )
    run_dir = repo / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    snapshot = import_backtest_run(
        run_dir,
        dataset_id="demo_run",
        snapshot_id="snap-1",
        datasets_root=repo / "research_datasets",
    )
    (snapshot.root / "raw" / "summary_metrics.json.gz").unlink()
    (snapshot.root / "raw" / "daily_returns.md.gz").unlink()

    clean_checkout_errors = DatasetRegistry(repo / "research_datasets").validate()

    assert not any("missing raw_file_integrity dataset_file" in error for error in clean_checkout_errors)

    (snapshot.root / "raw" / "source.json.gz").unlink()

    damaged_snapshot_errors = DatasetRegistry(repo / "research_datasets").validate()

    assert any("missing declared dataset file raw:" in error for error in damaged_snapshot_errors)


def test_backtest_run_importer_accepts_utf8_bom_summary_metrics(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    (run_dir / "summary_metrics.json").write_bytes(
        b"\xef\xbb\xbf" + json.dumps({"sharpe": 1.2}).encode("utf-8")
    )

    snapshot = import_backtest_run(
        run_dir,
        dataset_id="demo_run",
        snapshot_id="snap-1",
        datasets_root=tmp_path / "research_datasets",
    )

    assert DataViewLoader(snapshot).summary_metrics()["sharpe"] == 1.2


def test_migrate_backtest_runs_to_datasets_compacts_source_run(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    (run_dir / "detail_api_export.json").write_text(json.dumps({"detail": ["x"] * 200}), encoding="utf-8")

    results = migrate_backtest_runs_to_datasets(
        strategies_root=tmp_path / "strategies",
        datasets_root=tmp_path / "research_datasets",
        compact_source=True,
    )

    assert len(results) == 1
    assert results[0].dataset_id == "demo_backtest_runs"
    assert results[0].snapshot_id == "run-1"
    assert set(results[0].compacted_files) == {
        "api_export.json",
        "detail_api_export.json",
        "summary_metrics.json",
        "tabs_raw/audit_log.jsonl",
        "tabs_raw/daily_returns.md",
    }
    api_pointer = json.loads((run_dir / "api_export.json").read_text(encoding="utf-8"))
    audit_pointer = json.loads((run_dir / "tabs_raw" / "audit_log.jsonl").read_text(encoding="utf-8"))
    returns_pointer = json.loads((run_dir / "tabs_raw" / "daily_returns.md").read_text(encoding="utf-8"))
    summary_pointer = json.loads((run_dir / "summary_metrics.json").read_text(encoding="utf-8"))
    assert api_pointer["kind"] == "data_center_pointer"
    assert api_pointer["dataset_file"] == "raw/api_export.json.gz"
    assert "compressed_sha256" in api_pointer
    assert audit_pointer["kind"] == "data_center_pointer"
    assert audit_pointer["dataset_file"] == "raw/audit_log.jsonl.gz"
    assert returns_pointer["dataset_file"] == "raw/daily_returns.md.gz"
    assert summary_pointer["dataset_file"] == "raw/summary_metrics.json.gz"
    assert parse_cumulative_returns_md(run_dir / "tabs_raw" / "daily_returns.md").iloc[0] == pytest.approx(0.01)
    assert load_rebalance_events(run_dir / "tabs_raw" / "audit_log.jsonl")[0]["event"] == "rebalance_signals"
    assert (tmp_path / "research_datasets" / "demo_backtest_runs" / "run-1" / "dataset.json").is_file()


def test_datasets_cli_migrates_backtest_runs(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)

    exit_code = datasets_cli.main(
        [
            "migrate-backtest-runs",
            "--strategies-root",
            str(tmp_path / "strategies"),
            "--datasets-root",
            str(tmp_path / "research_datasets"),
            "--compact-source",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "research_datasets" / "demo_backtest_runs" / "run-1" / "dataset.json").is_file()


def test_migrate_backtest_runs_regenerates_incomplete_snapshot_dir(tmp_path) -> None:
    run_dir = tmp_path / "strategies" / "demo" / "backtest_runs" / "run-1"
    _write_backtest_run(run_dir)
    partial = tmp_path / "research_datasets" / "demo_backtest_runs" / "run-1"
    (partial / "raw").mkdir(parents=True)
    (partial / "raw" / "source.json.gz").write_bytes(b"incomplete")

    results = migrate_backtest_runs_to_datasets(
        strategies_root=tmp_path / "strategies",
        datasets_root=tmp_path / "research_datasets",
    )

    assert results[0].imported is True
    assert (partial / "dataset.json").is_file()


def test_backtest_run_importer_rejects_missing_required_files_and_duplicate_snapshot(tmp_path) -> None:
    run_dir = tmp_path / "run-1"
    _write_backtest_run(run_dir)
    datasets_root = tmp_path / "research_datasets"
    import_backtest_run(run_dir, dataset_id="demo_run", snapshot_id="snap-1", datasets_root=datasets_root)
    with pytest.raises(DatasetError, match="already exists"):
        import_backtest_run(run_dir, dataset_id="demo_run", snapshot_id="snap-1", datasets_root=datasets_root)

    missing = tmp_path / "run-missing"
    _write_backtest_run(missing)
    (missing / "tabs_raw" / "audit_log.jsonl").unlink()
    with pytest.raises(DatasetError, match="audit_log"):
        import_backtest_run(missing, dataset_id="bad", datasets_root=datasets_root)


def test_funnel_promotes_only_eligible_candidates() -> None:
    frame = pd.DataFrame(
        [
            {"candidate_id": "a", "score": 3.0},
            {"candidate_id": "b", "score": 2.0},
            {"candidate_id": "c", "score": 1.0},
        ]
    )
    fast = build_fast_funnel(frame, score_column="score", top_k=2)
    assert fast.shortlist["candidate_id"].tolist() == ["a", "b"]
    reviewed = fast.shortlist.assign(
        eligible_for_cloud=[True, False],
        refinement_score=[1.0, 2.0],
    )
    full = promote_full_funnel(reviewed, cloud_top_k=1)
    assert full.cloud_candidates["candidate_id"].tolist() == ["a"]


def test_builtin_plugins_declare_local_capabilities() -> None:
    assert BUILTIN_PLUGINS["factor_scan"].capabilities.fidelity_level == FidelityLevel.LOCAL_EXACT
    assert "weight_shape" in BUILTIN_PLUGINS["parameter_followup"].capabilities.replayable_params
    assert "paired_bootstrap" in BUILTIN_PLUGINS["robustness_check"].capabilities.local_capabilities
    assert "exact_domain_scan" in BUILTIN_PLUGINS["portfolio_volatility"].capabilities.local_capabilities


def test_workflow_templates_validate_required_fields(tmp_path) -> None:
    templates = load_workflow_templates(Path("scripts/research/workflows/templates"))
    assert {template.template for template in templates} >= {
        "factor_scan",
        "parameter_followup",
        "robustness_check",
        "generic",
        "cloud_confirmation",
        "portfolio_volatility",
    }
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema_version": 1, "template": "bad"}), encoding="utf-8")
    with pytest.raises(WorkflowTemplateError, match="missing"):
        load_workflow_templates(tmp_path)


def test_research_core_toolkits_expose_metrics_robustness_and_replay_contract() -> None:
    returns = pd.Series([0.01, 0.02, -0.01], index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]))
    metrics = MetricToolkit.summary(returns)
    assert {"annual_return", "max_drawdown", "sharpe", "volatility"} <= set(metrics)
    bootstrap = RobustnessToolkit.paired_bootstrap(returns, returns + 0.001, n_boot=20, block=2)
    assert bootstrap["observed"] > 0
    replay = ReplayResult(calibrated=False, diagnostics={"reason": "test"}, tables={})
    assert replay.diagnostics["reason"] == "test"


def test_variant_registry_materializer_and_authorization_guards(tmp_path) -> None:
    strategy_root = tmp_path / "strategies" / "demo_strategy"
    strategy_root.mkdir(parents=True)
    (strategy_root / "demo_strategy.py").write_text(
        "\n".join([
            "def set_parameter(context):",
            "    g.MomentumTiltStrength = 0.50",
            "    g.ExecutionTimingMode = 'baseline'",
            "",
        ]),
        encoding="utf-8",
    )
    manifest = StrategyManifestReader(tmp_path / "strategies").ensure(strategy_root)
    assert manifest.payload["strategy"] == "demo_strategy"

    registry = VariantRegistry(strategy_root)
    record = registry.register(
        variant_id="momentum-035",
        variant_type="parameter",
        payload={"param_overrides": {"MomentumTiltStrength": 0.35}},
        description="local parameter check",
    )
    assert record["status"] == "candidate"
    assert record["owner"] == "research-platform"
    with pytest.raises(VariantError, match="already exists"):
        registry.register(variant_id="momentum-035", variant_type="parameter")
    with pytest.raises(VariantError, match="status and merge_status"):
        registry.update("momentum-035", {"status": "merge_ready"})
    with pytest.raises(VariantError, match="unknown variant update field"):
        registry.update("momentum-035", {"free_form_state": "bad"})
    updated_record = registry.update(
        "momentum-035",
        {"description": "updated", "owner": "strategy-library", "updated_by": "test"},
    )
    assert updated_record["owner"] == "strategy-library"

    out_path = StrategyMaterializer(strategy_root, output_root=tmp_path / ".local").materialize(
        "momentum-035",
        run_id="test",
    )
    assert "g.MomentumTiltStrength = 0.35" in out_path.read_text(encoding="utf-8")
    manifest_payload = json.loads((out_path.parent / "materialized.json").read_text(encoding="utf-8"))
    assert manifest_payload["uploaded_code_sha256"].startswith("sha256:")
    second_path = StrategyMaterializer(strategy_root, output_root=tmp_path / ".local").materialize(
        "momentum-035",
        run_id="test-2",
    )
    second_manifest = json.loads((second_path.parent / "materialized.json").read_text(encoding="utf-8"))
    assert second_manifest["uploaded_code_sha256"] == manifest_payload["uploaded_code_sha256"]
    (strategy_root / "demo_strategy.py").write_text(
        "\n".join([
            "def set_parameter(context):",
            "    pass",
            "",
            "def update_runtime_state():",
            "    g.MomentumTiltStrength = 0.50",
            "",
        ]),
        encoding="utf-8",
    )
    registry.register(
        variant_id="bad-location",
        variant_type="parameter",
        payload={"param_overrides": {"MomentumTiltStrength": 0.35}},
    )
    with pytest.raises(VariantError, match="outside set_parameter"):
        StrategyMaterializer(strategy_root, output_root=tmp_path / ".local").materialize("bad-location")
    with pytest.raises(VariantError, match="unsupported parameter literal type"):
        registry.register(
            variant_id="bad-param",
            variant_type="parameter",
            payload={"param_overrides": {"MomentumTiltStrength": {"bad": {1, 2}}}},
        )

    with pytest.raises(VariantError, match="code_source"):
        registry.register(variant_id="structural-a", variant_type="structural")
    with pytest.raises(VariantError, match="explicit status transitions"):
        registry.register(
            variant_id="structural-ready",
            variant_type="structural",
            status="merge_ready",
            payload={"code_source": {"type": "git", "ref": "feature/a", "path": "strategies/demo_strategy/demo_strategy.py"}},
        )
    registry.register(
        variant_id="structural-a",
        variant_type="structural",
        payload={"code_source": {"type": "git", "ref": "feature/a", "path": "strategies/demo_strategy/demo_strategy.py"}},
    )
    with pytest.raises(VariantError, match="invalid structural status transition"):
        registry.transition_status("structural-a", "merge_ready")
    with pytest.raises(GitAuthorizationError):
        registry.transition_status("structural-a", "merged_confirmed")
    with pytest.raises(GitAuthorizationError):
        StructuralBranchManager(tmp_path).create_branch(variant_id="structural-a")
    with pytest.raises(GitAuthorizationError):
        VariantMergeManager(tmp_path).apply_merge(source_ref="feature/structural-a")


def test_structural_materializer_reads_git_ref(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    strategy_root = repo / "strategies" / "demo_strategy"
    strategy_root.mkdir(parents=True)
    strategy_file = strategy_root / "demo_strategy.py"
    strategy_file.write_text("def set_parameter(context):\n    g.Mode = 'main'\n", encoding="utf-8")
    StrategyManifestReader(repo / "strategies").ensure(strategy_root)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "main")
    _git(repo, "switch", "-c", "feature/structural")
    strategy_file.write_text("def set_parameter(context):\n    g.Mode = 'feature'\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    _git(repo, "switch", "main")

    registry = VariantRegistry(strategy_root)
    registry.register(
        variant_id="structural-feature",
        variant_type="structural",
        payload={
            "code_source": {
                "type": "git",
                "ref": "feature/structural",
                "path": "strategies/demo_strategy/demo_strategy.py",
            }
        },
    )
    out_path = StrategyMaterializer(strategy_root, output_root=repo / ".local").materialize(
        "structural-feature",
        run_id="test",
    )
    assert "g.Mode = 'feature'" in out_path.read_text(encoding="utf-8")


def test_branch_plan_has_no_side_effect_and_branch_create_requires_clean_worktree(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    before_branch = _git(repo, "branch", "--show-current").strip()
    plan = StructuralBranchManager(repo).branch_plan(variant_id="structural-a", base_ref="main")
    after_branch = _git(repo, "branch", "--show-current").strip()
    assert before_branch == after_branch == "main"
    assert plan["working_tree_clean"] is True

    (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
    with pytest.raises(VariantError, match="clean"):
        StructuralBranchManager(repo).create_branch(variant_id="structural-a", base_ref="main", yes=True)
    (repo / "dirty.txt").unlink()

    created = StructuralBranchManager(repo).create_branch(variant_id="structural-a", base_ref="main", yes=True)
    assert created["executed"] is True
    assert _git(repo, "branch", "--show-current").strip() == "research/structural-a"


def test_variant_merge_apply_updates_status_after_authorized_clean_merge(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    strategy_root = repo / "strategies" / "demo_strategy"
    strategy_root.mkdir(parents=True)
    (strategy_root / "demo_strategy.py").write_text("def set_parameter(context):\n    g.Mode = 'main'\n", encoding="utf-8")
    StrategyManifestReader(repo / "strategies").ensure(strategy_root)
    registry = VariantRegistry(strategy_root)
    registry.register(
        variant_id="structural-merge",
        variant_type="structural",
        status="cloud_confirmed",
        payload={
            "code_source": {
                "type": "git",
                "ref": "feature/structural-merge",
                "path": "strategies/demo_strategy/demo_strategy.py",
            }
        },
    )
    registry.transition_status("structural-merge", "merge_ready")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature/structural-merge")
    (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "feature")
    _git(repo, "switch", "main")

    manager = VariantMergeManager(repo)
    plan = manager.merge_plan(strategy_root=strategy_root, variant_id="structural-merge", target_ref="main")
    assert plan["post_merge_status"] == "merged_pending_validation"
    assert registry.get("structural-merge")["status"] == "merge_ready"
    with pytest.raises(GitAuthorizationError):
        manager.apply_merge(strategy_root=strategy_root, variant_id="structural-merge", target_ref="main")

    result = manager.apply_merge(strategy_root=strategy_root, variant_id="structural-merge", target_ref="main", yes=True)
    assert result["status"] == "merged"
    updated = registry.get("structural-merge")
    assert updated["status"] == "merged_pending_validation"
    assert updated["merge_status"] == "merged_pending_validation"
    assert updated["code_source"]["commit"] == plan["source_sha"]


def test_variant_merge_conflict_stops_without_status_update(tmp_path) -> None:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    strategy_root = repo / "strategies" / "demo_strategy"
    strategy_root.mkdir(parents=True)
    conflict_file = repo / "conflict.txt"
    conflict_file.write_text("base\n", encoding="utf-8")
    (strategy_root / "demo_strategy.py").write_text("def set_parameter(context):\n    g.Mode = 'main'\n", encoding="utf-8")
    StrategyManifestReader(repo / "strategies").ensure(strategy_root)
    registry = VariantRegistry(strategy_root)
    registry.register(
        variant_id="structural-conflict",
        variant_type="structural",
        status="cloud_confirmed",
        payload={
            "code_source": {
                "type": "git",
                "ref": "feature/conflict",
                "path": "strategies/demo_strategy/demo_strategy.py",
            }
        },
    )
    registry.transition_status("structural-conflict", "merge_ready")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "base")
    _git(repo, "switch", "-c", "feature/conflict")
    conflict_file.write_text("feature\n", encoding="utf-8")
    _git(repo, "add", "conflict.txt")
    _git(repo, "commit", "-m", "feature")
    _git(repo, "switch", "main")
    conflict_file.write_text("main\n", encoding="utf-8")
    _git(repo, "add", "conflict.txt")
    _git(repo, "commit", "-m", "main")

    result = VariantMergeManager(repo).apply_merge(
        strategy_root=strategy_root,
        variant_id="structural-conflict",
        target_ref="main",
        yes=True,
    )
    assert result["status"] == "conflict_or_failed"
    assert result["conflict_files"] == ["conflict.txt"]
    assert registry.get("structural-conflict")["status"] == "merge_ready"


def test_docs_indexer_writes_report_catalog(tmp_path) -> None:
    docs = tmp_path / "docs"
    report_dir = tmp_path / "strategies" / "demo" / "reports" / "research" / "topic"
    docs.mkdir()
    report_dir.mkdir(parents=True)
    (docs / "guide.md").write_text("# Guide\n", encoding="utf-8")
    (report_dir / "report.md").write_text("# Research Report\n\n日期：2026-05-19\ntags: alpha, beta\n", encoding="utf-8")

    payload = DocsIndexer(tmp_path).write()
    assert payload["count"] == 2
    registry = ReportRegistry(tmp_path)
    rows = registry.find_by_strategy("demo")
    assert [row["path"] for row in rows] == ["strategies/demo/reports/research/topic/report.md"]
    assert rows[0]["date"] == "2026-05-19"
    assert rows[0]["tags"] == ["alpha", "beta"]
    assert (tmp_path / "docs" / "indexes" / "docs_catalog.json").is_file()
    assert (tmp_path / "docs" / "indexes" / "reports_catalog.json").is_file()
    assert (tmp_path / "docs" / "indexes" / "datasets_catalog.json").is_file()
    assert (tmp_path / "docs" / "indexes" / "variants_catalog.json").is_file()


def test_docs_indexer_identifies_stale_report_entries(tmp_path) -> None:
    report_dir = tmp_path / "strategies" / "demo" / "reports" / "research" / "topic"
    report_dir.mkdir(parents=True)
    report = report_dir / "report.md"
    report.write_text("# Research Report\n", encoding="utf-8")
    indexer = DocsIndexer(tmp_path)
    indexer.write()
    report.unlink()
    assert indexer.stale_entries() == ["strategies/demo/reports/research/topic/report.md"]


def test_evidence_linker_requires_existing_paths(tmp_path) -> None:
    evidence = tmp_path / "tables" / "result.csv"
    evidence.parent.mkdir()
    evidence.write_text("x\n", encoding="utf-8")
    block = EvidenceLinker(tmp_path).render_block({"结果": "tables/result.csv"})
    assert "<!-- pathref: repo/tables/result.csv -->" in block
    with pytest.raises(FileNotFoundError):
        EvidenceLinker(tmp_path).render_block({"缺失": "tables/missing.csv"})


def test_validate_baseline_exports_reports_missing_fields() -> None:
    missing = validate_baseline_exports({"daily_returns": []})
    assert "signals" in missing
    assert "daily_returns" not in missing


def test_parameter_followup_uses_strategy_adapter(tmp_path, monkeypatch) -> None:
    class DummyAdapter(ParameterReplayAdapter):
        name = "dummy"

        def build_feature_spec(self, project):
            return {"version": 1}

        def dataset_fingerprint(self, project):
            return "sha256:dummy"

        def build_features(self, project):
            return {}

        def variants(self, project):
            return [{"label": "v1", "strength": 0.1}, {"label": "v2", "strength": 0.2}]

        def score_fast(self, features, variant):
            return {
                "candidate_id": variant["label"],
                "variant": variant["label"],
                "strength": variant["strength"],
                "shape": "linear",
                "fast_score": variant["strength"],
            }

        def review_full(self, features, candidate):
            return {
                **candidate,
                "eligible_for_cloud": candidate["candidate_id"] == "v2",
                "promotion_reasons": "passed_local_gates" if candidate["candidate_id"] == "v2" else "weaker",
                "refinement_score": candidate["fast_score"],
            }

    monkeypatch.setitem(PARAMETER_REPLAY_ADAPTERS, "dummy", DummyAdapter())
    project_dir = tmp_path / "parameter"
    create_project(
        project_dir=project_dir,
        strategy="etf_factor_rotation",
        project="parameter",
        template="parameter_followup",
        extra_inputs={"adapter": "dummy"},
    )
    project_config = load_project(project_dir)
    assert project_config["owner"] == "research-platform"
    assert project_config["lifecycle"] == "active"
    monkeypatch.chdir(tmp_path)
    fast = run_project(project_dir=project_dir, run_id="fast-1", mode="fast", top_k=2, cloud_top_k=1)
    assert fast["manifest"]["mode"] == "fast"
    full = promote_run(
        project_dir=project_dir,
        fast_run_id="fast-1",
        full_run_id="full-1",
        top_k=2,
        cloud_top_k=1,
    )
    assert full["manifest"]["mode"] == "full"
    cloud = pd.read_csv(project_dir / "runs" / "full-1" / "tables" / "cloud_candidates.csv")
    assert cloud["candidate_id"].tolist() == ["v2"]


def test_factor_scan_fast_and_full_runs(tmp_path, monkeypatch) -> None:
    raw = tmp_path / "prices.json"
    _write_price_bundle(raw)
    project_dir = tmp_path / "factor_scan"
    create_project(
        project_dir=project_dir,
        strategy="etf_factor_rotation",
        project="demo",
        template="factor_scan",
        raw_data=str(raw),
    )
    monkeypatch.chdir(tmp_path)
    fast = run_project(
        project_dir=project_dir,
        run_id="fast-1",
        mode="fast",
        top_k=5,
        cloud_top_k=2,
    )
    assert fast["manifest"]["mode"] == "fast"
    assert (project_dir / "runs" / "fast-1" / "tables" / "shortlist.csv").exists()
    assert (project_dir / "runs" / "fast-1" / "tables" / "benchmark.json").exists()

    full = promote_run(
        project_dir=project_dir,
        fast_run_id="fast-1",
        full_run_id="full-1",
        top_k=3,
        cloud_top_k=2,
    )
    assert full["manifest"]["mode"] == "full"
    assert (project_dir / "runs" / "full-1" / "tables" / "cloud_candidates.csv").exists()

    warm = run_project(
        project_dir=project_dir,
        run_id="fast-2",
        mode="fast",
        top_k=5,
        cloud_top_k=2,
    )
    assert warm["manifest"]["feature_cache"]["cache_hit"] is True
    resumed = resume_run(project_dir=project_dir, run_id="fast-2")
    assert resumed["manifest"]["run_id"] == "fast-2"


def test_robustness_check_fast_and_full_runs(tmp_path, monkeypatch) -> None:
    baseline = tmp_path / "baseline.md"
    variant = tmp_path / "variant.md"
    baseline_curve = np.linspace(0.0, 0.10, 320).tolist()
    variant_curve = np.linspace(0.0, 0.14, 320).tolist()
    _write_daily_returns(baseline, baseline_curve)
    _write_daily_returns(variant, variant_curve)
    project_dir = tmp_path / "robustness"
    create_project(
        project_dir=project_dir,
        strategy="etf_factor_rotation",
        project="robustness",
        template="robustness_check",
        extra_inputs={
            "baseline_returns": str(baseline),
            "variants": [{"label": "variant-a", "returns": str(variant)}],
        },
    )
    monkeypatch.chdir(tmp_path)
    fast = run_project(project_dir=project_dir, run_id="fast-1", mode="fast", top_k=1, cloud_top_k=1)
    assert fast["manifest"]["mode"] == "fast"
    full = promote_run(
        project_dir=project_dir,
        fast_run_id="fast-1",
        full_run_id="full-1",
        top_k=1,
        cloud_top_k=1,
    )
    assert full["manifest"]["mode"] == "full"
    review = pd.read_csv(project_dir / "runs" / "full-1" / "tables" / "full_candidate_review.csv")
    assert review["candidate_id"].tolist() == ["variant-a"]


def test_batch_executor_collects_rows_and_failures() -> None:
    result = execute_batch(
        [1, 2, 3],
        lambda value: {"value": value} if value != 2 else (_ for _ in ()).throw(ValueError("boom")),
    )
    assert result.item_count == 3
    assert [row["value"] for row in result.rows] == [1, 3]
    assert result.errors[0]["error_type"] == "ValueError"


def test_coverage_audit_flags_missing_intervals() -> None:
    complete = audit_scan_coverage(
        [
            ScanCoverageSlice(
                slice_id="20",
                lower_bound=0.0,
                upper_bound=0.2,
                breakpoints=(0.0, 0.1, 0.2),
                interval_points=(0.05, 0.15),
            )
        ]
    )
    missing = audit_scan_coverage(
        [
            ScanCoverageSlice(
                slice_id="20",
                lower_bound=0.0,
                upper_bound=0.2,
                breakpoints=(0.0, 0.1, 0.2),
                interval_points=(0.05,),
            )
        ]
    )
    assert coverage_is_complete(complete) is True
    assert coverage_is_complete(missing) is False


def test_smoke_benchmark_projects_warm_runtime() -> None:
    summary = run_smoke_benchmark(
        [1, 2, 3],
        lambda value: {"value": value},
        full_item_count=6,
        target_seconds=10.0,
    )
    assert summary.sample_size == 3
    assert summary.full_item_count == 6
    assert summary.predicted_full_seconds >= 0
    assert summary.passed is True


def test_portfolio_volatility_promotion_requires_warm_smoke(tmp_path) -> None:
    project_dir = tmp_path / "portfolio"
    fast_dir = project_dir / "runs" / "fast-1" / "tables"
    fast_dir.mkdir(parents=True)
    shortlist = pd.DataFrame([{"candidate_id": "portfolio-volatility-full-scan"}])
    plugin = PortfolioVolatilityPlugin()

    (fast_dir / "smoke_summary.json").write_text(
        json.dumps(
            {
                "coverage_complete": True,
                "feature_cache_hit": False,
                "smoke_passed": False,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="feature_cache_not_warm"):
        plugin.validate_promotion(project_dir=project_dir, fast_run_id="fast-1", shortlist=shortlist)

    (fast_dir / "smoke_summary.json").write_text(
        json.dumps(
            {
                "coverage_complete": True,
                "feature_cache_hit": True,
                "smoke_passed": True,
            }
        ),
        encoding="utf-8",
    )
    plugin.validate_promotion(project_dir=project_dir, fast_run_id="fast-1", shortlist=shortlist)
