"""Local analysis workflow for execution-timing impact research."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from scripts.research.etf_window_research.spec import SCORE_END
from scripts.research.research_core.audit import load_rebalance_events
from scripts.research.research_core.layout import ResearchProjectLayout, ResearchRunLayout
from scripts.research.research_core.metrics import (
    paired_block_bootstrap,
    performance_metrics,
    rolling_sharpe,
    yearly_metrics,
)
from scripts.research.research_core.prices import PriceFrames, load_price_bundle
from scripts.research.research_core.reporting import markdown_table, write_json


STRATEGY = "etf_factor_rotation"
ETF_CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")
WEIGHT_TOL = 1e-8
CALIBRATION_TOL = 1e-6


@dataclass(frozen=True)
class SignalSnapshot:
    """One locally recomputed signal state at a specific as-of date."""

    asof_date: pd.Timestamp
    trend_gates: np.ndarray
    rp_weights: np.ndarray
    momentum_scores: np.ndarray
    momentum_tilts: np.ndarray
    rsrs_tilts: np.ndarray
    tilted_weights: np.ndarray
    crowd_penalties: np.ndarray
    raw_weights: np.ndarray
    portfolio_vol_scale: float
    final_weights: np.ndarray


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_project_dir() -> Path:
    return _repo_root() / "strategies" / STRATEGY / "reports" / "research" / "execution_timing"


def default_raw_price_path() -> Path:
    return (
        _repo_root()
        / "strategies"
        / STRATEGY
        / "reports"
        / "research"
        / "execution_timing"
        / "inputs"
        / "raw"
        / "execution_timing_prices.json"
    )


def default_audit_log_path() -> Path:
    return (
        _repo_root()
        / "strategies"
        / STRATEGY
        / "backtest_runs"
        / "20260517-1724-bt580e16e5a3f1bf99d197cea88889da1a"
        / "tabs_raw"
        / "audit_log.jsonl"
    )


def _slice_prices(frames: PriceFrames, asof_date: pd.Timestamp) -> dict[str, pd.DataFrame]:
    close = frames.close.loc[:asof_date, list(ETF_CODES)]
    high = frames.high.loc[:asof_date, list(ETF_CODES)]
    low = frames.low.loc[:asof_date, list(ETF_CODES)]
    amount = frames.money.loc[:asof_date, list(ETF_CODES)]
    return {
        "close": close,
        "high": high,
        "low": low,
        "amount": amount,
        "close_ret": _joinquant_pct_change(close),
    }


def _joinquant_pct_change(frame: pd.DataFrame) -> pd.DataFrame:
    """Mirror JoinQuant's legacy `pct_change()` behavior on missing rows."""

    return frame.ffill().pct_change(fill_method=None)


def _resolve_ma_long_windows(params: dict) -> list[int]:
    values = params.get("MA_long_by_etf")
    return list(values) if values is not None else [int(params["MA_long"])] * len(ETF_CODES)


def _resolve_crowd_thresholds(params: dict) -> list[tuple[float, float, float]]:
    n = len(ETF_CODES)
    starts = list(params["CrowdStart_by_etf"]) if params.get("CrowdStart_by_etf") is not None else [params["CrowdStart"]] * n
    ends = list(params["CrowdEnd_by_etf"]) if params.get("CrowdEnd_by_etf") is not None else [params["CrowdEnd"]] * n
    mins = (
        list(params["MinCrowdPenalty_by_etf"])
        if params.get("MinCrowdPenalty_by_etf") is not None
        else [params["MinCrowdPenalty"]] * n
    )
    return [(float(start), float(end), float(minimum)) for start, end, minimum in zip(starts, ends, mins, strict=True)]


def _resolve_crowd_ret_windows(params: dict) -> list[tuple[int, int]]:
    n = len(ETF_CODES)
    shorts = (
        list(params["CrowdRetShort_by_etf"])
        if params.get("CrowdRetShort_by_etf") is not None
        else [params["CrowdRetShort"]] * n
    )
    mids = (
        list(params["CrowdRetMid_by_etf"])
        if params.get("CrowdRetMid_by_etf") is not None
        else [params["CrowdRetMid"]] * n
    )
    return [(int(short), int(mid)) for short, mid in zip(shorts, mids, strict=True)]


def _percentile_rank(value: float, series: pd.Series) -> float:
    if len(series) == 0 or pd.isna(value):
        return 0.5
    return float((series < value).mean())


def _compute_trend_gates(prices: dict[str, pd.DataFrame], params: dict) -> np.ndarray:
    close = prices["close"]
    gates = np.zeros(len(ETF_CODES), dtype=float)
    for idx, code in enumerate(ETF_CODES):
        series = close[code].dropna()
        window = _resolve_ma_long_windows(params)[idx]
        if len(series) < window:
            continue
        gates[idx] = float(series.iloc[-1] > series.iloc[-window:].mean())
    return gates


