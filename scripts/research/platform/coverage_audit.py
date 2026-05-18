"""Reusable scan-domain coverage auditing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import pandas as pd


@dataclass(frozen=True)
class ScanCoverageSlice:
    """Coverage payload for one independent scan slice."""

    slice_id: str
    lower_bound: float
    upper_bound: float
    breakpoints: tuple[float, ...]
    interval_points: tuple[float, ...]
    breakpoint_sources: Mapping[str, int] = field(default_factory=dict)


def audit_scan_coverage(slices: list[ScanCoverageSlice]) -> pd.DataFrame:
    """Return one row per slice with coverage counts and gap flags."""

    rows = []
    for item in slices:
        breakpoints = tuple(sorted(set(float(value) for value in item.breakpoints)))
        interval_points = tuple(sorted(set(float(value) for value in item.interval_points)))
        expected_intervals = max(0, len(breakpoints) - 1)
        missing_breakpoints = int(
            not breakpoints
            or breakpoints[0] != float(item.lower_bound)
            or breakpoints[-1] != float(item.upper_bound)
        )
        missing_intervals = max(0, expected_intervals - len(interval_points))
        row = {
            "slice_id": item.slice_id,
            "lower_bound": float(item.lower_bound),
            "upper_bound": float(item.upper_bound),
            "breakpoint_count": len(breakpoints),
            "interval_count": expected_intervals,
            "interval_point_count": len(interval_points),
            "evaluation_point_count": len(breakpoints) + len(interval_points),
            "missing_breakpoints": missing_breakpoints,
            "missing_intervals": missing_intervals,
        }
        row.update({f"source_{key}": int(value) for key, value in item.breakpoint_sources.items()})
        rows.append(row)
    return pd.DataFrame(rows)


def coverage_is_complete(frame: pd.DataFrame) -> bool:
    """Return whether all slices cover both boundaries and every interval."""

    if frame.empty:
        return False
    return bool(
        int(frame["missing_breakpoints"].sum()) == 0
        and int(frame["missing_intervals"].sum()) == 0
    )
