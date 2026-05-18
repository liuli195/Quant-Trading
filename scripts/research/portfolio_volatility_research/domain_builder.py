"""Exact scan-domain construction for portfolio-volatility targets."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .evaluator import PortfolioVolContext, WINDOWS


@dataclass(frozen=True)
class PortfolioVolDomain:
    """One exact scan domain for one volatility window."""

    window: int
    breakpoints: tuple[float, ...]
    interval_points: tuple[float, ...]
    breakpoint_sources: dict[str, int]

    @property
    def upper_bound(self) -> float:
        """Largest target considered for this window."""

        return self.breakpoints[-1]

    @property
    def evaluation_points(self) -> tuple[float, ...]:
        """All points needed for breakpoint and interval coverage."""

        return tuple(sorted(set(self.breakpoints + self.interval_points)))


def _unique_sorted(values: set[float], *, atol: float = 1e-12) -> tuple[float, ...]:
    """Collapse floating-point duplicates that do not form meaningful intervals."""

    merged: list[float] = []
    for value in sorted(float(item) for item in values):
        if not merged or value - merged[-1] > atol:
            merged.append(value)
        else:
            merged[-1] = max(merged[-1], value)
    return tuple(merged)

def _max_total_roots(
    raw: np.ndarray,
    *,
    portfolio_vol: float,
    local_breakpoints: list[float],
    min_weight: float,
    max_weight: float,
    max_total: float,
) -> list[float]:
    roots: list[float] = []
    for lower, upper in zip(local_breakpoints, local_breakpoints[1:]):
        midpoint = (lower + upper) / 2.0
        scaled = raw * midpoint / portfolio_vol
        slope = 0.0
        intercept = 0.0
        for raw_weight, scaled_weight in zip(raw, scaled, strict=True):
            if scaled_weight < min_weight:
                continue
            if scaled_weight > max_weight:
                intercept += max_weight
            else:
                slope += float(raw_weight) / portfolio_vol
        if slope <= 0:
            continue
        root = (max_total - intercept) / slope
        if lower < root < upper:
            roots.append(float(root))
    return roots


def build_domains(ctx: PortfolioVolContext) -> dict[int, PortfolioVolDomain]:
    """Build the exact behavior-complete target-volatility domains."""

    min_weight = float(ctx.params["MinWeight"])
    max_weight = float(ctx.params["MaxWeight"])
    max_total = float(ctx.params["MaxTotalWeight"])
    domains: dict[int, PortfolioVolDomain] = {}
    for window in WINDOWS:
        breakpoints = {0.0}
        source_counts = {
            "portfolio_vol": 0,
            "min_weight": 0,
            "max_weight": 0,
            "max_total_weight": 0,
        }
        for event, portfolio_vol in zip(ctx.events, ctx.portfolio_vol_cache[window], strict=True):
            raw = np.asarray(event["raw_weights"], dtype=float)
            portfolio_vol = float(portfolio_vol)
            if portfolio_vol <= 0:
                continue
            breakpoints.add(portfolio_vol)
            source_counts["portfolio_vol"] += 1
            local_breakpoints = {0.0, portfolio_vol}
            for raw_weight in raw:
                raw_weight = float(raw_weight)
                if raw_weight <= 0:
                    continue
                min_root = portfolio_vol * min_weight / raw_weight
                max_root = portfolio_vol * max_weight / raw_weight
                if 0.0 <= min_root <= portfolio_vol:
                    local_breakpoints.add(float(min_root))
                    source_counts["min_weight"] += 1
                if 0.0 <= max_root <= portfolio_vol:
                    local_breakpoints.add(float(max_root))
                    source_counts["max_weight"] += 1
            sorted_local = sorted(local_breakpoints)
            roots = _max_total_roots(
                raw,
                portfolio_vol=portfolio_vol,
                local_breakpoints=sorted_local,
                min_weight=min_weight,
                max_weight=max_weight,
                max_total=max_total,
            )
            breakpoints.update(roots)
            source_counts["max_total_weight"] += len(roots)
            breakpoints.update(sorted_local)
        sorted_breakpoints = _unique_sorted(breakpoints)
        interval_points = tuple(
            (lower + upper) / 2.0
            for lower, upper in zip(sorted_breakpoints, sorted_breakpoints[1:])
        )
        domains[window] = PortfolioVolDomain(
            window=window,
            breakpoints=sorted_breakpoints,
            interval_points=interval_points,
            breakpoint_sources=source_counts,
        )
    return domains


def representative_smoke_points(
    domains: dict[int, PortfolioVolDomain],
    *,
    per_window: int = 16,
) -> list[dict[str, float | int]]:
    """Select representative points for a bounded performance smoke pass."""

    rows: list[dict[str, float | int]] = []
    for window, domain in domains.items():
        points = np.asarray(domain.evaluation_points, dtype=float)
        if len(points) <= per_window:
            selected = points
        else:
            indices = np.linspace(0, len(points) - 1, per_window, dtype=int)
            selected = points[indices]
        for target in sorted(set(float(value) for value in selected)):
            rows.append({"window": int(window), "target": target})
    return rows