def _compute_rp_weights(
    prices: dict[str, pd.DataFrame],
    trend_gates: np.ndarray,
    params: dict,
) -> np.ndarray:
    close_ret = prices["close_ret"]
    active = np.flatnonzero(trend_gates > 0)
    weights = np.zeros(len(ETF_CODES), dtype=float)
    if len(active) == 0:
        return weights
    vols = np.zeros(len(ETF_CODES), dtype=float)
    for idx in active:
        ret = close_ret[ETF_CODES[idx]].dropna().iloc[-int(params["VolWindow"]) :]
        vols[idx] = (
            1.0
            if len(ret) < 5
            else max(float(ret.std() * np.sqrt(params["annual_factor"])), 1e-8)
        )
    inverse = np.zeros(len(ETF_CODES), dtype=float)
    inverse[active] = np.where(vols[active] > 0, 1.0 / vols[active], 0.0)
    total = float(inverse.sum())
    return inverse / total if total > 0 else weights


def _compute_momentum_scores(
    prices: dict[str, pd.DataFrame],
    trend_gates: np.ndarray,
    params: dict,
) -> np.ndarray:
    close = prices["close"]
    scores = np.zeros(len(ETF_CODES), dtype=float)
    active = np.flatnonzero(trend_gates > 0)
    if len(active) == 0:
        return scores
    active_codes = [ETF_CODES[idx] for idx in active]
    active_close = close[active_codes]
    windows = [int(params["MomShort"]), int(params["MomMid"]), int(params["MomLong"])]
    weights = [float(params["w20"]), float(params["w60"]), float(params["w120"])]
    if len(active_close) <= max(windows):
        return scores
    for window, weight in zip(windows, weights, strict=True):
        period_ret = active_close.iloc[-1] / active_close.iloc[-(window + 1)] - 1
        ranks = period_ret.rank(pct=True).fillna(0.0)
        for idx in active:
            scores[idx] += weight * float(ranks.get(ETF_CODES[idx], 0.0))
    return scores


def _compute_momentum_tilts(
    momentum_scores: np.ndarray,
    trend_gates: np.ndarray,
    params: dict,
) -> np.ndarray:
    tilts = np.zeros(len(ETF_CODES), dtype=float)
    active = np.flatnonzero(trend_gates > 0)
    if len(active) == 0:
        return tilts
    mean_score = float(momentum_scores[active].mean())
    for idx in active:
        raw = 1.0 + float(params["MomentumTiltStrength"]) * (float(momentum_scores[idx]) - mean_score)
        tilt = float(np.clip(raw, params["MomentumTiltMin"], params["MomentumTiltMax"]))
        extreme_start = params.get("MomentumExtremeScoreStart")
        if extreme_start is not None and momentum_scores[idx] >= extreme_start:
            tilt = min(tilt, float(params["MomentumExtremeTiltCap"]))
        tilts[idx] = tilt
    return tilts


def _compute_rsrs_adjusted_scores(prices: dict[str, pd.DataFrame], params: dict) -> np.ndarray:
    high = prices["high"]
    low = prices["low"]
    n_window = int(params["RSRS_N"])
    m_window = int(params["RSRS_M"])
    scores = np.zeros(len(ETF_CODES), dtype=float)
    for idx, code in enumerate(ETF_CODES):
        h = high[code].dropna()
        l = low[code].dropna()
        common = h.index.intersection(l.index)
        h = h.loc[common]
        l = l.loc[common]
        if len(h) < m_window + n_window - 1:
            continue
        h_roll = h.rolling(n_window)
        l_roll = l.rolling(n_window)
        cov = h_roll.cov(l).dropna().to_numpy()
        var_l = l_roll.var().dropna().to_numpy()
        var_h = h_roll.var().dropna().to_numpy()
        betas = cov / var_l
        r2s = cov**2 / (var_h * var_l)
        bad = (
            (var_l < 1e-10)
            | (var_h < 1e-10)
            | (~np.isfinite(betas))
            | (~np.isfinite(r2s))
        )
        betas[bad] = 1.0
        r2s[bad] = 0.0
        if len(betas) < m_window:
            continue
        beta_tail = betas[-m_window:]
        std = float(np.std(beta_tail))
        rsrs_z = 0.0 if std < 1e-10 else float((beta_tail[-1] - np.mean(beta_tail)) / std)
        scores[idx] = rsrs_z * float(r2s[-1])
    return scores


def _compute_rsrs_tilts(
    prices: dict[str, pd.DataFrame],
    trend_gates: np.ndarray,
    params: dict,
) -> np.ndarray:
    tilts = np.zeros(len(ETF_CODES), dtype=float)
    active = np.flatnonzero(trend_gates > 0)
    if len(active) == 0:
        return tilts
    adjusted = _compute_rsrs_adjusted_scores(prices, params)
    mean_active = float(adjusted[active].mean())
    full_cut = float(params["RSRS_NegativeFullCut"])
    for idx in active:
        raw = 1.0 + (float(adjusted[idx]) - mean_active) / full_cut
        tilts[idx] = float(np.clip(raw, params["RSRSTiltMin"], params["RSRSTiltMax"]))
    return tilts


