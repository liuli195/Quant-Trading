"""Reusable building blocks for local strategy research workflows."""

from .audit import load_rebalance_events, load_run_start_params
from .calendar import (
    build_weekly_anchor_frame,
    first_trading_days_by_week,
    forward_return_frame,
)
from .layout import ResearchProjectLayout, ResearchRunLayout
from .metrics import (
    paired_block_bootstrap,
    parse_cumulative_returns_md,
    performance_metrics,
    rolling_sharpe,
    yearly_metrics,
)
from .prices import PriceFrames, load_price_bundle

__all__ = [
    "PriceFrames",
    "ResearchProjectLayout",
    "ResearchRunLayout",
    "build_weekly_anchor_frame",
    "first_trading_days_by_week",
    "forward_return_frame",
    "load_price_bundle",
    "load_rebalance_events",
    "load_run_start_params",
    "paired_block_bootstrap",
    "parse_cumulative_returns_md",
    "performance_metrics",
    "rolling_sharpe",
    "yearly_metrics",
]
