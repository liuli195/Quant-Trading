from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .layout import ResearchProjectLayout, ResearchRunLayout
from .spec import (
    BOOTSTRAP_BLOCK_SIZE,
    BOOTSTRAP_REPS,
    CROWD_THRESHOLD,
    CROWD_WINDOW,
    DISCOVERY_END,
    ETF_CODES,
    ETF_LABELS,
    FACTOR_SPECS,
    HORIZONS,
    PRIMARY_HORIZON,
    SCORE_END,
    SCORE_START,
    SEGMENTS,
    window_band,
)


@dataclass(frozen=True)
class PriceFrames:
    close: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    money: pd.DataFrame
    calendar: pd.DatetimeIndex


@dataclass(frozen=True)
class ResearchCache:
    anchors: pd.DataFrame
    forward: pd.DataFrame
    factor_values: dict[tuple[str, str, int], pd.Series]


def load_price_bundle(path: str | Path) -> PriceFrames:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    prices = payload.get("prices") or {}
    frames: dict[str, pd.DataFrame] = {}
    for field in ("close", "high", "low", "money"):
        series_map: dict[str, pd.Series] = {}
        for code in ETF_CODES:
            records = prices.get(code) or []
            if not records:
                continue
            frame = pd.DataFrame(records)
            if "date" not in frame.columns or field not in frame.columns:
                continue
            series = pd.Series(
                pd.to_numeric(frame[field], errors="coerce").values,
                index=pd.to_datetime(frame["date"]),
                name=code,
            )
            series_map[code] = series
        frames[field] = pd.DataFrame(series_map).sort_index().reindex(columns=ETF_CODES)

    calendar = pd.DatetimeIndex(pd.to_datetime(payload.get("calendar") or [])).sort_values()
    if len(calendar) == 0:
        calendar = frames["close"].index
    return PriceFrames(
        close=frames["close"],
        high=frames["high"],
        low=frames["low"],
        money=frames["money"],
        calendar=calendar,
    )


def first_trading_days_by_week(calendar: pd.DatetimeIndex, start: date, end: date) -> pd.DatetimeIndex:
    mask = (calendar.date >= start) & (calendar.date <= end)
    scoped = calendar[mask]
    if len(scoped) == 0:
        return scoped
    groups = pd.Series(scoped, index=scoped).groupby(scoped.to_period("W-SUN"))
    return pd.DatetimeIndex([group.iloc[0] for _, group in groups])


def _anchor_frame(calendar: pd.DatetimeIndex) -> pd.DataFrame:
    anchors = first_trading_days_by_week(calendar, SCORE_START, SCORE_END)
    rows = []
    for anchor in anchors:
        position = int(calendar.searchsorted(anchor))
        if position <= 0:
            continue
        row = {"signal_date": anchor, "asof_date": calendar[position - 1]}
        for horizon in HORIZONS:
            future_pos = position + horizon - 1
            row[f"future_{horizon}d"] = calendar[future_pos] if future_pos < len(calendar) else pd.NaT
        rows.append(row)
    return pd.DataFrame(rows)


