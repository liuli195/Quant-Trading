"""Local counterfactual replay for momentum-tilt variants."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from scripts.research.research_core.metrics import paired_block_bootstrap, performance_metrics, rolling_sharpe, yearly_metrics


@dataclass(frozen=True)
class VariantSpec:
    """One local momentum-tilt counterfactual."""

    label: str
    strength: float
    shape: str = "linear"
    extreme_start: float | None = None
    extreme_cap: float = 1.0


@dataclass(frozen=True)
class ReplayResult:
    """Counterfactual replay output."""

    spec: VariantSpec
    returns: pd.Series
    weights: pd.DataFrame
    contributions: pd.DataFrame
    metrics: dict[str, float]


def compute_momentum_tilts(
    momentum_scores: np.ndarray,
    trend_gates: np.ndarray,
    params: dict,
    spec: VariantSpec,
) -> np.ndarray:
    """Recompute momentum tilts for one local variant."""

    tilts = np.zeros(len(momentum_scores), dtype=float)
    active = np.flatnonzero(trend_gates > 0)
    if len(active) == 0:
        return tilts
    active_scores = momentum_scores[active]
    mean_score = float(np.mean(active_scores))
    tilt_min = float(params["MomentumTiltMin"])
    tilt_max = float(params["MomentumTiltMax"])
    for idx in active:
        score = float(momentum_scores[idx])
        raw_tilt = float(np.clip(1.0 + spec.strength * (score - mean_score), tilt_min, tilt_max))
        tilt = raw_tilt
        if spec.shape == "plateau" and spec.extreme_start is not None and score >= spec.extreme_start:
            tilt = min(raw_tilt, spec.extreme_cap)
        elif spec.shape == "soft_shoulder" and spec.extreme_start is not None and score >= spec.extreme_start:
            if raw_tilt > spec.extreme_cap:
                progress = min(max((score - spec.extreme_start) / (1.0 - spec.extreme_start), 0.0), 1.0)
                tilt = raw_tilt - (raw_tilt - spec.extreme_cap) * progress
        tilts[idx] = tilt
    return tilts


def apply_relative_tilts(
    rp_weights: np.ndarray,
    trend_gates: np.ndarray,
    momentum_tilts: np.ndarray,
    rsrs_tilts: np.ndarray,
) -> np.ndarray:
    """Combine relative tilts and renormalize inside the active set."""

    tilted = np.zeros(len(rp_weights), dtype=float)
    active = np.flatnonzero((trend_gates > 0) & (rp_weights > 0))
    if len(active) == 0:
        return tilted
    tilted_raw = rp_weights * momentum_tilts * rsrs_tilts
    total_raw = float(tilted_raw[active].sum())
    base_total = float(rp_weights[active].sum())
    if total_raw <= 0 or base_total <= 0:
        return np.asarray(rp_weights, dtype=float)
    tilted[active] = tilted_raw[active] / total_raw * base_total
    return tilted


def apply_weight_constraints(final_weights: np.ndarray, params: dict) -> np.ndarray:
    """Mirror the strategy's final weight constraints."""

    result = np.asarray(final_weights, dtype=float).copy()
    max_weight = float(params["MaxWeight"])
    min_weight = float(params["MinWeight"])
    max_total = float(params["MaxTotalWeight"])
    result[result > max_weight] = max_weight
    result[result < min_weight] = 0.0
    total = float(result.sum())
    if total > max_total:
        result = result * max_total / total
    return result


def recompute_final_weights(event: dict, spec: VariantSpec) -> np.ndarray:
    """Recompute one weekly target-weight vector from logged state."""

    params = dict(event["params"])
    trend_gates = np.asarray(event["trend_gates"], dtype=float)
    rp_weights = np.asarray(event["rp_weights"], dtype=float)
    scores = np.asarray(event["momentum_scores"], dtype=float)
    rsrs_tilts = np.asarray(event["rsrs_tilts"], dtype=float)
    crowd_penalties = np.asarray(event["crowd_penalties"], dtype=float)
    momentum_tilts = compute_momentum_tilts(scores, trend_gates, params, spec)
    tilted = apply_relative_tilts(rp_weights, trend_gates, momentum_tilts, rsrs_tilts)
    raw_weights = tilted * trend_gates * crowd_penalties
    final_before_constraints = raw_weights * float(event["portfolio_vol_scale"])
    return apply_weight_constraints(final_before_constraints, params)