def _apply_relative_tilts(
    rp_weights: np.ndarray,
    trend_gates: np.ndarray,
    momentum_tilts: np.ndarray,
    rsrs_tilts: np.ndarray,
) -> np.ndarray:
    tilted = np.zeros(len(ETF_CODES), dtype=float)
    active = np.flatnonzero((trend_gates > 0) & (rp_weights > 0))
    if len(active) == 0:
        return tilted
    raw = rp_weights * momentum_tilts * rsrs_tilts
    total_raw = float(raw[active].sum())
    base_total = float(rp_weights[active].sum())
    if total_raw <= 0 or base_total <= 0:
        return rp_weights.copy()
    tilted[active] = raw[active] / total_raw * base_total
    return tilted


def _compute_crowd_penalties(prices: dict[str, pd.DataFrame], params: dict) -> np.ndarray:
    close = prices["close"]
    amount = prices["amount"]
    penalties = np.ones(len(ETF_CODES), dtype=float)
    crowd_window = int(params["CrowdWindow"])
    eligible = [code for code in ETF_CODES if len(close[code].dropna()) >= crowd_window]
    if not eligible:
        return penalties
    recent_close = close[eligible].iloc[-crowd_window:]
    ret_windows = _resolve_crowd_ret_windows(params)
    short_cache: dict[int, pd.DataFrame] = {}
    mid_cache: dict[int, pd.DataFrame] = {}
    for idx, code in enumerate(ETF_CODES):
        if code not in eligible:
            continue
        short_w, mid_w = ret_windows[idx]
        short_cache.setdefault(short_w, recent_close / recent_close.shift(short_w) - 1)
        mid_cache.setdefault(mid_w, recent_close / recent_close.shift(mid_w) - 1)
    amount_cols = [code for code in eligible if code in amount.columns]
    amt_ma = None
    if amount_cols:
        aligned = amount[amount_cols].loc[amount.index.intersection(recent_close.index)]
        if len(aligned) >= int(params["AmountMAWindow"]):
            amt_ma = aligned.rolling(int(params["AmountMAWindow"])).mean()
    deviation = recent_close / recent_close.rolling(int(params["DeviationMAWindow"])).mean() - 1
    volatility = _joinquant_pct_change(recent_close).rolling(int(params["CrowdVolWindow"])).std() * np.sqrt(
        float(params["annual_factor"])
    )
    thresholds = _resolve_crowd_thresholds(params)
    for idx, code in enumerate(ETF_CODES):
        if code not in eligible:
            continue
        short_w, mid_w = ret_windows[idx]
        col_short = short_cache[short_w][code].dropna()
        col_mid = mid_cache[mid_w][code].dropna()
        col_dev = deviation[code].dropna()
        col_vol = volatility[code].dropna()
        indicators = [
            _percentile_rank(float(col_short.iloc[-1]), col_short) if len(col_short) > 1 else 0.5,
            _percentile_rank(float(col_mid.iloc[-1]), col_mid) if len(col_mid) > 1 else 0.5,
            (
                _percentile_rank(float(amt_ma[code].dropna().iloc[-1]), amt_ma[code].dropna())
                if amt_ma is not None and code in amt_ma.columns and len(amt_ma[code].dropna()) > 1
                else 0.5
            ),
            _percentile_rank(float(col_dev.iloc[-1]), col_dev) if len(col_dev) > 1 else 0.5,
            _percentile_rank(float(col_vol.iloc[-1]), col_vol) if len(col_vol) > 1 else 0.5,
        ]
        score = float(np.mean(indicators))
        start, end, minimum = thresholds[idx]
        if score <= start:
            penalty = 1.0
        elif score >= end:
            penalty = minimum
        else:
            penalty = 1.0 - (score - start) / (end - start) * (1.0 - minimum)
            penalty = max(minimum, min(1.0, penalty))
        penalties[idx] = float(penalty)
    return penalties


def _compute_portfolio_vol_scale(
    prices: dict[str, pd.DataFrame],
    raw_weights: np.ndarray,
    params: dict,
) -> float:
    active = np.flatnonzero(raw_weights > 1e-8)
    if len(active) == 0:
        return 1.0
    returns = []
    window = int(params["PortfolioVolWindow"])
    for idx in active:
        series = prices["close_ret"][ETF_CODES[idx]].dropna().iloc[-window:]
        if len(series) < window:
            return 1.0
        returns.append(series.to_numpy())
    matrix = np.column_stack(returns)
    cov_annual = np.atleast_2d(np.cov(matrix, rowvar=False)) * float(params["annual_factor"])
    active_weights = raw_weights[active]
    portfolio_vol = float(np.sqrt(max(active_weights @ cov_annual @ active_weights, 0.0)))
    if portfolio_vol <= float(params["TargetVol"]) or portfolio_vol < 1e-8:
        return 1.0
    return min(float(params["TargetVol"]) / portfolio_vol, float(params["MaxPortfolioVolScale"]))