def _forward_return_frame(close: pd.DataFrame, anchors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, anchor in anchors.iterrows():
        for code in ETF_CODES:
            record = {
                "signal_date": anchor["signal_date"],
                "asof_date": anchor["asof_date"],
                "etf": code,
            }
            base = close.at[anchor["asof_date"], code] if anchor["asof_date"] in close.index else np.nan
            for horizon in HORIZONS:
                future_date = anchor[f"future_{horizon}d"]
                if pd.isna(future_date) or future_date not in close.index or pd.isna(base):
                    record[f"forward_{horizon}d"] = np.nan
                else:
                    future_close = close.at[future_date, code]
                    record[f"forward_{horizon}d"] = future_close / base - 1 if pd.notna(future_close) else np.nan
            rows.append(record)
    return pd.DataFrame(rows)


def _rolling_percentile_rank(series: pd.Series, lookback: int = CROWD_WINDOW) -> pd.Series:
    def _rank(values: pd.Series) -> float:
        current = values.iloc[-1]
        valid = values.dropna()
        if len(valid) == 0 or pd.isna(current):
            return np.nan
        return float((valid.iloc[:-1] < current).mean()) if len(valid) > 1 else 0.5

    return series.rolling(lookback, min_periods=2).apply(_rank, raw=False)


def _factor_series(frames: PriceFrames, code: str, factor: str, window: int) -> pd.Series:
    close = frames.close[code]
    money = frames.money[code]
    if factor == "trend_gate":
        return (close > close.rolling(window).mean()).astype(float)
    if factor == "momentum_return":
        return close / close.shift(window) - 1
    if factor in {"crowd_ret_short", "crowd_ret_mid"}:
        return _rolling_percentile_rank(close / close.shift(window) - 1)
    if factor == "crowd_amount":
        return _rolling_percentile_rank(money.rolling(window).mean())
    if factor == "crowd_deviation":
        return _rolling_percentile_rank(close / close.rolling(window).mean() - 1)
    if factor == "crowd_volatility":
        return _rolling_percentile_rank(close.pct_change().rolling(window).std() * np.sqrt(252))
    raise ValueError(f"Unsupported factor: {factor}")


def _ordered_block_sample(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    if len(frame) == 0:
        return frame
    starts = rng.integers(0, max(len(frame) - BOOTSTRAP_BLOCK_SIZE + 1, 1), size=max(len(frame), 1))
    blocks = [frame.iloc[start : start + BOOTSTRAP_BLOCK_SIZE] for start in starts]
    return pd.concat(blocks, ignore_index=True).iloc[: len(frame)]


def _bootstrap_metric(
    frame: pd.DataFrame,
    metric_fn: Callable[[pd.DataFrame], float],
    *,
    reps: int = BOOTSTRAP_REPS,
) -> tuple[float, float, float]:
    clean = frame.dropna(subset=["factor_value", "forward_return"]).sort_values("signal_date")
    if len(clean) < 8 or reps <= 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(42)
    values = []
    for _ in range(reps):
        sampled = _ordered_block_sample(clean, rng)
        values.append(metric_fn(sampled))
    arr = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if len(arr) == 0:
        return np.nan, np.nan, np.nan
    return float(np.nanpercentile(arr, 2.5)), float(np.nanpercentile(arr, 97.5)), float(np.nanstd(arr, ddof=1))


def _trend_metric(frame: pd.DataFrame) -> dict[str, float]:
    on = frame[frame["factor_value"] >= 0.5]["forward_return"]
    off = frame[frame["factor_value"] < 0.5]["forward_return"]
    benefit = on.mean() - off.mean()
    return {
        "benefit": float(benefit),
        "state_a_mean": float(on.mean()),
        "state_b_mean": float(off.mean()),
        "state_a_count": int(on.count()),
        "state_b_count": int(off.count()),
        "secondary_metric": float((on > 0).mean() - (off > 0).mean()),
    }


def _momentum_metric(frame: pd.DataFrame) -> dict[str, float]:
    clean = frame.dropna(subset=["factor_value", "forward_return"])
    if len(clean) < 6:
        return {
            "benefit": np.nan,
            "state_a_mean": np.nan,
            "state_b_mean": np.nan,
            "state_a_count": 0,
            "state_b_count": 0,
            "secondary_metric": np.nan,
        }
    ranks = clean["factor_value"].rank(method="first")
    bucket = pd.qcut(ranks, 3, labels=["low", "mid", "high"])
    grouped = clean.assign(bucket=bucket).groupby("bucket", observed=False)["forward_return"]
    top = grouped.get_group("high") if "high" in grouped.groups else pd.Series(dtype=float)
    bottom = grouped.get_group("low") if "low" in grouped.groups else pd.Series(dtype=float)
    corr = clean["factor_value"].rank().corr(clean["forward_return"].rank())
    return {
        "benefit": float(top.mean() - bottom.mean()),
        "state_a_mean": float(top.mean()),
        "state_b_mean": float(bottom.mean()),
        "state_a_count": int(top.count()),
        "state_b_count": int(bottom.count()),
        "secondary_metric": float(corr),
    }


def _crowd_metric(frame: pd.DataFrame) -> dict[str, float]:
    high = frame[frame["factor_value"] >= CROWD_THRESHOLD]["forward_return"]
    normal = frame[frame["factor_value"] < CROWD_THRESHOLD]["forward_return"]
    benefit = normal.mean() - high.mean()
    return {
        "benefit": float(benefit),
        "state_a_mean": float(normal.mean()),
        "state_b_mean": float(high.mean()),
        "state_a_count": int(normal.count()),
        "state_b_count": int(high.count()),
        "secondary_metric": float((normal > 0).mean() - (high > 0).mean()),
    }


def _metric_fn_for_factor(factor: str) -> Callable[[pd.DataFrame], dict[str, float]]:
    if factor == "trend_gate":
        return _trend_metric
    if factor == "momentum_return":
        return _momentum_metric
    return _crowd_metric


def _subset_anchor_dates(anchors: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    return anchors[(anchors["signal_date"].dt.date >= start) & (anchors["signal_date"].dt.date <= end)].copy()


def build_research_cache(frames: PriceFrames) -> ResearchCache:
    anchors = _anchor_frame(frames.calendar)
    forward = _forward_return_frame(frames.close, anchors)
    factor_values = {
        (spec.factor, code, window): _factor_series(frames, code, spec.factor, window)
        for spec in FACTOR_SPECS
        for code in ETF_CODES
        for window in spec.windows
    }
    return ResearchCache(
        anchors=anchors,
        forward=forward,
        factor_values=factor_values,
    )


def build_factor_window_grid(
    frames: PriceFrames,
    period_start: date = SCORE_START,
    period_end: date = SCORE_END,
    horizons: tuple[int, ...] | None = None,
    bootstrap_horizons: tuple[int, ...] = (PRIMARY_HORIZON,),
    bootstrap_reps: int | None = None,
    cache: ResearchCache | None = None,
) -> pd.DataFrame:
    selected_horizons = horizons or HORIZONS
    selected_bootstrap_reps = BOOTSTRAP_REPS if bootstrap_reps is None else bootstrap_reps
    research_cache = cache or build_research_cache(frames)
    anchors = _subset_anchor_dates(research_cache.anchors, period_start, period_end)
    period_signal_dates = set(anchors["signal_date"])
    forward = research_cache.forward[research_cache.forward["signal_date"].isin(period_signal_dates)]
    rows: list[dict[str, object]] = []
    for spec in FACTOR_SPECS:
        metric_fn = _metric_fn_for_factor(spec.factor)
        for code in ETF_CODES:
            for window in spec.windows:
                factor_values = research_cache.factor_values[(spec.factor, code, window)]
                for horizon in selected_horizons:
                    etf_forward = forward[forward["etf"] == code][
                        ["signal_date", "asof_date", f"forward_{horizon}d"]
                    ].copy()
                    etf_forward = etf_forward.rename(columns={f"forward_{horizon}d": "forward_return"})
                    signal = etf_forward.copy()
                    signal["factor_value"] = signal["asof_date"].map(factor_values)
                    clean = signal.dropna(subset=["factor_value", "forward_return"])
                    metrics = metric_fn(clean)
                    if horizon in bootstrap_horizons and selected_bootstrap_reps > 0:
                        ci_low, ci_high, std_error = _bootstrap_metric(
                            clean,
                            lambda sample, fn=metric_fn: fn(sample)["benefit"],
                            reps=selected_bootstrap_reps,
                        )
                    else:
                        ci_low, ci_high, std_error = np.nan, np.nan, np.nan
                    rows.append(
                        {
                            "family": spec.family,
                            "factor": spec.factor,
                            "etf": code,
                            "etf_label": ETF_LABELS[code],
                            "window": window,
                            "window_band": window_band(window),
                            "horizon": horizon,
                            "sample_count": int(len(clean)),
                            "benefit": metrics["benefit"],
                            "state_a_mean": metrics["state_a_mean"],
                            "state_b_mean": metrics["state_b_mean"],
                            "state_a_count": metrics["state_a_count"],
                            "state_b_count": metrics["state_b_count"],
                            "secondary_metric": metrics["secondary_metric"],
                            "ci_low": ci_low,
                            "ci_high": ci_high,
                            "std_error": std_error,
                        }
                    )
    return pd.DataFrame(rows)


def _primary_horizon_view(grid: pd.DataFrame) -> pd.DataFrame:
    if "horizon" not in grid.columns:
        return grid
    return grid[grid["horizon"] == PRIMARY_HORIZON].copy()


def build_best_window_summary(grid: pd.DataFrame) -> pd.DataFrame:
    grid = _primary_horizon_view(grid)
    rows = []
    for (factor, etf), group in grid.groupby(["factor", "etf"], sort=True):
        ranked = group.sort_values(["benefit", "window"], ascending=[False, True])
        best = ranked.iloc[0]
        threshold = best["benefit"] - (best["std_error"] if pd.notna(best["std_error"]) else 0.0)
        stable = ranked[ranked["benefit"] >= threshold]["window"].astype(int).tolist()
        rows.append(
            {
                "factor": factor,
                "family": best["family"],
                "etf": etf,
                "etf_label": best["etf_label"],
                "best_window": int(best["window"]),
                "best_band": best["window_band"],
                "best_benefit": best["benefit"],
                "best_ci_low": best["ci_low"],
                "best_ci_high": best["ci_high"],
                "stable_windows_1se": ";".join(str(window) for window in stable),
            }
        )
    return pd.DataFrame(rows)


def build_pooled_vs_etf_specific(grid: pd.DataFrame) -> pd.DataFrame:
    grid = _primary_horizon_view(grid)
    rows = []
    for factor, group in grid.groupby("factor", sort=True):
        valid = group.dropna(subset=["benefit"])
        if valid.empty:
            rows.append(
                {
                    "factor": factor,
                    "family": group["family"].iloc[0],
                    "shared_window": np.nan,
                    "shared_mean_benefit": np.nan,
                    "etf_specific_mean_benefit": np.nan,
                    "specific_minus_shared": np.nan,
                    "specific_windows": "",
                }
            )
            continue
        pooled = valid.groupby("window", as_index=False)["benefit"].mean().sort_values(
            ["benefit", "window"], ascending=[False, True]
        )
        shared = pooled.iloc[0]
        specific = valid.loc[valid.groupby("etf")["benefit"].idxmax()]
        rows.append(
            {
                "factor": factor,
                "family": group["family"].iloc[0],
                "shared_window": int(shared["window"]),
                "shared_mean_benefit": shared["benefit"],
                "etf_specific_mean_benefit": specific["benefit"].mean(),
                "specific_minus_shared": specific["benefit"].mean() - shared["benefit"],
                "specific_windows": ";".join(
                    f"{row.etf_label}:{int(row.window)}" for row in specific.sort_values("etf_label").itertuples()
                ),
            }
        )
    return pd.DataFrame(rows)


def build_holdout_validation(frames: PriceFrames, cache: ResearchCache | None = None) -> pd.DataFrame:
    research_cache = cache or build_research_cache(frames)
    discovery = build_factor_window_grid(
        frames,
        SCORE_START,
        DISCOVERY_END,
        horizons=(PRIMARY_HORIZON,),
        bootstrap_horizons=(),
        bootstrap_reps=0,
        cache=research_cache,
    )
    holdout = build_factor_window_grid(
        frames,
        date(2025, 1, 1),
        SCORE_END,
        horizons=(PRIMARY_HORIZON,),
        bootstrap_horizons=(),
        bootstrap_reps=0,
        cache=research_cache,
    )
    discovery_best = build_best_window_summary(discovery)
    holdout = _primary_horizon_view(holdout)
    rows = []
    for best in discovery_best.itertuples():
        match = holdout[
            (holdout["factor"] == best.factor)
            & (holdout["etf"] == best.etf)
            & (holdout["window"] == best.best_window)
        ]
        holdout_row = match.iloc[0] if not match.empty else None
        rows.append(
            {
                "factor": best.factor,
                "family": best.family,
                "etf": best.etf,
                "etf_label": best.etf_label,
                "discovery_best_window": best.best_window,
                "discovery_best_band": best.best_band,
                "discovery_benefit": best.best_benefit,
                "holdout_benefit": np.nan if holdout_row is None else holdout_row["benefit"],
                "holdout_nonnegative": False
                if holdout_row is None or pd.isna(holdout_row["benefit"])
                else bool(holdout_row["benefit"] >= 0),
            }
        )
    return pd.DataFrame(rows)


def build_segment_stability(frames: PriceFrames, cache: ResearchCache | None = None) -> pd.DataFrame:
    research_cache = cache or build_research_cache(frames)
    rows = []
    for segment_name, (start, end) in SEGMENTS.items():
        if segment_name in {"discovery", "holdout"}:
            continue
        grid = build_factor_window_grid(
            frames,
            start,
            end,
            horizons=(PRIMARY_HORIZON,),
            bootstrap_horizons=(),
            bootstrap_reps=0,
            cache=research_cache,
        )
        best = build_best_window_summary(grid)
        best["segment"] = segment_name
        rows.append(best)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def build_bootstrap_summary(grid: pd.DataFrame) -> pd.DataFrame:
    return _primary_horizon_view(grid)[
        [
            "family",
            "factor",
            "etf",
            "etf_label",
            "window",
            "benefit",
            "ci_low",
            "ci_high",
            "std_error",
            "sample_count",
        ]
    ].copy()


def _percentile_rank(value: float, series: pd.Series) -> float:
    valid = series.dropna()
    if len(valid) == 0 or pd.isna(value):
        return 0.5
    return float((valid < value).mean())


def _default_trend_gates(frames: PriceFrames, asof: pd.Timestamp) -> np.ndarray:
    windows = {"159819.XSHE": 20, "513100.XSHG": 40, "518880.XSHG": 100}
    values = []
    for code in ETF_CODES:
        series = frames.close[code].loc[:asof].dropna()
        window = windows[code]
        gate = float(len(series) >= window and series.iloc[-1] > series.iloc[-window:].mean())
        values.append(gate)
    return np.asarray(values, dtype=float)


def _default_momentum_scores(frames: PriceFrames, asof: pd.Timestamp, gates: np.ndarray) -> np.ndarray:
    windows = (20, 60, 120)
    weights = (0.2, 0.3, 0.5)
    scores = np.zeros(len(ETF_CODES))
    active_codes = [code for idx, code in enumerate(ETF_CODES) if gates[idx] > 0]
    if not active_codes:
        return scores
    active_close = frames.close.loc[:asof, active_codes]
    if len(active_close) <= max(windows):
        return scores
    for window, weight in zip(windows, weights):
        ret = active_close.iloc[-1] / active_close.iloc[-(window + 1)] - 1
        ranks = ret.rank(pct=True).fillna(0.0)
        for idx, code in enumerate(ETF_CODES):
            scores[idx] += weight * float(ranks.get(code, 0.0))
    return scores


def _default_crowd_penalties(frames: PriceFrames, asof: pd.Timestamp) -> np.ndarray:
    close = frames.close.loc[:asof, ETF_CODES]
    money = frames.money.loc[:asof, ETF_CODES]
    penalties = np.ones(len(ETF_CODES))
    eligible_codes = [code for code in ETF_CODES if len(close[code].dropna()) >= CROWD_WINDOW]
    if not eligible_codes:
        return penalties

    recent_close = close[eligible_codes].iloc[-CROWD_WINDOW:]
    recent_money = money[eligible_codes].loc[money.index.intersection(recent_close.index)]
    ret20 = recent_close / recent_close.shift(20) - 1
    ret60 = recent_close / recent_close.shift(60) - 1
    amount_ma20 = recent_money.rolling(20).mean()
    deviation20 = recent_close / recent_close.rolling(20).mean() - 1
    vol20 = recent_close.pct_change().rolling(20).std() * np.sqrt(252)

    for idx, code in enumerate(ETF_CODES):
        if code not in eligible_codes:
            continue
        indicators = [
            _percentile_rank(ret20[code].dropna().iloc[-1], ret20[code].dropna()),
            _percentile_rank(ret60[code].dropna().iloc[-1], ret60[code].dropna()),
            _percentile_rank(amount_ma20[code].dropna().iloc[-1], amount_ma20[code].dropna()),
            _percentile_rank(deviation20[code].dropna().iloc[-1], deviation20[code].dropna()),
            _percentile_rank(vol20[code].dropna().iloc[-1], vol20[code].dropna()),
        ]
        score = float(np.nanmean(indicators))
        if score <= 0.60:
            penalties[idx] = 1.0
        elif score >= 0.95:
            penalties[idx] = 0.30
        else:
            penalties[idx] = 1 - (score - 0.60) / 0.35 * 0.70
    return penalties.astype(float)


def compare_default_signals(frames: PriceFrames, audit_log_path: str | Path) -> pd.DataFrame:
    events = []
    for line in Path(audit_log_path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if payload.get("event") == "rebalance_signals":
            events.append(payload)
    rows = []
    for event in events:
        signal_date = pd.Timestamp(event["current_dt"]).normalize()
        previous_date = pd.Timestamp(event["previous_date"]).normalize()
        gates = _default_trend_gates(frames, previous_date)
        momentum_scores = _default_momentum_scores(frames, previous_date, gates)
        crowd_penalties = _default_crowd_penalties(frames, previous_date)
        rows.append(
            {
                "signal_date": signal_date,
                "previous_date": previous_date,
                "trend_gate_max_abs_error": float(
                    np.max(np.abs(gates - np.asarray(event["trend_gates"], dtype=float)))
                ),
                "momentum_score_max_abs_error": float(
                    np.max(np.abs(momentum_scores - np.asarray(event["momentum_scores"], dtype=float)))
                ),
                "crowd_penalty_max_abs_error": float(
                    np.max(np.abs(crowd_penalties - np.asarray(event["crowd_penalties"], dtype=float)))
                ),
            }
        )
    return pd.DataFrame(rows)


def _markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_无可用记录。_"
    display = frame.copy()
    display = display.fillna("")
    headers = [str(column) for column in display.columns]
    rows = [[str(value) for value in row] for row in display.itertuples(index=False, name=None)]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def render_data_integrity(frames: PriceFrames) -> str:
    anchors = _anchor_frame(frames.calendar)
    forward = _forward_return_frame(frames.close, anchors)
    rows = []
    for code in ETF_CODES:
        close = frames.close[code]
        directional_shortfall = 0
        crowd_shortfall = 0
        for asof in anchors["asof_date"]:
            available = int(close.loc[:asof].dropna().shape[0])
            directional_shortfall += int(available < max(max(spec.windows) for spec in FACTOR_SPECS))
            crowd_shortfall += int(available < CROWD_WINDOW)
        rows.append(
            {
                "ETF": ETF_LABELS[code],
                "代码": code,
                "首日": "" if close.dropna().empty else close.dropna().index.min().date().isoformat(),
                "末日": "" if close.dropna().empty else close.dropna().index.max().date().isoformat(),
                "close缺失": int(close.isna().sum()),
                "high缺失": int(frames.high[code].isna().sum()),
                "low缺失": int(frames.low[code].isna().sum()),
                "money缺失": int(frames.money[code].isna().sum()),
                "最长方向窗不足": directional_shortfall,
                "拥挤分位预热不足": crowd_shortfall,
            }
        )
    frame = pd.DataFrame(rows)
    horizon_rows = []
    for horizon in HORIZONS:
        horizon_rows.append(
            {
                "horizon": horizon,
                "可用样本": int(forward[f"forward_{horizon}d"].notna().sum()),
                "尾部未成熟样本": int(forward[f"forward_{horizon}d"].isna().sum()),
            }
        )
    horizon_frame = pd.DataFrame(horizon_rows)
    return "\n".join(
        [
            "# 时间窗异质性研究数据完整性",
            "",
            f"- 交易日历条数：{len(frames.calendar)}",
            f"- 评分区间：`{SCORE_START.isoformat()} ~ {SCORE_END.isoformat()}`",
            "",
            _markdown_table(frame),
            "",
            "## 前向收益可用性",
            "",
            _markdown_table(horizon_frame),
            "",
        ]
    )


def render_default_signal_reproduction(compare: pd.DataFrame) -> str:
    summary = pd.DataFrame(
        [
            {
                "指标": column,
                "最大误差": compare[column].max() if not compare.empty else np.nan,
                "均值误差": compare[column].mean() if not compare.empty else np.nan,
            }
            for column in [
                "trend_gate_max_abs_error",
                "momentum_score_max_abs_error",
                "crowd_penalty_max_abs_error",
            ]
        ]
    )
    return "\n".join(
        [
            "# 默认信号复现对账",
            "",
            _markdown_table(summary),
            "",
            "判定：三项最大误差均应接近 0，才可继续解释后续窗口扫描结果。",
            "",
        ]
    )


def render_robustness_check(holdout: pd.DataFrame, segments: pd.DataFrame) -> str:
    segment_counts = (
        segments.groupby(["factor", "etf", "best_band"]).size().reset_index(name="count")
        if not segments.empty
        else pd.DataFrame()
    )
    holdout_ok = int(holdout["holdout_nonnegative"].sum()) if not holdout.empty else 0
    return "\n".join(
        [
            "# 时间窗异质性稳健性检查",
            "",
            f"- 留出集非负记录数：{holdout_ok}/{len(holdout)}",
            "",
            "## 留出集",
            "",
            _markdown_table(holdout),
            "",
            "## 分段最佳档位",
            "",
            _markdown_table(segment_counts),
            "",
        ]
    )


def render_validation_report(best: pd.DataFrame, pooled: pd.DataFrame, holdout: pd.DataFrame) -> str:
    family_hits = (
        pooled.assign(hit=pooled["specific_minus_shared"] > 0)
        .groupby("family", as_index=False)
        .agg(positive_factor_count=("hit", "sum"), factor_count=("hit", "count"))
    )
    return "\n".join(
        [
            "# ETF 时间窗异质性验证报告",
            "",
            "## 1. 研究结论概览",
            "",
            _markdown_table(family_hits),
            "",
            "## 2. 最佳窗口",
            "",
            _markdown_table(best),
            "",
            "## 3. 共享窗口 vs ETF 专属窗口",
            "",
            _markdown_table(pooled),
            "",
            "## 4. 留出集检查",
            "",
            _markdown_table(holdout),
            "",
            "说明：本报告只完成研究层验证；是否写回正式策略，仍需经过云端 A/B。",
            "",
        ]
    )


def _safe_name(value: str) -> str:
    return value.replace("/", "_").replace(" ", "_")


def write_analysis_outputs(
    output_dir: str | Path,
    frames: PriceFrames,
    grid: pd.DataFrame,
    best: pd.DataFrame,
    pooled: pd.DataFrame,
    holdout: pd.DataFrame,
    segments: pd.DataFrame,
    bootstrap: pd.DataFrame,
    default_compare: pd.DataFrame | None = None,
) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "window_response_curves").mkdir(exist_ok=True)

    (root / "data_integrity.md").write_text(render_data_integrity(frames), encoding="utf-8")
    grid.to_csv(root / "factor_window_grid.csv", index=False)
    best.to_csv(root / "best_window_summary.csv", index=False)
    pooled.to_csv(root / "pooled_vs_etf_specific.csv", index=False)
    holdout.to_csv(root / "holdout_validation.csv", index=False)
    segments.to_csv(root / "segment_stability.csv", index=False)
    bootstrap.to_csv(root / "bootstrap_summary.csv", index=False)
    (root / "robustness_check.md").write_text(render_robustness_check(holdout, segments), encoding="utf-8")
    (root / "window-heterogeneity-validation-report.md").write_text(
        render_validation_report(best, pooled, holdout),
        encoding="utf-8",
    )

    for factor, factor_frame in grid.groupby("factor", sort=True):
        factor_frame.to_csv(root / "window_response_curves" / f"{_safe_name(factor)}.csv", index=False)

    if default_compare is not None:
        default_compare.to_csv(root / "default_signal_reproduction.csv", index=False)
        (root / "default_signal_reproduction.md").write_text(
            render_default_signal_reproduction(default_compare),
            encoding="utf-8",
        )


def write_project_run_outputs(
    run_layout: ResearchRunLayout,
    *,
    frames: PriceFrames,
    grid: pd.DataFrame,
    best: pd.DataFrame,
    pooled: pd.DataFrame,
    holdout: pd.DataFrame,
    segments: pd.DataFrame,
    bootstrap: pd.DataFrame,
    raw_data_path: str | Path,
    audit_log_path: str | Path | None = None,
    default_compare: pd.DataFrame | None = None,
) -> None:
    run_layout.ensure_dirs()

    reports = run_layout.reports_dir
    tables = run_layout.tables_dir
    curves = run_layout.curves_dir

    (reports / "data_integrity.md").write_text(render_data_integrity(frames), encoding="utf-8")
    (reports / "robustness_check.md").write_text(render_robustness_check(holdout, segments), encoding="utf-8")
    (reports / "window-heterogeneity-validation-report.md").write_text(
        render_validation_report(best, pooled, holdout),
        encoding="utf-8",
    )

    grid.to_csv(tables / "factor_window_grid.csv", index=False)
    best.to_csv(tables / "best_window_summary.csv", index=False)
    pooled.to_csv(tables / "pooled_vs_etf_specific.csv", index=False)
    holdout.to_csv(tables / "holdout_validation.csv", index=False)
    segments.to_csv(tables / "segment_stability.csv", index=False)
    bootstrap.to_csv(tables / "bootstrap_summary.csv", index=False)

    for factor, factor_frame in grid.groupby("factor", sort=True):
        factor_frame.to_csv(curves / f"{_safe_name(factor)}.csv", index=False)

    if default_compare is not None:
        default_compare.to_csv(tables / "default_signal_reproduction.csv", index=False)
        (reports / "default_signal_reproduction.md").write_text(
            render_default_signal_reproduction(default_compare),
            encoding="utf-8",
        )

    manifest = {
        "schema_version": 1,
        "project": "etf_window_research",
        "run_id": run_layout.run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "raw_data": Path(raw_data_path).as_posix(),
            "audit_log": "" if audit_log_path is None else Path(audit_log_path).as_posix(),
        },
        "artifacts": {
            "reports": sorted(path.name for path in reports.iterdir() if path.is_file()),
            "tables": sorted(path.name for path in tables.iterdir() if path.is_file()),
            "curves": sorted(path.name for path in curves.iterdir() if path.is_file()),
        },
    }
    run_layout.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_analysis_tables(
    raw_data_path: str | Path,
    audit_log_path: str | Path | None = None,
) -> tuple[PriceFrames, dict[str, pd.DataFrame], pd.DataFrame | None]:
    frames = load_price_bundle(raw_data_path)
    cache = build_research_cache(frames)
    grid = build_factor_window_grid(frames, cache=cache)
    best = build_best_window_summary(grid)
    pooled = build_pooled_vs_etf_specific(grid)
    holdout = build_holdout_validation(frames, cache=cache)
    segments = build_segment_stability(frames, cache=cache)
    bootstrap = build_bootstrap_summary(grid)
    default_compare = compare_default_signals(frames, audit_log_path) if audit_log_path else None
    tables = {
        "grid": grid,
        "best": best,
        "pooled": pooled,
        "holdout": holdout,
        "segments": segments,
        "bootstrap": bootstrap,
        "default_compare": default_compare if default_compare is not None else pd.DataFrame(),
    }
    return frames, tables, default_compare


def analyze_bundle(
    raw_data_path: str | Path,
    output_dir: str | Path,
    audit_log_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    frames, tables, default_compare = _build_analysis_tables(raw_data_path, audit_log_path)
    write_analysis_outputs(
        output_dir=output_dir,
        frames=frames,
        grid=tables["grid"],
        best=tables["best"],
        pooled=tables["pooled"],
        holdout=tables["holdout"],
        segments=tables["segments"],
        bootstrap=tables["bootstrap"],
        default_compare=default_compare,
    )
    return tables


def analyze_project(
    project_dir: str | Path,
    run_id: str,
    raw_data_path: str | Path | None = None,
    audit_log_path: str | Path | None = None,
) -> dict[str, pd.DataFrame]:
    project = ResearchProjectLayout.from_path(project_dir)
    project.ensure_project_dirs()
    raw_path = Path(raw_data_path) if raw_data_path else project.raw_price_bundle_path()
    frames, tables, default_compare = _build_analysis_tables(raw_path, audit_log_path)
    write_project_run_outputs(
        project.run(run_id),
        frames=frames,
        grid=tables["grid"],
        best=tables["best"],
        pooled=tables["pooled"],
        holdout=tables["holdout"],
        segments=tables["segments"],
        bootstrap=tables["bootstrap"],
        raw_data_path=raw_path,
        audit_log_path=audit_log_path,
        default_compare=default_compare,
    )
    return tables