def event_weight_frame(events: list[dict], spec: VariantSpec | None = None) -> pd.DataFrame:
    """Build one weekly weight frame from audit events."""

    rows = []
    for event in events:
        signal_date = pd.Timestamp(event["current_dt"]).normalize()
        weights = (
            np.asarray(event["final_weights"], dtype=float)
            if spec is None
            else recompute_final_weights(event, spec)
        )
        row = {"signal_date": signal_date}
        for code, weight in zip(event["pool"], weights, strict=True):
            row[code] = float(weight)
        rows.append(row)
    return pd.DataFrame(rows).sort_values("signal_date").reset_index(drop=True)


def expand_weight_schedule(
    weekly_weights: pd.DataFrame,
    calendar: pd.DatetimeIndex,
    codes: Iterable[str],
) -> pd.DataFrame:
    """Forward-fill weekly weights across daily trading dates."""

    selected_codes = list(codes)
    frame = weekly_weights.set_index("signal_date").reindex(columns=selected_codes)
    expanded = frame.reindex(calendar).sort_index().ffill().fillna(0.0)
    expanded.index.name = "date"
    return expanded


def replay_variant(
    events: list[dict],
    close: pd.DataFrame,
    baseline_returns: pd.Series,
    spec: VariantSpec,
) -> ReplayResult:
    """Replay one local counterfactual around the realized baseline path."""

    codes = tuple(close.columns)
    daily_index = baseline_returns.index
    etf_returns = close.pct_change().reindex(daily_index).fillna(0.0)
    baseline_schedule = expand_weight_schedule(event_weight_frame(events), daily_index, codes)
    variant_schedule = expand_weight_schedule(event_weight_frame(events, spec), daily_index, codes)
    delta_weights = variant_schedule - baseline_schedule
    contributions = delta_weights * etf_returns
    replay_returns = baseline_returns.add(contributions.sum(axis=1), fill_value=0.0)
    return ReplayResult(
        spec=spec,
        returns=replay_returns.rename(spec.label),
        weights=variant_schedule,
        contributions=contributions,
        metrics=performance_metrics(replay_returns),
    )


def summarize_variant_vs_baseline(
    baseline_returns: pd.Series,
    result: ReplayResult,
) -> dict[str, float]:
    """Compute decision-facing robustness summaries for one replay result."""

    baseline_metrics = performance_metrics(baseline_returns)
    rolling_base = rolling_sharpe(baseline_returns)
    rolling_variant = rolling_sharpe(result.returns)
    aligned_rolling = pd.concat([rolling_base, rolling_variant], axis=1).dropna()
    yearly = yearly_metrics(result.returns).merge(
        yearly_metrics(baseline_returns),
        on="year",
        suffixes=("_variant", "_baseline"),
    )
    bootstrap = paired_block_bootstrap(baseline_returns, result.returns)
    contribution_totals = result.contributions.sum()
    improvement = result.metrics["total_return"] - baseline_metrics["total_return"]
    dominant_share = 0.0
    if improvement != 0:
        dominant_share = float(contribution_totals.abs().max() / abs(improvement))
    leave_one = {}
    for code in result.contributions.columns:
        without_code = baseline_returns + (result.contributions.sum(axis=1) - result.contributions[code])
        leave_one[code] = performance_metrics(without_code)["sharpe"] - baseline_metrics["sharpe"]
    return {
        "annual_return_delta": result.metrics["annual_return"] - baseline_metrics["annual_return"],
        "sharpe_delta": result.metrics["sharpe"] - baseline_metrics["sharpe"],
        "max_drawdown_delta": result.metrics["max_drawdown"] - baseline_metrics["max_drawdown"],
        "rolling_sharpe_win_rate": (
            float((aligned_rolling.iloc[:, 1] > aligned_rolling.iloc[:, 0]).mean())
            if not aligned_rolling.empty
            else np.nan
        ),
        "years_better": float((yearly["sharpe_variant"] > yearly["sharpe_baseline"]).sum()),
        "bootstrap_observed": bootstrap["observed"],
        "bootstrap_ci_low": bootstrap["ci_low"],
        "bootstrap_ci_high": bootstrap["ci_high"],
        "bootstrap_p_value": bootstrap["p_value"],
        "dominant_etf_share": dominant_share,
        **{f"leave_one_{code}_sharpe_delta": value for code, value in leave_one.items()},
    }
