"""Calendar and forward-return helpers for weekly strategy research."""

from __future__ import annotations

from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd


def first_trading_days_by_week(
    calendar: pd.DatetimeIndex,
    start: date,
    end: date,
) -> pd.DatetimeIndex:
    """Return the first available trading day of each natural week."""

    mask = (calendar.date >= start) & (calendar.date <= end)
    scoped = calendar[mask]
    if len(scoped) == 0:
        return scoped
    groups = pd.Series(scoped, index=scoped).groupby(scoped.to_period("W-SUN"))
    return pd.DatetimeIndex([group.iloc[0] for _, group in groups])


def build_weekly_anchor_frame(
    calendar: pd.DatetimeIndex,
    start: date,
    end: date,
    horizons: Iterable[int],
) -> pd.DataFrame:
    """Build weekly signal/as-of/future-date anchors."""

    selected_horizons = tuple(horizons)
    rows: list[dict[str, object]] = []
    for anchor in first_trading_days_by_week(calendar, start, end):
        position = int(calendar.searchsorted(anchor))
        if position <= 0:
            continue
        row: dict[str, object] = {
            "signal_date": anchor,
            "asof_date": calendar[position - 1],
        }
        for horizon in selected_horizons:
            future_pos = position + horizon - 1
            row[f"future_{horizon}d"] = calendar[future_pos] if future_pos < len(calendar) else pd.NaT
        rows.append(row)
    return pd.DataFrame(rows)


def forward_return_frame(
    close: pd.DataFrame,
    anchors: pd.DataFrame,
    horizons: Iterable[int],
    codes: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Compute forward returns from anchor as-of closes."""

    selected_horizons = tuple(horizons)
    selected_codes = tuple(codes) if codes is not None else tuple(close.columns)
    rows: list[dict[str, object]] = []
    for _, anchor in anchors.iterrows():
        asof_date = pd.Timestamp(anchor["asof_date"])
        for code in selected_codes:
            record: dict[str, object] = {
                "signal_date": pd.Timestamp(anchor["signal_date"]),
                "asof_date": asof_date,
                "etf": code,
            }
            base = close.at[asof_date, code] if asof_date in close.index and code in close.columns else np.nan
            for horizon in selected_horizons:
                future_date = anchor.get(f"future_{horizon}d", pd.NaT)
                if pd.isna(future_date) or future_date not in close.index or pd.isna(base):
                    record[f"forward_{horizon}d"] = np.nan
                else:
                    future_close = close.at[pd.Timestamp(future_date), code]
                    record[f"forward_{horizon}d"] = (
                        future_close / base - 1 if pd.notna(future_close) else np.nan
                    )
            rows.append(record)
    return pd.DataFrame(rows)
