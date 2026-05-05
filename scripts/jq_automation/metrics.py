from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .quota import load_ledger

# Chinese metric key -> stable English key
METRIC_KEY_MAP: dict[str, str] = {
    "策略收益": "total_return",
    "策略年化收益": "annual_return",
    "基准收益": "benchmark_return",
    "超额收益": "excess_return",
    "最大回撤": "max_drawdown",
    "最大回撤区间": "max_drawdown_period",
    "阿尔法": "alpha",
    "贝塔": "beta",
    "夏普比率": "sharpe",
    "索提诺比率": "sortino",
    "信息比率": "information_ratio",
    "策略波动率": "volatility",
    "基准波动率": "benchmark_volatility",
    "胜率": "win_ratio",
    "盈亏比": "profit_loss_ratio",
    "日胜率": "day_win_ratio",
    "盈利次数": "win_count",
    "亏损次数": "lose_count",
    "超额收益最大回撤": "excess_max_drawdown",
    "超额收益夏普比率": "excess_sharpe",
    "日均超额收益": "daily_excess_return",
}

# API export stats keys -> English key
API_STATS_KEY_MAP: dict[str, str] = {
    "total_return": "total_return",
    "annual_algo_return": "annual_return",
    "annual_bm_return": "benchmark_return",
    "excess_return": "excess_return",
    "max_drawdown": "max_drawdown",
    "alpha": "alpha",
    "beta": "beta",
    "sharpe": "sharpe",
    "sortino": "sortino",
    "information": "information_ratio",
    "algorithm_volatility": "volatility",
    "benchmark_volatility": "benchmark_volatility",
    "win_ratio": "win_ratio",
    "profit_loss_ratio": "profit_loss_ratio",
    "day_win_ratio": "day_win_ratio",
    "win_count": "win_count",
    "lose_count": "lose_count",
}

DEFAULT_METRICS: list[dict[str, str]] = [
    {"key": "annual_return", "direction": "maximize"},
    {"key": "excess_return", "direction": "maximize"},
    {"key": "max_drawdown", "direction": "minimize"},
    {"key": "sharpe", "direction": "maximize"},
    {"key": "actual_minutes", "direction": "minimize"},
]

METRIC_LABEL_CN: dict[str, str] = {
    "total_return": "策略收益",
    "annual_return": "策略年化收益",
    "benchmark_return": "基准收益",
    "excess_return": "超额收益",
    "max_drawdown": "最大回撤",
    "max_drawdown_period": "最大回撤区间",
    "alpha": "阿尔法",
    "beta": "贝塔",
    "sharpe": "夏普比率",
    "sortino": "索提诺比率",
    "information_ratio": "信息比率",
    "volatility": "策略波动率",
    "benchmark_volatility": "基准波动率",
    "win_ratio": "胜率",
    "profit_loss_ratio": "盈亏比",
    "day_win_ratio": "日胜率",
    "win_count": "盈利次数",
    "lose_count": "亏损次数",
    "excess_max_drawdown": "超额收益最大回撤",
    "excess_sharpe": "超额收益夏普比率",
    "daily_excess_return": "日均超额收益",
    "actual_minutes": "实际耗时(分)",
}


@dataclass
class VariantMetrics:
    label: str
    role: str
    is_baseline: bool
    metrics: dict[str, float | None]
    metadata: dict[str, Any]
    artifacts_present: dict[str, bool]  # has_backtest_report, has_strategy_analysis, has_performance_analysis
    issues: list[str] = field(default_factory=list)