def _apply_weight_constraints(weights: np.ndarray, params: dict) -> np.ndarray:
    result = weights.copy()
    result[result > float(params["MaxWeight"])] = float(params["MaxWeight"])
    result[result < float(params["MinWeight"])] = 0.0
    total = float(result.sum())
    if total > float(params["MaxTotalWeight"]):
        result = result * float(params["MaxTotalWeight"]) / total
    return result


def compute_signal_snapshot(frames: PriceFrames, params: dict, asof_date: pd.Timestamp) -> SignalSnapshot:
    """Recompute one local signal state using the strategy's pure logic."""

    prices = _slice_prices(frames, asof_date)
    trend_gates = _compute_trend_gates(prices, params)
    rp_weights = _compute_rp_weights(prices, trend_gates, params)
    momentum_scores = _compute_momentum_scores(prices, trend_gates, params)
    momentum_tilts = _compute_momentum_tilts(momentum_scores, trend_gates, params)
    rsrs_tilts = _compute_rsrs_tilts(prices, trend_gates, params)
    tilted_weights = _apply_relative_tilts(rp_weights, trend_gates, momentum_tilts, rsrs_tilts)
    crowd_penalties = _compute_crowd_penalties(prices, params)
    raw_weights = tilted_weights * trend_gates * crowd_penalties
    portfolio_vol_scale = _compute_portfolio_vol_scale(prices, raw_weights, params)
    final_weights = _apply_weight_constraints(raw_weights * portfolio_vol_scale, params)
    return SignalSnapshot(
        asof_date=pd.Timestamp(asof_date).normalize(),
        trend_gates=trend_gates,
        rp_weights=rp_weights,
        momentum_scores=momentum_scores,
        momentum_tilts=momentum_tilts,
        rsrs_tilts=rsrs_tilts,
        tilted_weights=tilted_weights,
        crowd_penalties=crowd_penalties,
        raw_weights=raw_weights,
        portfolio_vol_scale=portfolio_vol_scale,
        final_weights=final_weights,
    )


def _weight_state(weights: np.ndarray) -> str:
    total = float(weights.sum())
    if total <= WEIGHT_TOL:
        return "all_cash"
    if total < 1.0 - WEIGHT_TOL:
        return "partial_invested"
    return "full_invested"


def _topk_order(snapshot: SignalSnapshot) -> str:
    active = [
        (ETF_CODES[idx], float(snapshot.momentum_scores[idx]))
        for idx in range(len(ETF_CODES))
        if snapshot.trend_gates[idx] > 0
    ]
    ordered = sorted(active, key=lambda item: (-item[1], item[0]))
    return ">".join(code for code, _ in ordered)


def build_signal_shift_weekly(events: list[dict], frames: PriceFrames) -> pd.DataFrame:
    """Compare logged baseline weights with Monday-close refreshed weights."""

    rows = []
    for event in events:
        signal_date = pd.Timestamp(event["current_dt"]).normalize()
        baseline_asof = pd.Timestamp(event["previous_date"]).normalize()
        params = dict(event["params"])
        baseline = compute_signal_snapshot(frames, params, baseline_asof)
        refreshed = compute_signal_snapshot(frames, params, signal_date)
        logged_weights = np.asarray(event["final_weights"], dtype=float)
        refreshed_weights = refreshed.final_weights
        row = {
            "signal_date": signal_date,
            "baseline_asof_date": baseline_asof,
            "refreshed_asof_date": signal_date,
            "baseline_recompute_final_weight_max_abs_error": float(
                np.max(np.abs(baseline.final_weights - logged_weights))
            ),
            "trend_gate_changed": bool(np.max(np.abs(refreshed.trend_gates - baseline.trend_gates)) > WEIGHT_TOL),
            "momentum_score_changed": bool(
                np.max(np.abs(refreshed.momentum_scores - baseline.momentum_scores)) > WEIGHT_TOL
            ),
            "crowd_penalty_changed": bool(
                np.max(np.abs(refreshed.crowd_penalties - baseline.crowd_penalties)) > WEIGHT_TOL
            ),
            "portfolio_vol_scale_changed": bool(
                abs(refreshed.portfolio_vol_scale - baseline.portfolio_vol_scale) > WEIGHT_TOL
            ),
            "target_weight_l1_distance": float(np.abs(refreshed_weights - logged_weights).sum()),
            "any_target_weight_changed": bool(np.max(np.abs(refreshed_weights - logged_weights)) > WEIGHT_TOL),
            "baseline_topk_order": _topk_order(baseline),
            "refreshed_topk_order": _topk_order(refreshed),
            "topk_order_changed": _topk_order(baseline) != _topk_order(refreshed),
            "baseline_state": _weight_state(logged_weights),
            "refreshed_state": _weight_state(refreshed_weights),
            "state_changed": _weight_state(logged_weights) != _weight_state(refreshed_weights),
        }
        for idx, code in enumerate(ETF_CODES):
            row[f"baseline_weight_{code}"] = float(logged_weights[idx])
            row[f"refreshed_weight_{code}"] = float(refreshed_weights[idx])
            row[f"weight_delta_{code}"] = float(refreshed_weights[idx] - logged_weights[idx])
        rows.append(row)
    return pd.DataFrame(rows)


