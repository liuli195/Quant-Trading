from __future__ import annotations

import pandas as pd
import pytest

from scripts.research.portfolio_volatility_research.domain_builder import build_domains
from scripts.research.portfolio_volatility_research.evaluator import PortfolioVolContext


def _context() -> PortfolioVolContext:
    return PortfolioVolContext(
        events=[
            {
                "raw_weights": [0.8, 0.3, 0.2],
            }
        ],
        close=pd.DataFrame(),
        asset_returns=pd.DataFrame(),
        baseline_returns=pd.Series(dtype=float),
        baseline_schedule=pd.DataFrame(),
        baseline_metrics={},
        baseline_cloud_metrics={},
        params={"MinWeight": 0.05, "MaxWeight": 0.60, "MaxTotalWeight": 1.0},
        portfolio_vol_cache={20: [0.2], 40: [0.2], 60: [0.2], 90: [0.2], 120: [0.2]},
    )


def test_build_domains_includes_boundaries_breakpoints_and_intervals() -> None:
    domain = build_domains(_context())[20]
    assert domain.breakpoints[0] == 0.0
    assert domain.breakpoints[-1] == 0.2
    assert any(value == pytest.approx(0.2 * 0.05 / 0.8) for value in domain.breakpoints)
    assert any(value == pytest.approx(0.2 * 0.60 / 0.8) for value in domain.breakpoints)
    assert len(domain.interval_points) == len(domain.breakpoints) - 1