def parse_metric_value(raw: Any) -> float | None:
    """Parse a metric value from JoinQuant's string representation.

    ``"18.06%"  -> 0.1806``
    ``"-1.841"  -> -1.841``
    ``0          -> 0.0``
    ``""         -> None``
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100.0
        return float(text)
    except ValueError:
        return None


def extract_from_summary_metrics(run_dir: Path) -> dict[str, float | None]:
    """Read and normalise ``summary_metrics.json`` to English-keyed float values."""
    path = run_dir / "summary_metrics.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, float | None] = {}
    for cn_key, eng_key in METRIC_KEY_MAP.items():
        if cn_key in raw:
            result[eng_key] = parse_metric_value(raw[cn_key])
    return result


def extract_from_api_stats(bundle_or_path: dict[str, Any] | Path) -> dict[str, float | None]:
    """Extract metrics from ``api_export.json`` stats section as a fallback."""
    if isinstance(bundle_or_path, Path):
        path = bundle_or_path
        if not path.is_file():
            return {}
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = bundle_or_path

    stats = {}
    if isinstance(raw, dict):
        stats = raw.get("stats", {}) or {}
    data = stats.get("data", {}) if isinstance(stats, dict) else {}

    result: dict[str, float | None] = {}
    for api_key, eng_key in API_STATS_KEY_MAP.items():
        value = data.get(api_key)
        if value is not None:
            parsed = parse_metric_value(value)
            if parsed is not None:
                result[eng_key] = parsed
    return result


def extract_from_metadata(run_dir: Path) -> dict[str, Any]:
    """Read core fields from ``metadata.json``."""
    path = run_dir / "metadata.json"
    if not path.is_file():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "backtest_id": raw.get("backtest_id", raw.get("backtestId")),
        "backtest_url": raw.get("backtest_url", raw.get("backtestUrl")),
        "strategy_name": raw.get("strategy_name"),
        "start_date": raw.get("start_date_effective"),
        "end_date": raw.get("end_date_effective"),
        "capital": raw.get("capital"),
        "params_snapshot": raw.get("params", {}),
        "extraction_method": raw.get("extraction_method"),
    }


def extract_actual_minutes(run_dir: Path, run_id: str) -> float | None:
    """Read actual consumed minutes from the quota ledger for a given run."""
    from .quota import ledger_path_for

    metadata = extract_from_metadata(run_dir)
    generated_at = metadata.get("generated_at")
    date_key = None
    if generated_at:
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(str(generated_at).replace("Z", "+00:00"))
            date_key = dt.strftime("%Y%m%d")
        except (ValueError, TypeError):
            pass

    ledger_path = ledger_path_for(date_key)
    ledger = load_ledger(ledger_path) if ledger_path.is_file() else load_ledger()
    for item in ledger.get("runs", []):
        if item.get("run_id") == run_id:
            actual = item.get("actual_minutes")
            if actual not in (None, ""):
                return float(actual)
            # Fall back to estimated_minutes if actual is unavailable
            est = item.get("estimated_minutes")
            if est not in (None, ""):
                return float(est)
    return None


def check_artifacts(run_dir: Path) -> dict[str, bool]:
    """Check which report artifacts exist for a run."""
    report_dir = run_dir / "report"
    return {
        "has_backtest_report": (report_dir / "backtest_report.md").is_file(),
        "has_strategy_analysis": (report_dir / "strategy-analysis.md").is_file(),
        "has_performance_analysis": (report_dir / "performance-analysis.md").is_file(),
    }


def collect_all_metrics(
    run_dir: Path,
    run_id: str,
    experiment_metrics: list[dict[str, str]] | None = None,
) -> VariantMetrics:
    """Collect and merge all metrics for a single backtest run.

    Returns a ``VariantMetrics`` with role and is_baseline left as placeholder
    values (caller should override from AB experiment data).
    """
    sm_metrics = extract_from_summary_metrics(run_dir)
    api_metrics = extract_from_api_stats(run_dir / "api_export.json")
    metadata = extract_from_metadata(run_dir)
    actual_min = extract_actual_minutes(run_dir, run_id)

    merged: dict[str, float | None] = {}
    keys = experiment_metrics or DEFAULT_METRICS
    metric_keys = {m["key"] for m in keys}
    metric_keys.add("actual_minutes")

    for key in metric_keys:
        # Prefer summary_metrics, fall back to api stats
        val = sm_metrics.get(key)
        if val is None:
            val = api_metrics.get(key)
        merged[key] = val

    if actual_min is not None:
        merged["actual_minutes"] = actual_min

    artifacts = check_artifacts(run_dir)

    return VariantMetrics(
        label="",
        role="",
        is_baseline=False,
        metrics=merged,
        metadata=metadata,
        artifacts_present=artifacts,
    )