def has_open_prices(frames: PriceFrames) -> bool:
    """Return whether the bundle contains usable open-price rows."""

    return not frames.open.dropna(how="all").empty


def _next_trading_day(calendar: pd.DatetimeIndex, date_value: pd.Timestamp) -> pd.Timestamp | None:
    position = int(calendar.searchsorted(pd.Timestamp(date_value).normalize()))
    next_pos = position + 1
    return None if next_pos >= len(calendar) else pd.Timestamp(calendar[next_pos]).normalize()


def build_delay_only_weekly(events: list[dict], frames: PriceFrames) -> pd.DataFrame:
    """Estimate pure one-day execution delay from unchanged target weights."""

    if not has_open_prices(frames):
        return pd.DataFrame()
    rows = []
    previous_weights = np.zeros(len(ETF_CODES), dtype=float)
    open_frame = frames.open.reindex(columns=list(ETF_CODES))
    for event in events:
        trade_date = pd.Timestamp(event["current_dt"]).normalize()
        delayed_trade_date = _next_trading_day(frames.calendar, trade_date)
        if delayed_trade_date is None:
            continue
        if trade_date not in open_frame.index or delayed_trade_date not in open_frame.index:
            continue
        open_returns = open_frame.loc[delayed_trade_date] / open_frame.loc[trade_date] - 1.0
        if open_returns.isna().all():
            continue
        target_weights = np.asarray(event["final_weights"], dtype=float)
        contribution = (previous_weights - target_weights) * open_returns.to_numpy(dtype=float)
        row = {
            "signal_date": trade_date,
            "baseline_trade_date": trade_date,
            "delayed_trade_date": delayed_trade_date,
            "baseline_open_to_next_open_return": float(np.nansum(target_weights * open_returns)),
            "delay_only_open_to_next_open_return": float(np.nansum(previous_weights * open_returns)),
            "delay_minus_baseline_return": float(np.nansum(contribution)),
        }
        for idx, code in enumerate(ETF_CODES):
            row[f"previous_weight_{code}"] = float(previous_weights[idx])
            row[f"target_weight_{code}"] = float(target_weights[idx])
            row[f"open_return_{code}"] = float(open_returns.get(code, np.nan))
            row[f"contribution_{code}"] = float(contribution[idx])
        rows.append(row)
        previous_weights = target_weights
    return pd.DataFrame(rows)


def _weekly_weight_frame(
    events: list[dict],
    *,
    weight_rows: pd.DataFrame | None = None,
    delayed: bool,
) -> pd.DataFrame:
    rows = []
    for idx, event in enumerate(events):
        signal_date = pd.Timestamp(event["current_dt"]).normalize()
        trade_date = signal_date
        if delayed:
            trade_date = pd.Timestamp(weight_rows.iloc[idx]["delayed_trade_date"]).normalize() if weight_rows is not None else trade_date
        row = {"trade_date": trade_date}
        if weight_rows is None:
            weights = np.asarray(event["final_weights"], dtype=float)
        else:
            weights = np.asarray(
                [weight_rows.iloc[idx][f"refreshed_weight_{code}"] for code in ETF_CODES],
                dtype=float,
            )
        for code, weight in zip(ETF_CODES, weights, strict=True):
            row[code] = float(weight)
        rows.append(row)
    return pd.DataFrame(rows)


def _expand_open_weight_schedule(
    weekly: pd.DataFrame,
    calendar: pd.DatetimeIndex,
) -> pd.DataFrame:
    frame = weekly.set_index("trade_date").reindex(columns=list(ETF_CODES))
    expanded = frame.reindex(calendar).sort_index().ffill().fillna(0.0)
    expanded.index.name = "date"
    return expanded


def build_timing_path_compare(
    events: list[dict],
    frames: PriceFrames,
    signal_shift: pd.DataFrame,
    delay_only: pd.DataFrame,
) -> pd.DataFrame:
    """Build local open-to-open return paths for the three timing definitions."""

    if delay_only.empty or signal_shift.empty or not has_open_prices(frames):
        return pd.DataFrame()
    open_frame = frames.open.reindex(columns=list(ETF_CODES))
    open_returns = (open_frame.shift(-1) / open_frame - 1.0).iloc[:-1]
    baseline_weekly = _weekly_weight_frame(events, delayed=False)
    logic2_weekly = _weekly_weight_frame(
        events,
        weight_rows=delay_only.assign(
            **{
                f"refreshed_weight_{code}": [
                    np.asarray(event["final_weights"], dtype=float)[idx]
                    for event in events
                ]
                for idx, code in enumerate(ETF_CODES)
            }
        ),
        delayed=True,
    )
    logic3_weekly = _weekly_weight_frame(events, weight_rows=signal_shift.merge(
        delay_only[["signal_date", "delayed_trade_date"]],
        on="signal_date",
        how="inner",
    ), delayed=True)
    study_start = min(pd.Timestamp(event["current_dt"]).normalize() for event in events)
    study_end = pd.Timestamp(SCORE_END)
    calendar = open_returns.index[(open_returns.index >= study_start) & (open_returns.index < study_end)]
    open_returns = open_returns.reindex(calendar)
    baseline_schedule = _expand_open_weight_schedule(baseline_weekly, calendar)
    logic2_schedule = _expand_open_weight_schedule(logic2_weekly, calendar)
    logic3_schedule = _expand_open_weight_schedule(logic3_weekly, calendar)
    frame = pd.DataFrame(
        {
            "date": calendar,
            "baseline": (baseline_schedule * open_returns).sum(axis=1).to_numpy(),
            "logic_2_delay_only": (logic2_schedule * open_returns).sum(axis=1).to_numpy(),
            "logic_3_live_like": (logic3_schedule * open_returns).sum(axis=1).to_numpy(),
        }
    )
    return frame.dropna().reset_index(drop=True)


