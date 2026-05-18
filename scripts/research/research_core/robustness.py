"""Reusable robustness checks for local research."""

from __future__ import annotations

import pandas as pd

from .metrics import paired_block_bootstrap, rolling_sharpe, yearly_metrics


class RobustnessToolkit:
    """Small facade for standard robustness routines."""

    @staticmethod
    def paired_bootstrap(
        baseline: pd.Series,
        variant: pd.Series,
        *,
        n_boot: int = 2000,
        block: int = 40,
        seed: int = 42,
    ) -> dict[str, float]:
        return paired_block_bootstrap(baseline, variant, n_boot=n_boot, block=block, seed=seed)

    @staticmethod
    def rolling_win_rate(baseline: pd.Series, variant: pd.Series, *, window: int = 252) -> float:
        lhs = rolling_sharpe(baseline, window=window)
        rhs = rolling_sharpe(variant, window=window)
        aligned = pd.concat([lhs.rename("baseline"), rhs.rename("variant")], axis=1).dropna()
        if aligned.empty:
            return 0.0
        return float((aligned["variant"] > aligned["baseline"]).mean())

    @staticmethod
    def yearly_split(returns: pd.Series) -> pd.DataFrame:
        return yearly_metrics(returns)
