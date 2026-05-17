"""Price bundle loading helpers shared by research projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class PriceFrames:
    """Normalized daily price bundle."""

    close: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    money: pd.DataFrame
    calendar: pd.DatetimeIndex


def _field_frame(payload: dict, codes: tuple[str, ...], field: str, calendar: pd.DatetimeIndex) -> pd.DataFrame:
    series_map: dict[str, pd.Series] = {}
    for code in codes:
        rows = payload.get("prices", {}).get(code, [])
        if not rows:
            continue
        frame = pd.DataFrame(rows)
        if "date" not in frame.columns or field not in frame.columns:
            continue
        index = pd.to_datetime(frame["date"]).dt.normalize()
        values = pd.to_numeric(frame[field], errors="coerce")
        series_map[code] = pd.Series(values.to_numpy(), index=index)
    frame = pd.DataFrame(series_map, index=calendar)
    return frame.reindex(columns=list(codes))


def load_price_bundle(path: str | Path, codes: Iterable[str] | None = None) -> PriceFrames:
    """Load the repository's canonical JoinQuant price export JSON."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    inferred_codes = tuple(payload.get("prices", {}).keys())
    selected_codes = tuple(codes) if codes is not None else inferred_codes
    calendar = pd.DatetimeIndex(pd.to_datetime(payload["calendar"]).normalize())
    return PriceFrames(
        close=_field_frame(payload, selected_codes, "close", calendar),
        high=_field_frame(payload, selected_codes, "high", calendar),
        low=_field_frame(payload, selected_codes, "low", calendar),
        money=_field_frame(payload, selected_codes, "money", calendar),
        calendar=calendar,
    )
