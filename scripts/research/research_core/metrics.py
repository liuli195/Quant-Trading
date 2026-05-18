"""Performance metrics shared by local research projects."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pandas as pd


def parse_cumulative_returns_md(path: str | Path) -> pd.Series:
    """Parse a repository `daily_returns.md` file into daily returns."""

    dates: list[pd.Timestamp] = []
    cumulative: list[float] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        parts = [part.strip() for part in line.strip("| ").split("|")]
        if len(parts) < 2 or not parts[0].startswith("20"):
            continue
        try:
            dates.append(pd.Timestamp(parts[0]))
            cumulative.append(float(parts[1]))
        except ValueError:
            continue
    if not cumulative:
        return pd.Series(dtype=float)
    cum = np.asarray(cumulative, dtype=float)
    daily = np.empty_like(cum)
    daily[0] = cum[0]
    daily[1:] = (1.0 + cum[1:]) / (1.0 + cum[:-1]) - 1.0
    return pd.Series(daily, index=pd.DatetimeIndex(dates), name="daily_return")


def performance_metrics(returns: pd.Series | np.ndarray) -> dict[str, float]:
    """Compute compact strategy metrics from daily returns."""

    series = pd.Series(returns, dtype=float).dropna()
    if series.empty:
        return {
            "total_return": 0.0,
            "annual_return": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
        }
    wealth = (1.0 + series).cumprod()
    total_return = float(wealth.iloc[-1] - 1.0)
    annual_return = float((1.0 + total_return) ** (252.0 / len(series)) - 1.0)
    volatility = float(series.std(ddof=1) * np.sqrt(252)) if len(series) > 1 else 0.0
    sharpe = float(series.mean() / series.std(ddof=1) * np.sqrt(252)) if volatility > 0 else 0.0
    max_drawdown = float((wealth / wealth.cummax() - 1.0).min())
    return {
        "total_return": total_return,
        "annual_return": annual_return,
        "volatility": volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
    }


def paired_block_bootstrap(
    lhs: pd.Series | np.ndarray,
    rhs: pd.Series | np.ndarray,
    *,
    n_boot: int = 2000,
    block: int = 40,
    seed: int = 42,
) -> dict[str, float]:
    """Bootstrap paired mean-return differences as `rhs - lhs`."""

    left = np.asarray(lhs, dtype=float)
    right = np.asarray(rhs, dtype=float)
    if len(left) != len(right):
        raise ValueError("paired series must have the same length")
    diff = right - left
    n = len(diff)
    if n == 0:
        raise ValueError("paired series must not be empty")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    means = np.empty(n_boot)
    for idx in range(n_boot):
        block_ids = rng.integers(0, n_blocks, size=n_blocks)
        sample = np.concatenate(
            [diff[b * block : min((b + 1) * block, n)] for b in block_ids]
        )[:n]
        means[idx] = float(np.mean(sample))
    observed = float(np.mean(diff))
    if observed >= 0:
        p_value = float((np.sum(means <= 0) + 1) / (n_boot + 1))
    else:
        p_value = float((np.sum(means >= 0) + 1) / (n_boot + 1))
    return {
        "observed": observed,
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
        "p_value": p_value,
    }


def rolling_sharpe(returns: pd.Series | np.ndarray, window: int = 252) -> pd.Series:
    """Compute rolling annualized Sharpe."""

    series = pd.Series(returns, dtype=float)
    rolling_mean = series.rolling(window).mean()
    rolling_std = series.rolling(window).std(ddof=1)
    return rolling_mean / rolling_std * np.sqrt(252)


def yearly_metrics(returns: pd.Series) -> pd.DataFrame:
    """Compute one metrics row per calendar year."""

    if not isinstance(returns.index, pd.DatetimeIndex):
        raise TypeError("returns must use a DatetimeIndex")
    rows = []
    for year, group in returns.groupby(returns.index.year):
        metrics = performance_metrics(group)
        rows.append({"year": int(year), "days": int(group.notna().sum()), **metrics})
    return pd.DataFrame(rows)


class MetricToolkit:
    """Facade for common performance metrics."""

    @staticmethod
    def summary(returns: pd.Series | np.ndarray) -> dict[str, float]:
        return performance_metrics(returns)

    @staticmethod
    def annual_return(returns: pd.Series | np.ndarray) -> float:
        return performance_metrics(returns)["annual_return"]

    @staticmethod
    def max_drawdown(returns: pd.Series | np.ndarray) -> float:
        return performance_metrics(returns)["max_drawdown"]

    @staticmethod
    def sharpe(returns: pd.Series | np.ndarray) -> float:
        return performance_metrics(returns)["sharpe"]

    @staticmethod
    def volatility(returns: pd.Series | np.ndarray) -> float:
        return performance_metrics(returns)["volatility"]

    @staticmethod
    def rolling_sharpe(returns: pd.Series | np.ndarray, window: int = 252) -> pd.Series:
        return rolling_sharpe(returns, window=window)

    @staticmethod
    def yearly(returns: pd.Series) -> pd.DataFrame:
        return yearly_metrics(returns)