def _signal_shift_summary(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {"status": "empty"}
    max_error = float(frame["baseline_recompute_final_weight_max_abs_error"].max())
    calibrated = max_error <= CALIBRATION_TOL
    return {
        "status": "ok" if calibrated else "blocked_recompute_not_calibrated",
        "usable_for_decision": calibrated,
        "weeks": int(len(frame)),
        "baseline_recompute_max_abs_error": max_error,
        "changed_weeks": int(frame["any_target_weight_changed"].sum()),
        "changed_week_ratio": float(frame["any_target_weight_changed"].mean()),
        "topk_order_change_count": int(frame["topk_order_changed"].sum()),
        "state_change_count": int(frame["state_changed"].sum()),
        "l1_distance_mean": float(frame["target_weight_l1_distance"].mean()),
        "l1_distance_median": float(frame["target_weight_l1_distance"].median()),
        "l1_distance_p90": float(frame["target_weight_l1_distance"].quantile(0.90)),
        "module_change_counts": {
            "TrendGate": int(frame["trend_gate_changed"].sum()),
            "MomentumScore": int(frame["momentum_score_changed"].sum()),
            "CrowdPenalty": int(frame["crowd_penalty_changed"].sum()),
            "PortfolioVolScale": int(frame["portfolio_vol_scale_changed"].sum()),
        },
    }


def _delay_summary(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {"status": "blocked_missing_open"}
    annual_rows = []
    for year, group in frame.groupby(frame["signal_date"].dt.year):
        annual_rows.append(
            {
                "year": int(year),
                "weeks": int(len(group)),
                "compounded_delta": float((1.0 + group["delay_minus_baseline_return"]).prod() - 1.0),
                "mean_weekly_delta": float(group["delay_minus_baseline_return"].mean()),
            }
        )
    worst = frame.nsmallest(10, "delay_minus_baseline_return")[
        ["signal_date", "delay_minus_baseline_return"]
    ].copy()
    worst["signal_date"] = worst["signal_date"].dt.strftime("%Y-%m-%d")
    contributions = {
        code: float(frame[f"contribution_{code}"].sum())
        for code in ETF_CODES
        if f"contribution_{code}" in frame.columns
    }
    return {
        "status": "ok",
        "weeks": int(len(frame)),
        "mean_weekly_delta": float(frame["delay_minus_baseline_return"].mean()),
        "compounded_delta": float((1.0 + frame["delay_minus_baseline_return"]).prod() - 1.0),
        "annual_breakdown": annual_rows,
        "worst_weeks": worst.to_dict(orient="records"),
        "contribution_by_etf": contributions,
    }


def _timing_summary(frame: pd.DataFrame) -> dict[str, object]:
    if frame.empty:
        return {"status": "blocked_missing_open"}
    series = frame.set_index("date")
    metrics = {column: performance_metrics(series[column]) for column in series.columns}
    boot_logic2 = paired_block_bootstrap(series["baseline"], series["logic_2_delay_only"])
    boot_logic3 = paired_block_bootstrap(series["baseline"], series["logic_3_live_like"])
    rolling = pd.concat(
        [
            rolling_sharpe(series["baseline"]).rename("baseline"),
            rolling_sharpe(series["logic_2_delay_only"]).rename("logic_2_delay_only"),
            rolling_sharpe(series["logic_3_live_like"]).rename("logic_3_live_like"),
        ],
        axis=1,
    ).dropna()
    yearly = yearly_metrics(series["baseline"]).rename(
        columns={column: f"{column}_baseline" for column in yearly_metrics(series["baseline"]).columns if column != "year"}
    )
    for label in ["logic_2_delay_only", "logic_3_live_like"]:
        yearly_variant = yearly_metrics(series[label]).rename(
            columns={column: f"{column}_{label}" for column in yearly_metrics(series[label]).columns if column != "year"}
        )
        yearly = yearly.merge(yearly_variant, on="year", how="outer")
    return {
        "status": "ok",
        "metrics": metrics,
        "annual_return_delta": {
            "logic_2_minus_baseline": metrics["logic_2_delay_only"]["annual_return"] - metrics["baseline"]["annual_return"],
            "logic_3_minus_baseline": metrics["logic_3_live_like"]["annual_return"] - metrics["baseline"]["annual_return"],
        },
        "max_drawdown_delta": {
            "logic_2_minus_baseline": metrics["logic_2_delay_only"]["max_drawdown"] - metrics["baseline"]["max_drawdown"],
            "logic_3_minus_baseline": metrics["logic_3_live_like"]["max_drawdown"] - metrics["baseline"]["max_drawdown"],
        },
        "bootstrap": {
            "logic_2_minus_baseline": boot_logic2,
            "logic_3_minus_baseline": boot_logic3,
        },
        "rolling_sharpe_win_rate": {
            "logic_2_vs_baseline": float((rolling["logic_2_delay_only"] > rolling["baseline"]).mean())
            if not rolling.empty
            else np.nan,
            "logic_3_vs_baseline": float((rolling["logic_3_live_like"] > rolling["baseline"]).mean())
            if not rolling.empty
            else np.nan,
        },
        "yearly": yearly.to_dict(orient="records"),
    }


def _render_delay_report(summary: dict[str, object]) -> str:
    if summary["status"] != "ok":
        return "\n".join(
            [
                "# 执行延迟影响",
                "",
                "- 当前原始行情包还没有可用 `open` 字段，`delay_only` 暂时不能计算。",
                "- 先刷新带 `open` 的 JoinQuant 行情导出，再重跑本地研究。",
                "",
            ]
        )
    annual = pd.DataFrame(summary["annual_breakdown"])
    worst = pd.DataFrame(summary["worst_weeks"])
    contributions = pd.DataFrame(
        [{"ETF": code, "累计贡献": value} for code, value in summary["contribution_by_etf"].items()]
    )
    return "\n".join(
        [
            "# 执行延迟影响",
            "",
            f"- **周数**: `{summary['weeks']}`",
            f"- **周度均值差**: `{summary['mean_weekly_delta']:.4%}`",
            f"- **全样本累计差**: `{summary['compounded_delta']:.4%}`",
            "",
            "## 年度拆解",
            "",
            markdown_table(annual),
            "",
            "## 最差 10 周",
            "",
            markdown_table(worst),
            "",
            "## ETF 贡献",
            "",
            markdown_table(contributions),
            "",
        ]
    )


def _render_signal_shift_report(summary: dict[str, object]) -> str:
    if summary["status"] == "empty":
        return "# 信号刷新影响\n\n_无可用记录。_\n"
    if summary["status"] != "ok":
        return "\n".join(
            [
                "# 信号刷新影响",
                "",
                "- 当前本地复算还没有通过 baseline 校准，`signal_shift` 结果暂不可用于决策。",
                f"- **baseline 本地复算最大误差**: `{summary['baseline_recompute_max_abs_error']:.3e}`",
                f"- **校准阈值**: `{CALIBRATION_TOL:.1e}`",
                "",
            ]
        )
    module_counts = pd.DataFrame(
        [{"模块": key, "触发周数": value} for key, value in summary["module_change_counts"].items()]
    )
    return "\n".join(
        [
            "# 信号刷新影响",
            "",
            f"- **周数**: `{summary['weeks']}`",
            f"- **目标权重变化周数**: `{summary['changed_weeks']}`",
            f"- **目标权重变化占比**: `{summary['changed_week_ratio']:.1%}`",
            f"- **L1 距离中位数 / P90**: `{summary['l1_distance_median']:.4f}` / `{summary['l1_distance_p90']:.4f}`",
            f"- **TopK 顺序变化**: `{summary['topk_order_change_count']}`",
            f"- **仓位状态切换**: `{summary['state_change_count']}`",
            f"- **baseline 本地复算最大误差**: `{summary['baseline_recompute_max_abs_error']:.3e}`",
            "",
            "## 模块触发次数",
            "",
            markdown_table(module_counts),
            "",
        ]
    )


def _timing_decision(summary: dict[str, object], signal_summary: dict[str, object]) -> dict[str, object]:
    reasons = []
    if summary["status"] != "ok":
        reasons.append("missing_open_prices")
    if signal_summary.get("usable_for_decision") is False:
        reasons.append("signal_recompute_not_calibrated")
    if reasons:
        return {
            "status": "blocked",
            "needs_cloud_confirmation": False,
            "reasons": reasons,
        }
    annual = summary["annual_return_delta"]
    drawdown = summary["max_drawdown_delta"]
    if abs(float(annual["logic_2_minus_baseline"])) > 0.003:
        reasons.append("logic_2_annual_delta_gt_0.30pp")
    if abs(float(annual["logic_3_minus_baseline"])) > 0.005:
        reasons.append("logic_3_annual_delta_gt_0.50pp")
    if float(drawdown["logic_2_minus_baseline"]) < -0.003:
        reasons.append("logic_2_drawdown_worse_gt_0.30pp")
    if float(drawdown["logic_3_minus_baseline"]) < -0.003:
        reasons.append("logic_3_drawdown_worse_gt_0.30pp")
    if signal_summary.get("changed_week_ratio", 0.0) > 0.10:
        reasons.append("signal_shift_not_rare")
    return {
        "status": "ok",
        "needs_cloud_confirmation": bool(reasons),
        "reasons": reasons,
    }


def _render_timing_decision(summary: dict[str, object], decision: dict[str, object]) -> str:
    if decision["status"] != "ok":
        return "\n".join(
            [
                "# 本地时序研究决策",
                "",
                f"- 当前仍不能形成可用于决策的本地结论：`{';'.join(decision['reasons'])}`。",
                "- 需要先补齐 `open` 行情，并让 baseline 本地复算通过校准，再解释执行时序影响。",
                "",
            ]
        )
    metrics = pd.DataFrame(
        [
            {"口径": label, **values}
            for label, values in summary["metrics"].items()
        ]
    )
    return "\n".join(
        [
            "# 本地时序研究决策",
            "",
            f"- **是否建议进入云端确认**: `{'是' if decision['needs_cloud_confirmation'] else '否'}`",
            f"- **触发原因**: `{';'.join(decision['reasons']) if decision['reasons'] else 'none'}`",
            "",
            "## 三组近似路径",
            "",
            markdown_table(metrics),
            "",
            "说明：该结论仍属于本地近似，不能替代正式云端回测。",
            "",
        ]
    )


def _write_manifest(
    run: ResearchRunLayout,
    *,
    raw_price_path: Path,
    audit_log_path: Path,
    outputs: Iterable[str],
    has_open: bool,
) -> None:
    payload = {
        "schema_version": 1,
        "project": "execution_timing",
        "run_id": run.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "raw_price_path": raw_price_path.as_posix(),
            "audit_log_path": audit_log_path.as_posix(),
            "has_open_prices": has_open,
        },
        "outputs": list(outputs),
    }
    write_json(run.manifest_path, payload)


def analyze_project(
    *,
    project_dir: str | Path,
    run_id: str,
    raw_price_path: str | Path | None = None,
    audit_log_path: str | Path | None = None,
) -> dict[str, object]:
    """Run the local execution-timing workflow and persist outputs."""

    project = ResearchProjectLayout.from_path(project_dir)
    project.ensure_project_dirs()
    run = project.run(run_id)
    run.ensure_dirs()
    raw_path = Path(raw_price_path) if raw_price_path else default_raw_price_path()
    audit_path = Path(audit_log_path) if audit_log_path else default_audit_log_path()
    frames = load_price_bundle(raw_path, ETF_CODES)
    events = load_rebalance_events(audit_path)

    signal_shift = build_signal_shift_weekly(events, frames)
    delay_only = build_delay_only_weekly(events, frames)
    timing_compare = build_timing_path_compare(events, frames, signal_shift, delay_only)

    signal_summary = _signal_shift_summary(signal_shift)
    delay_summary = _delay_summary(delay_only)
    timing_summary = _timing_summary(timing_compare)
    timing_decision = _timing_decision(timing_summary, signal_summary)

    signal_shift.to_csv(run.tables_dir / "signal_shift_weekly.csv", index=False)
    delay_only.to_csv(run.tables_dir / "delay_only_weekly_impact.csv", index=False)
    timing_compare.to_csv(run.tables_dir / "timing_path_compare.csv", index=False)
    write_json(run.tables_dir / "signal_shift_summary.json", signal_summary)
    write_json(run.tables_dir / "delay_only_summary.json", delay_summary)
    write_json(run.tables_dir / "timing_path_summary.json", timing_summary)
    write_json(run.tables_dir / "timing_local_decision.json", timing_decision)

    (run.reports_dir / "signal_shift_report.md").write_text(
        _render_signal_shift_report(signal_summary),
        encoding="utf-8",
    )
    (run.reports_dir / "delay_only_impact.md").write_text(
        _render_delay_report(delay_summary),
        encoding="utf-8",
    )
    (run.reports_dir / "timing_local_decision.md").write_text(
        _render_timing_decision(timing_summary, timing_decision),
        encoding="utf-8",
    )

    outputs = [
        "reports/delay_only_impact.md",
        "reports/signal_shift_report.md",
        "reports/timing_local_decision.md",
        "tables/delay_only_weekly_impact.csv",
        "tables/delay_only_summary.json",
        "tables/signal_shift_weekly.csv",
        "tables/signal_shift_summary.json",
        "tables/timing_path_compare.csv",
        "tables/timing_path_summary.json",
        "tables/timing_local_decision.json",
    ]
    _write_manifest(
        run,
        raw_price_path=raw_path,
        audit_log_path=audit_path,
        outputs=outputs,
        has_open=has_open_prices(frames),
    )
    return {
        "signal_shift_summary": signal_summary,
        "delay_only_summary": delay_summary,
        "timing_path_summary": timing_summary,
        "timing_local_decision": timing_decision,
    }
