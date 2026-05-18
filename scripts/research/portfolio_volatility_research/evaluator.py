"""Portfolio-volatility replay helpers shared by the platform plugin."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.momentum_tilt_research.replay import (
    apply_weight_constraints,
    event_weight_frame,
    expand_weight_schedule,
)
from scripts.research.research_core.audit import load_rebalance_events
from scripts.research.research_core.metrics import performance_metrics
from scripts.research.research_core.prices import load_price_bundle

CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")
WINDOWS = (20, 40, 60, 90, 120)


@dataclass(frozen=True)
class PortfolioVolContext:
    """Reusable inputs for portfolio-volatility replay."""

    events: list[dict]
    close: pd.DataFrame
    asset_returns: pd.DataFrame
    baseline_returns: pd.Series
    baseline_schedule: pd.DataFrame
    baseline_metrics: dict[str, float]
    baseline_cloud_metrics: dict[str, float]
    params: dict
    portfolio_vol_cache: dict[int, list[float]]


def _portfolio_vol(
    returns: pd.DataFrame,
    raw_weights: np.ndarray,
    previous_date: str,
    window: int,
) -> float:
    history = (
        returns.loc[: pd.Timestamp(previous_date).normalize()]
        .tail(window)
        .dropna(how="all")
    )
    if len(history) < 5:
        return 0.0
    covariance = history.cov().to_numpy() * 252
    return float(np.sqrt(raw_weights @ covariance @ raw_weights))


def _parse_cloud_summary(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "annual_return": float(str(raw["策略年化收益"]).rstrip("%")) / 100,
        "volatility": float(raw["策略波动率"]),
        "sharpe": float(raw["夏普比率"]),
        "max_drawdown": -float(str(raw["最大回撤"]).rstrip("%")) / 100,
    }


def load_context(
    *,
    baseline_run_dir: Path,
    raw_price_path: Path,
) -> PortfolioVolContext:
    """Load replay inputs from one baseline cloud run and raw price bundle."""

    audit_log_path = baseline_run_dir / "tabs_raw" / "audit_log.jsonl"
    baseline_returns_path = baseline_run_dir / "tabs_raw" / "daily_returns.md"
    summary_path = baseline_run_dir / "summary_metrics.json"

    events = load_rebalance_events(audit_log_path)
    frames = load_price_bundle(raw_price_path, CODES)
    close = frames.close.reindex(columns=list(CODES))
    returns = close.pct_change()
    from scripts.research.research_core.metrics import parse_cumulative_returns_md

    baseline_returns = parse_cumulative_returns_md(baseline_returns_path)
    asset_returns = returns.reindex(baseline_returns.index).fillna(0.0)
    baseline_schedule = expand_weight_schedule(
        event_weight_frame(events),
        baseline_returns.index,
        CODES,
    )
    portfolio_vol_cache = {
        window: [
            _portfolio_vol(
                returns,
                np.asarray(event["raw_weights"], dtype=float),
                event["previous_date"],
                window,
            )
            for event in events
        ]
        for window in WINDOWS
    }
    return PortfolioVolContext(
        events=events,
        close=close,
        asset_returns=asset_returns,
        baseline_returns=baseline_returns,
        baseline_schedule=baseline_schedule,
        baseline_metrics=performance_metrics(baseline_returns),
        baseline_cloud_metrics=_parse_cloud_summary(summary_path),
        params=dict(events[0]["params"]),
        portfolio_vol_cache=portfolio_vol_cache,
    )


def build_variant_schedule(
    ctx: PortfolioVolContext,
    *,
    window: int,
    target: float,
) -> pd.DataFrame:
    """Build one target-weight schedule for a global target-volatility variant."""

    rows: list[dict[str, object]] = []
    for event, portfolio_vol in zip(
        ctx.events,
        ctx.portfolio_vol_cache[window],
        strict=True,
    ):
        raw = np.asarray(event["raw_weights"], dtype=float)
        scale = 1.0 if portfolio_vol <= 0 else min(1.0, float(target) / portfolio_vol)
        final = apply_weight_constraints(raw * scale, ctx.params)
        rows.append(
            {
                "signal_date": pd.Timestamp(event["current_dt"]).normalize(),
                **{code: float(weight) for code, weight in zip(CODES, final, strict=True)},
            }
        )
    weekly = pd.DataFrame(rows)
    return expand_weight_schedule(weekly, ctx.baseline_returns.index, CODES)


def evaluate_variant(
    ctx: PortfolioVolContext,
    *,
    window: int,
    target: float,
    label: str | None = None,
) -> dict[str, float | str]:
    """Evaluate one global target-volatility variant."""

    schedule = build_variant_schedule(ctx, window=window, target=target)
    contributions = (schedule - ctx.baseline_schedule) * ctx.asset_returns
    returns = ctx.baseline_returns.add(contributions.sum(axis=1), fill_value=0.0)
    metrics = performance_metrics(returns)
    return {
        "candidate_id": label or f"w{window}-t{target:.12f}",
        "label": label or f"w{window}-t{target:.12f}",
        "window": int(window),
        "target": float(target),
        "avg_position": float(schedule.sum(axis=1).mean()),
        **metrics,
        "annual_delta": metrics["annual_return"] - ctx.baseline_metrics["annual_return"],
        "volatility_delta": metrics["volatility"] - ctx.baseline_metrics["volatility"],
        "sharpe_delta": metrics["sharpe"] - ctx.baseline_metrics["sharpe"],
        "max_drawdown_delta": metrics["max_drawdown"] - ctx.baseline_metrics["max_drawdown"],
    }
