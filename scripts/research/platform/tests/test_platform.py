from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research.platform.contracts import FidelityLevel, validate_baseline_exports
from scripts.research.platform.batch_executor import execute_batch
from scripts.research.platform.benchmark_runner import run_smoke_benchmark
from scripts.research.platform.coverage_audit import (
    ScanCoverageSlice,
    audit_scan_coverage,
    coverage_is_complete,
)
from scripts.research.platform.datasets import import_joinquant_price_json, load_price_frames
from scripts.research.platform.engine import create_project, promote_run, resume_run, run_project
from scripts.research.platform.features import FeatureStore
from scripts.research.platform.funnel import build_fast_funnel, promote_full_funnel
from scripts.research.platform.plugins import (
    BUILTIN_PLUGINS,
    PARAMETER_REPLAY_ADAPTERS,
    ParameterReplayAdapter,
    PortfolioVolatilityPlugin,
)
from scripts.research.etf_window_research.spec import ETF_CODES


def _write_price_bundle(path: Path) -> None:
    dates = pd.bdate_range("2018-01-01", periods=800)
    payload = {
        "metadata": {"fields": ["close", "high", "low", "money"]},
        "calendar": [day.date().isoformat() for day in dates],
        "prices": {},
    }
    for idx, code in enumerate(ETF_CODES):
        close = np.linspace(1.0 + idx, 2.0 + idx, len(dates))
        payload["prices"][code] = [
            {
                "date": day.date().isoformat(),
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
    assert not frames.close.empty


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
