from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from scripts.research.momentum_tilt_research.analysis import (
    build_phase2_scan,
    build_response_curve,
    build_response_samples,
    build_zone_summary,
    evaluate_phase1_gate,
    evaluate_phase2_gate,
)
from scripts.research.momentum_tilt_research.cli import _cmd_ab_plan
from scripts.research.momentum_tilt_research.replay import (
    VariantSpec,
    event_weight_frame,
    replay_variant,
)
from scripts.research.research_core.prices import PriceFrames


ETF_CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")


def _synthetic_frames() -> PriceFrames:
    calendar = pd.bdate_range("2021-01-01", periods=120)
    close = pd.DataFrame(
        {
            ETF_CODES[0]: np.linspace(1.0, 1.4, len(calendar)),
            ETF_CODES[1]: np.linspace(1.0, 1.2, len(calendar)),
            ETF_CODES[2]: np.linspace(1.0, 1.1, len(calendar)),
        },
        index=calendar,
    )
    return PriceFrames(close=close, high=close, low=close, money=close, calendar=calendar)


def _event(signal_date: str, previous_date: str, scores: list[float]) -> dict:
    return {
        "current_dt": f"{signal_date}T09:30:00",
        "previous_date": previous_date,
        "pool": list(ETF_CODES),
        "trend_gates": [1.0, 1.0, 1.0],
        "rp_weights": [1 / 3, 1 / 3, 1 / 3],
        "momentum_scores": scores,
        "momentum_tilts": [1.0, 1.0, 1.0],
        "rsrs_tilts": [1.0, 1.0, 1.0],
        "crowd_penalties": [1.0, 1.0, 1.0],
        "portfolio_vol_scale": 1.0,
        "final_weights": [1 / 3, 1 / 3, 1 / 3],
        "params": {
            "MomentumTiltMin": 0.7,
            "MomentumTiltMax": 1.3,
            "MaxWeight": 0.6,
            "MinWeight": 0.05,
            "MaxTotalWeight": 1.0,
        },
    }


def _synthetic_events() -> list[dict]:
    return [
        _event("2021-01-04", "2021-01-01", [0.6, 0.95, 0.2]),
        _event("2021-01-11", "2021-01-08", [0.7, 0.9, 0.3]),
        _event("2021-01-18", "2021-01-15", [0.55, 0.92, 0.4]),
    ]


def test_response_curve_and_gate_build() -> None:
    frames = _synthetic_frames()
    samples = build_response_samples(_synthetic_events(), frames)
    curve = build_response_curve(samples)
    zone_summary = build_zone_summary(samples)
    assert not samples.empty
    assert not curve.empty
    assert {"mid", "high"}.issubset(set(zone_summary["score_zone"]))
    gate = evaluate_phase1_gate(zone_summary)
    assert "passed" in gate


def test_replay_variant_changes_weights_and_returns() -> None:
    frames = _synthetic_frames()
    baseline_returns = pd.Series(0.001, index=frames.calendar[1:40])
    result = replay_variant(
        _synthetic_events(),
        frames.close,
        baseline_returns,
        VariantSpec(label="linear-025", strength=0.25),
    )
    assert result.spec.label == "linear-025"
    assert not result.weights.empty
    assert len(result.returns) == len(baseline_returns)
    assert event_weight_frame(_synthetic_events(), VariantSpec(label="linear-050", strength=0.50)).shape[0] == 3


def test_phase2_scan_blocks_metrics_without_calibration() -> None:
    frames = _synthetic_frames()
    baseline_returns = pd.Series(0.001, index=frames.calendar[1:40])
    scan, results = build_phase2_scan(
        _synthetic_events(),
        frames,
        baseline_returns,
        calibration={
            "passed": False,
            "baseline_local_raw": {
                "annual_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
            },
            "baseline_cloud": {
                "annual_return": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
            },
        },
    )
    assert results == []
    assert set(scan["metrics_status"]) == {"blocked_replay_not_calibrated"}
    gate = evaluate_phase2_gate(scan)
    assert gate["passed"] is False


def test_ab_plan_writes_manifest_and_config(tmp_path) -> None:
    decision = tmp_path / "decision.json"
    decision.write_text('{"ab_ready": true}', encoding="utf-8")

    class Args:
        local_decision = str(decision)
        batch_id = "batch-a"
        output_dir = str(tmp_path / "batch")
        created = "2026-05-17T00:00:00"

    assert _cmd_ab_plan(Args()) == 0
    assert (tmp_path / "batch" / "manifest.json").exists()
    assert (tmp_path / "batch" / "abtests" / "momentum-strength-confirmation.json").exists()
