from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

import scripts.research.etf_window_research.analysis as analysis_module
from scripts.research.etf_window_research.analysis import (
    PriceFrames,
    build_best_window_summary,
    build_factor_window_grid,
    build_pooled_vs_etf_specific,
    build_research_cache,
    first_trading_days_by_week,
    write_project_run_outputs,
)
from scripts.research.etf_window_research.fetch_remote_data import fetch_remote_price_bundle
from scripts.research.etf_window_research.layout import ResearchProjectLayout
from scripts.research.etf_window_research.research_export import build_joinquant_research_export_script
from scripts.research.etf_window_research.spec import ETF_CODES, window_band


def _synthetic_frames() -> PriceFrames:
    dates = pd.bdate_range("2018-01-01", periods=1800)
    base = np.linspace(1.0, 3.0, len(dates))
    close = pd.DataFrame(
        {
            ETF_CODES[0]: base * (1 + 0.02 * np.sin(np.arange(len(dates)) / 5)),
            ETF_CODES[1]: base * (1 + 0.03 * np.sin(np.arange(len(dates)) / 17)),
            ETF_CODES[2]: base * (1 + 0.01 * np.sin(np.arange(len(dates)) / 31)),
        },
        index=dates,
    )
    money = pd.DataFrame(
        {
            code: 1_000_000 + 10_000 * np.cos(np.arange(len(dates)) / (idx + 3))
            for idx, code in enumerate(ETF_CODES)
        },
        index=dates,
    )
    return PriceFrames(close=close, high=close * 1.01, low=close * 0.99, money=money, calendar=dates)


def test_window_band_classification() -> None:
    assert window_band(20) == "short"
    assert window_band(40) == "mid"
    assert window_band(120) == "long"


def test_first_trading_day_by_week_uses_one_anchor_per_week() -> None:
    dates = pd.bdate_range("2026-01-01", "2026-01-31")
    anchors = first_trading_days_by_week(dates, date(2026, 1, 1), date(2026, 1, 31))
    assert len(anchors) == len(set(anchors.to_period("W-SUN")))
    assert anchors[0] == pd.Timestamp("2026-01-01")


def test_window_grid_and_summaries_build_on_synthetic_data(monkeypatch) -> None:
    monkeypatch.setattr(analysis_module, "BOOTSTRAP_REPS", 8)
    frames = _synthetic_frames()
    cache = build_research_cache(frames)
    grid = build_factor_window_grid(frames, cache=cache)
    best = build_best_window_summary(grid)
    pooled = build_pooled_vs_etf_specific(grid)

    assert not grid.empty
    assert set(grid["horizon"]) == {5, 10, 20, 40}
    assert grid.loc[grid["horizon"] == 5, "std_error"].notna().any()
    assert grid.loc[grid["horizon"] != 5, "std_error"].isna().all()
    assert {"trend_gate", "momentum_return", "crowd_amount"}.issubset(set(grid["factor"]))
    assert not best.empty
    assert not pooled.empty
    assert {"best_window", "stable_windows_1se"}.issubset(best.columns)
    assert {"shared_window", "specific_windows"}.issubset(pooled.columns)


def test_research_export_script_contains_required_fields() -> None:
    script = build_joinquant_research_export_script()
    for token in ["159819.XSHE", "513100.XSHG", "518880.XSHG", '"close"', '"money"', "write_file"]:
        assert token in script


def test_remote_fetch_entrypoint_is_importable() -> None:
    assert callable(fetch_remote_price_bundle)


def test_project_run_layout_separates_reports_tables_and_curves(tmp_path) -> None:
    frames = _synthetic_frames()
    project = ResearchProjectLayout.from_path(tmp_path / "window_heterogeneity")
    run = project.run("2026-05-15-baseline")

    grid = pd.DataFrame(
        [
            {
                "family": "trend",
                "factor": "trend_gate",
                "etf": ETF_CODES[0],
                "etf_label": "AI_ETF",
                "window": 20,
                "window_band": "short",
                "horizon": 5,
                "sample_count": 10,
                "benefit": 0.01,
                "state_a_mean": 0.02,
                "state_b_mean": 0.01,
                "state_a_count": 5,
                "state_b_count": 5,
                "secondary_metric": 0.1,
                "ci_low": 0.0,
                "ci_high": 0.02,
                "std_error": 0.005,
            }
        ]
    )
    best = pd.DataFrame(
        [
            {
                "factor": "trend_gate",
                "family": "trend",
                "etf": ETF_CODES[0],
                "etf_label": "AI_ETF",
                "best_window": 20,
                "best_band": "short",
                "best_benefit": 0.01,
                "best_ci_low": 0.0,
                "best_ci_high": 0.02,
                "stable_windows_1se": "20",
            }
        ]
    )
    pooled = pd.DataFrame(
        [
            {
                "factor": "trend_gate",
                "family": "trend",
                "shared_window": 20,
                "shared_mean_benefit": 0.01,
                "etf_specific_mean_benefit": 0.01,
                "specific_minus_shared": 0.0,
                "specific_windows": "AI_ETF:20",
            }
        ]
    )
    holdout = pd.DataFrame(
        [
            {
                "factor": "trend_gate",
                "family": "trend",
                "etf": ETF_CODES[0],
                "etf_label": "AI_ETF",
                "discovery_best_window": 20,
                "discovery_best_band": "short",
                "discovery_benefit": 0.01,
                "holdout_benefit": 0.005,
                "holdout_nonnegative": True,
            }
        ]
    )
    segments = best.assign(segment="segment_2021_2022")
    bootstrap = grid[
        [
            "family",
            "factor",
            "etf",
            "etf_label",
            "window",
            "benefit",
            "ci_low",
            "ci_high",
            "std_error",
            "sample_count",
        ]
    ].copy()

    raw_path = project.raw_price_bundle_path()
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text("{}", encoding="utf-8")

    write_project_run_outputs(
        run,
        frames=frames,
        grid=grid,
        best=best,
        pooled=pooled,
        holdout=holdout,
        segments=segments,
        bootstrap=bootstrap,
        raw_data_path=raw_path,
    )

    assert (run.reports_dir / "data_integrity.md").exists()
    assert (run.tables_dir / "factor_window_grid.csv").exists()
    assert (run.curves_dir / "trend_gate.csv").exists()
    assert run.manifest_path.exists()
