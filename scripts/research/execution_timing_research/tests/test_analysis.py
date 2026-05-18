from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.research.execution_timing_research.analysis import (
    _joinquant_pct_change,
    build_delay_only_weekly,
    build_signal_shift_weekly,
    compute_signal_snapshot,
    has_open_prices,
)
from scripts.research.research_core.prices import PriceFrames


ETF_CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")


def _params() -> dict:
    return {
        "MA_long": 3,
        "MA_long_by_etf": [3, 3, 3],
        "MomShort": 1,
        "MomMid": 2,
        "MomLong": 3,
        "w20": 0.2,
        "w60": 0.3,
        "w120": 0.5,
        "VolWindow": 3,
        "annual_factor": 252,
        "RSRS_N": 2,
        "RSRS_M": 3,
        "RSRS_NegativeFullCut": 1.8,
        "MomentumTiltStrength": 0.5,
        "MomentumTiltMin": 0.7,
        "MomentumTiltMax": 1.3,
        "MomentumExtremeScoreStart": None,
        "MomentumExtremeTiltCap": 1.0,
        "RSRSTiltMin": 0.7,
        "RSRSTiltMax": 1.3,
        "CrowdWindow": 4,
        "CrowdRetShort": 1,
        "CrowdRetMid": 2,
        "AmountMAWindow": 2,
        "DeviationMAWindow": 2,
        "CrowdVolWindow": 2,
        "CrowdStart": 0.6,
        "CrowdEnd": 0.95,
        "MinCrowdPenalty": 0.3,
        "CrowdStart_by_etf": None,
        "CrowdEnd_by_etf": None,
        "MinCrowdPenalty_by_etf": None,
        "CrowdRetShort_by_etf": None,
        "CrowdRetMid_by_etf": None,
        "PortfolioVolWindow": 3,
        "TargetVol": 0.08,
        "MaxPortfolioVolScale": 1.0,
        "MaxWeight": 0.6,
        "MinWeight": 0.05,
        "MaxTotalWeight": 1.0,
    }


def _frames() -> PriceFrames:
    calendar = pd.bdate_range("2026-01-01", periods=10)
    close = pd.DataFrame(
        {
            ETF_CODES[0]: np.linspace(1.0, 1.18, len(calendar)),
            ETF_CODES[1]: np.linspace(1.0, 1.09, len(calendar)),
            ETF_CODES[2]: np.linspace(1.0, 1.05, len(calendar)),
        },
        index=calendar,
    )
    open_ = close * 0.995
    return PriceFrames(
        open=open_,
        close=close,
        high=close * 1.01,
        low=close * 0.99,
        money=close * 1000,
        calendar=calendar,
    )


def _event(frames: PriceFrames) -> dict:
    previous_date = frames.calendar[5]
    signal_date = frames.calendar[6]
    snapshot = compute_signal_snapshot(frames, _params(), previous_date)
    return {
        "current_dt": f"{signal_date.date().isoformat()}T09:30:00",
        "previous_date": previous_date.date().isoformat(),
        "final_weights": snapshot.final_weights.tolist(),
        "params": _params(),
    }


def test_signal_shift_builds_weekly_rows() -> None:
    frames = _frames()
    weekly = build_signal_shift_weekly([_event(frames)], frames)
    assert len(weekly) == 1
    assert weekly["baseline_recompute_final_weight_max_abs_error"].iloc[0] < 1e-12
    assert "target_weight_l1_distance" in weekly.columns


def test_delay_only_uses_open_prices() -> None:
    frames = _frames()
    weekly = build_delay_only_weekly([_event(frames)], frames)
    assert has_open_prices(frames) is True
    assert len(weekly) == 1
    assert "delay_minus_baseline_return" in weekly.columns


def test_joinquant_pct_change_preserves_gap_bridge_return() -> None:
    frame = pd.DataFrame({"AAA": [5.0, np.nan, 1.0]})
    returns = _joinquant_pct_change(frame)
    assert returns.iloc[1, 0] == 0.0
    assert returns.iloc[2, 0] == -0.8
