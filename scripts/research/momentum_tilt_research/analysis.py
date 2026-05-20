"""Project analysis workflow for the momentum-tilt follow-up study."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from scripts.research.research_core.audit import load_rebalance_events, load_run_start_params
from scripts.research.research_core.calendar import forward_return_frame
from scripts.research.research_core.layout import ResearchProjectLayout, ResearchRunLayout
from scripts.research.research_core.metrics import (
    paired_block_bootstrap,
    parse_cumulative_returns_md,
    performance_metrics,
    rolling_sharpe,
    yearly_metrics,
)
from scripts.research.research_core.pointers import read_json_object
from scripts.research.research_core.prices import PriceFrames, load_price_bundle
from scripts.research.research_core.reporting import markdown_table, write_json

from .replay import (
    ReplayResult,
    VariantSpec,
    event_weight_frame,
    expand_weight_schedule,
    replay_variant,
    summarize_variant_vs_baseline,
)
from .spec import (
    BASELINE_RUN_ID,
    CALIBRATION_TOLERANCES,
    DISCOVERY,
    ETF_CODES,
    ETF_LABELS,
    EXTREME_090_RUN_ID,
    HORIZONS,
    HOLDOUT,
    LINEAR_025_RUN_ID,
    LINEAR_STRENGTHS,
    PRIMARY_HORIZON,
    SCORE_BIN_WIDTH,
    SCORE_END,
    SCORE_START,
    STRATEGY,
    YEAR_SEGMENTS,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_project_dir() -> Path:
    return _repo_root() / "strategies" / STRATEGY / "reports" / "momentum_tilt"


def default_raw_price_path() -> Path:
    return (
        _repo_root()
        / "strategies"
        / STRATEGY
        / "reports"
        / "research"
        / "window_heterogeneity"
        / "inputs"
        / "raw"
        / "etf_window_research_prices.json"
    )


def backtest_run_dir(run_id: str) -> Path:
    return _repo_root() / "strategies" / STRATEGY / "backtest_runs" / run_id


def default_audit_log_path() -> Path:
    return backtest_run_dir(BASELINE_RUN_ID) / "tabs_raw" / "audit_log.jsonl"


def default_baseline_returns_path() -> Path:
    return backtest_run_dir(BASELINE_RUN_ID) / "tabs_raw" / "daily_returns.md"


def _segment_name(ts: pd.Timestamp) -> str:
    value = ts.date()
    if DISCOVERY[0] <= value <= DISCOVERY[1]:
        return "discovery"
    if HOLDOUT[0] <= value <= HOLDOUT[1]:
        return "holdout"
    return "outside"


def _events_to_signal_frame(events: list[dict]) -> pd.DataFrame:
    rows = []
    for event in events:
        signal_date = pd.Timestamp(event["current_dt"]).normalize()
        previous_date = pd.Timestamp(event["previous_date"]).normalize()
        for code, score, gate, tilt in zip(
            event["pool"],
            event["momentum_scores"],
            event["trend_gates"],
            event["momentum_tilts"],
            strict=True,
        ):
            rows.append(
                {
                    "signal_date": signal_date,
                    "asof_date": previous_date,
                    "etf": code,
                    "etf_label": ETF_LABELS.get(code, code),
                    "momentum_score": float(score),
                    "trend_gate": float(gate),
                    "baseline_tilt": float(tilt),
                    "segment": _segment_name(signal_date),
                }
            )
    return pd.DataFrame(rows)


def _event_anchor_frame(events: list[dict], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    for event in events:
        signal_date = pd.Timestamp(event["current_dt"]).normalize()
        position = int(calendar.searchsorted(signal_date))
        row = {
            "signal_date": signal_date,
            "asof_date": pd.Timestamp(event["previous_date"]).normalize(),
        }
        for horizon in HORIZONS:
            future_pos = position + horizon - 1
            row[f"future_{horizon}d"] = calendar[future_pos] if future_pos < len(calendar) else pd.NaT
        rows.append(row)
    return pd.DataFrame(rows)


def build_response_samples(events: list[dict], frames: PriceFrames) -> pd.DataFrame:
    """Join active weekly signals with forward ETF returns."""

    signals = _events_to_signal_frame(events)
    anchors = _event_anchor_frame(events, frames.calendar)
    forward = forward_return_frame(frames.close, anchors, HORIZONS, codes=ETF_CODES)
    samples = signals.merge(forward, on=["signal_date", "asof_date", "etf"], how="left")
    samples = samples[samples["trend_gate"] > 0].copy()
    bins = np.arange(0.0, 1.0 + SCORE_BIN_WIDTH + 1e-9, SCORE_BIN_WIDTH)
    samples["score_bucket"] = pd.cut(
        samples["momentum_score"],
        bins=bins,
        include_lowest=True,
        right=False,
    )
    samples["score_bucket_start"] = samples["score_bucket"].map(
        lambda interval: np.nan if pd.isna(interval) else float(interval.left)
    )
    samples["score_zone"] = np.select(
        [
            samples["momentum_score"] < 0.50,
            samples["momentum_score"] < 0.90,
        ],
        ["low", "mid"],
        default="high",
    )
    return samples


def build_response_curve(samples: pd.DataFrame) -> pd.DataFrame:
    """Aggregate response curves by segment, ETF, and score bucket."""

    value_cols = [f"forward_{horizon}d" for horizon in HORIZONS]
    grouped = (
        samples.groupby(
            ["segment", "etf", "etf_label", "score_bucket_start"],
            dropna=False,
            observed=False,
        )[value_cols]
        .agg(["count", "mean"])
        .reset_index()
    )
    grouped.columns = [
        "_".join(part for part in col if part).rstrip("_")
        if isinstance(col, tuple)
        else col
        for col in grouped.columns
    ]
    return grouped


def build_zone_summary(samples: pd.DataFrame) -> pd.DataFrame:
    """Summarize low/mid/high zones for gating and reports."""

    value_cols = [f"forward_{horizon}d" for horizon in HORIZONS]
    melted = samples.melt(
        id_vars=["segment", "etf", "etf_label", "score_zone"],
        value_vars=value_cols,
        var_name="horizon",
        value_name="forward_return",
    ).dropna(subset=["forward_return"])
    melted["horizon"] = melted["horizon"].str.extract(r"(\d+)").astype(int)
    return (
        melted.groupby(["segment", "etf", "etf_label", "score_zone"], observed=False)
        .agg(
            sample_count=("forward_return", "size"),
            mean_forward_return=("forward_return", "mean"),
        )
        .reset_index()
    )


def evaluate_phase1_gate(zone_summary: pd.DataFrame) -> dict[str, object]:
    """Check whether mid-zone returns beat high-zone returns in both splits."""

    global_rows = (
        zone_summary.groupby(["segment", "score_zone"], observed=False)["mean_forward_return"]
        .mean()
        .reset_index()
        .pivot(index="segment", columns="score_zone", values="mean_forward_return")
    )
    discovery_edge = (
        float(global_rows.loc["discovery", "mid"] - global_rows.loc["discovery", "high"])
        if {"discovery"}.issubset(global_rows.index)
        and {"mid", "high"}.issubset(global_rows.columns)
        else np.nan
    )
    holdout_edge = (
        float(global_rows.loc["holdout", "mid"] - global_rows.loc["holdout", "high"])
        if {"holdout"}.issubset(global_rows.index)
        and {"mid", "high"}.issubset(global_rows.columns)
        else np.nan
    )
    per_etf = []
    pivot = zone_summary.pivot_table(
        index=["segment", "etf", "etf_label"],
        columns="score_zone",
        values="mean_forward_return",
        observed=False,
    ).reset_index()
    for _, row in pivot.iterrows():
        if row["segment"] not in {"discovery", "holdout"}:
            continue
        per_etf.append(
            {
                "segment": row["segment"],
                "etf": row["etf"],
                "etf_label": row["etf_label"],
                "mid_minus_high": float(row.get("mid", np.nan) - row.get("high", np.nan)),
            }
        )
    return {
        "passed": bool(pd.notna(discovery_edge) and pd.notna(holdout_edge) and discovery_edge > 0 and holdout_edge > 0),
        "discovery_mid_minus_high": discovery_edge,
        "holdout_mid_minus_high": holdout_edge,
        "per_etf": per_etf,
    }


def _format_bp(value: float) -> str:
    return f"{value * 10000:+.1f}"


def _write_svg_curve(path: Path, curve: pd.DataFrame, title: str) -> None:
    usable = curve.dropna(subset=["score_bucket_start", f"forward_{PRIMARY_HORIZON}d_mean"])
    if usable.empty:
        return
    xs = usable["score_bucket_start"].to_numpy(dtype=float)
    ys = usable[f"forward_{PRIMARY_HORIZON}d_mean"].to_numpy(dtype=float) * 10000
    width, height = 640, 320
    pad_x, pad_y = 48, 36
    x_min, x_max = 0.0, 1.0
    y_min = float(min(np.nanmin(ys), 0.0))
    y_max = float(max(np.nanmax(ys), 0.0))
    if y_min == y_max:
        y_min -= 1
        y_max += 1

    def sx(value: float) -> float:
        return pad_x + (value - x_min) / (x_max - x_min) * (width - 2 * pad_x)

    def sy(value: float) -> float:
        return height - pad_y - (value - y_min) / (y_max - y_min) * (height - 2 * pad_y)

    points = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in zip(xs, ys, strict=True))
    zero_y = sy(0.0)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="{width}" height="{height}" fill="white"/>
<text x="{pad_x}" y="22" font-size="16" font-family="Arial">{title}</text>
<line x1="{pad_x}" y1="{zero_y:.1f}" x2="{width-pad_x}" y2="{zero_y:.1f}" stroke="#999" stroke-width="1"/>
<line x1="{pad_x}" y1="{pad_y}" x2="{pad_x}" y2="{height-pad_y}" stroke="#333" stroke-width="1"/>
<line x1="{pad_x}" y1="{height-pad_y}" x2="{width-pad_x}" y2="{height-pad_y}" stroke="#333" stroke-width="1"/>
<polyline fill="none" stroke="#176d81" stroke-width="2.5" points="{points}"/>
<text x="{pad_x}" y="{height-10}" font-size="12" font-family="Arial">MomentumScore</text>
<text x="{width-pad_x-40}" y="{height-10}" font-size="12" font-family="Arial">1.0</text>
<text x="8" y="{pad_y}" font-size="12" font-family="Arial">{y_max:.1f} bp</text>
<text x="8" y="{height-pad_y}" font-size="12" font-family="Arial">{y_min:.1f} bp</text>
</svg>
"""
    path.write_text(svg, encoding="utf-8")


def write_phase0_outputs(
    run: ResearchRunLayout,
    *,
    audit_log_path: Path,
    raw_price_path: Path,
    baseline_returns_path: Path,
    events: list[dict],
    params: dict,
) -> None:
    """Persist baseline freeze and split definitions."""

    run.reports_dir.mkdir(parents=True, exist_ok=True)
    metrics = performance_metrics(parse_cumulative_returns_md(baseline_returns_path))
    baseline_lines = [
        "# 基线快照",
        "",
        f"- **baseline run**: `{BASELINE_RUN_ID}`",
        f"- **审计日志**: [audit_log.jsonl](../../../../../backtest_runs/{BASELINE_RUN_ID}/tabs_raw/audit_log.jsonl) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id={BASELINE_RUN_ID})/audit_log.jsonl -->",
        "- **原始行情**: [etf_window_research_prices.json](../../../../window_heterogeneity/inputs/raw/etf_window_research_prices.json) <!-- pathref: strategy_research_project_raw_inputs(strategy=etf_factor_rotation, project=window_heterogeneity)/etf_window_research_prices.json -->",
        f"- **日收益**: [daily_returns.md](../../../../../backtest_runs/{BASELINE_RUN_ID}/tabs_raw/daily_returns.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id={BASELINE_RUN_ID})/daily_returns.md -->",
        f"- **信号周数**: `{len(events)}`",
        "",
        "## 当前正式参数",
        "",
        markdown_table(
            pd.DataFrame(
                [
                    {"参数": key, "值": params[key]}
                    for key in [
                        "MomentumTiltStrength",
                        "MomentumTiltMin",
                        "MomentumTiltMax",
                        "MomentumExtremeScoreStart",
                        "MomentumExtremeTiltCap",
                    ]
                ]
            )
        ),
        "",
        "## baseline 指标",
        "",
        markdown_table(
            pd.DataFrame(
                [
                    {
                        "总收益": f"{metrics['total_return']:.2%}",
                        "年化": f"{metrics['annual_return']:.2%}",
                        "Sharpe": f"{metrics['sharpe']:.3f}",
                        "最大回撤": f"{abs(metrics['max_drawdown']):.2%}",
                    }
                ]
            )
        ),
        "",
    ]
    (run.reports_dir / "baseline_snapshot.md").write_text("\n".join(baseline_lines), encoding="utf-8")

    split_frame = pd.DataFrame(
        [
            {"切片": "discovery", "起始": DISCOVERY[0], "结束": DISCOVERY[1]},
            {"切片": "holdout", "起始": HOLDOUT[0], "结束": HOLDOUT[1]},
            *[
                {"切片": label, "起始": start, "结束": end}
                for label, start, end in YEAR_SEGMENTS
            ],
        ]
    )
    sample_lines = [
        "# 样本切分",
        "",
        markdown_table(split_frame),
        "",
        "- 所有后续响应曲线、replay 与稳健性验证统一使用该切分。",
        "- 预热历史只用于信号计算，不纳入评分区间。",
        "",
    ]
    (run.reports_dir / "sample_split.md").write_text("\n".join(sample_lines), encoding="utf-8")


def write_phase1_outputs(
    run: ResearchRunLayout,
    samples: pd.DataFrame,
    curve: pd.DataFrame,
    zone_summary: pd.DataFrame,
    gate: dict[str, object],
) -> None:
    """Persist response-curve research outputs."""

    curve.to_csv(run.tables_dir / "momentum_response_curve.csv", index=False)
    zone_summary.to_csv(run.tables_dir / "momentum_zone_summary.csv", index=False)

    summary = zone_summary.copy()
    summary["mean_forward_bp"] = summary["mean_forward_return"].map(lambda value: round(value * 10000, 1))
    summary = summary.drop(columns=["mean_forward_return"])
    report_lines = [
        "# 动量响应曲线",
        "",
        f"- **活跃样本数**: `{len(samples)}`",
        f"- **主观察 horizon**: `{PRIMARY_HORIZON}d`",
        f"- **Phase 1 gate**: `{'通过' if gate['passed'] else '未通过'}`",
        f"- **discovery 中段 - 高段**: `{_format_bp(float(gate['discovery_mid_minus_high']))} bp`",
        f"- **holdout 中段 - 高段**: `{_format_bp(float(gate['holdout_mid_minus_high']))} bp`",
        "",
        "## 分区摘要",
        "",
        markdown_table(summary),
        "",
        "## 解读",
        "",
        "- `mid` 定义为 `0.50 <= score < 0.90`，`high` 定义为 `score >= 0.90`。",
        "- Phase 1 gate 只有在 discovery 与 holdout 的全局 `mid - high` 都为正时通过。",
        "",
    ]
    (run.reports_dir / "momentum_response_curve.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    all_curve = curve[curve["segment"] == "discovery"].copy()
    for code, label in ETF_LABELS.items():
        _write_svg_curve(
            run.curves_dir / f"momentum_response_{label.lower()}.svg",
            all_curve[all_curve["etf"] == code],
            f"{label} {PRIMARY_HORIZON}d response",
        )


def _parse_cloud_summary(run_id: str) -> dict[str, float]:
    raw = read_json_object(backtest_run_dir(run_id) / "summary_metrics.json")
    return {
        "annual_return": float(str(raw["策略年化收益"]).rstrip("%")) / 100,
        "sharpe": float(raw["夏普比率"]),
        "max_drawdown": -float(str(raw["最大回撤"]).rstrip("%")) / 100,
    }


def _anchor_metrics(
    local_metrics: dict[str, float],
    *,
    local_baseline: dict[str, float],
    cloud_baseline: dict[str, float],
) -> dict[str, float]:
    """Anchor local relative deltas onto cloud absolute metrics."""

    anchored = dict(local_metrics)
    for key in ["annual_return", "sharpe", "max_drawdown"]:
        anchored[key] = cloud_baseline[key] + (local_metrics[key] - local_baseline[key])
    return anchored


def calibrate_replay(
    events: list[dict],
    frames: PriceFrames,
    baseline_returns: pd.Series,
) -> dict[str, object]:
    """Validate the local replay against already-known cloud variants."""

    baseline_cloud = _parse_cloud_summary(BASELINE_RUN_ID)
    local_baseline = performance_metrics(baseline_returns)
    baseline_path_pass = all(
        [
            abs(local_baseline["annual_return"] - baseline_cloud["annual_return"])
            <= CALIBRATION_TOLERANCES["annual_return_abs"],
            abs(local_baseline["max_drawdown"] - baseline_cloud["max_drawdown"])
            <= CALIBRATION_TOLERANCES["max_drawdown_abs"],
        ]
    )
    linear_result = replay_variant(
        events,
        frames.close.reindex(columns=list(ETF_CODES)),
        baseline_returns,
        VariantSpec(label="linear-025", strength=0.25),
    )
    extreme_result = replay_variant(
        events,
        frames.close.reindex(columns=list(ETF_CODES)),
        baseline_returns,
        VariantSpec(
            label="extreme-neutral-090",
            strength=0.50,
            shape="plateau",
            extreme_start=0.90,
            extreme_cap=1.0,
        ),
    )
    cloud_linear = _parse_cloud_summary(LINEAR_025_RUN_ID)
    cloud_extreme = _parse_cloud_summary(EXTREME_090_RUN_ID)
    local_baseline_anchored = _anchor_metrics(
        local_baseline,
        local_baseline=local_baseline,
        cloud_baseline=baseline_cloud,
    )
    local_linear_anchored = _anchor_metrics(
        linear_result.metrics,
        local_baseline=local_baseline,
        cloud_baseline=baseline_cloud,
    )
    local_extreme_anchored = _anchor_metrics(
        extreme_result.metrics,
        local_baseline=local_baseline,
        cloud_baseline=baseline_cloud,
    )
    replay_order = (
        local_linear_anchored["sharpe"]
        > local_extreme_anchored["sharpe"]
        > local_baseline_anchored["sharpe"]
    )
    cloud_order = cloud_linear["sharpe"] > cloud_extreme["sharpe"] > baseline_cloud["sharpe"]
    direction_pass = all(
        [
            local_linear_anchored["annual_return"] > local_baseline_anchored["annual_return"],
            local_extreme_anchored["annual_return"] > local_baseline_anchored["annual_return"],
            local_linear_anchored["sharpe"] > local_baseline_anchored["sharpe"],
            local_extreme_anchored["sharpe"] > local_baseline_anchored["sharpe"],
        ]
    )
    known_variant_pass = all(
        [
            abs(local_linear_anchored["annual_return"] - cloud_linear["annual_return"])
            <= CALIBRATION_TOLERANCES["annual_return_abs"],
            abs(local_linear_anchored["sharpe"] - cloud_linear["sharpe"])
            <= CALIBRATION_TOLERANCES["sharpe_abs"],
            abs(local_linear_anchored["max_drawdown"] - cloud_linear["max_drawdown"])
            <= CALIBRATION_TOLERANCES["max_drawdown_abs"],
            abs(local_extreme_anchored["annual_return"] - cloud_extreme["annual_return"])
            <= CALIBRATION_TOLERANCES["annual_return_abs"],
            abs(local_extreme_anchored["sharpe"] - cloud_extreme["sharpe"])
            <= CALIBRATION_TOLERANCES["sharpe_abs"],
            abs(local_extreme_anchored["max_drawdown"] - cloud_extreme["max_drawdown"])
            <= CALIBRATION_TOLERANCES["max_drawdown_abs"],
        ]
    )
    return {
        "passed": bool(baseline_path_pass and known_variant_pass and replay_order and cloud_order and direction_pass),
        "baseline_path_pass": bool(baseline_path_pass),
        "known_variant_pass": bool(known_variant_pass),
        "relative_order_pass": bool(replay_order and cloud_order),
        "direction_pass": bool(direction_pass),
        "baseline_cloud": baseline_cloud,
        "baseline_local_raw": local_baseline,
        "baseline_local": local_baseline_anchored,
        "linear_025_local_raw": linear_result.metrics,
        "linear_025_local": local_linear_anchored,
        "extreme_090_local_raw": extreme_result.metrics,
        "extreme_090_local": local_extreme_anchored,
        "linear_025_cloud": cloud_linear,
        "extreme_090_cloud": cloud_extreme,
    }


def write_calibration_outputs(run: ResearchRunLayout, calibration: dict[str, object]) -> None:
    write_json(run.tables_dir / "replay_calibration.json", calibration)
    rows = []
    for label in ["baseline", "linear_025", "extreme_090"]:
        local = calibration[f"{label}_local"]
        cloud = calibration[f"{label}_cloud"]
        rows.append(
            {
                "variant": label,
                "local_annual": f"{local['annual_return']:.2%}",
                "cloud_annual": f"{cloud['annual_return']:.2%}",
                "local_sharpe": f"{local['sharpe']:.3f}",
                "cloud_sharpe": f"{cloud['sharpe']:.3f}",
                "local_mdd": f"{abs(local['max_drawdown']):.2%}",
                "cloud_mdd": f"{abs(cloud['max_drawdown']):.2%}",
            }
        )
    lines = [
        "# Replay 校准",
        "",
        f"- **整体结论**: `{'通过' if calibration['passed'] else '未通过'}`",
        f"- **baseline 路径**: `{'通过' if calibration['baseline_path_pass'] else '未通过'}`",
        f"- **已知变体绝对误差**: `{'通过' if calibration['known_variant_pass'] else '未通过'}`",
        f"- **已知变体排序**: `{'通过' if calibration['relative_order_pass'] else '未通过'}`",
        f"- **改善方向**: `{'通过' if calibration['direction_pass'] else '未通过'}`",
        "",
        markdown_table(pd.DataFrame(rows)),
        "",
        "说明：本地 replay 以云端 baseline 的真实日收益为锚，只估计不同动量倾斜带来的相对差异；",
        "绝对年化、Sharpe、回撤通过 baseline 云端指标做锚定，避免把聚宽内部 Sharpe 口径差异误判为 replay 失真。",
        "",
    ]
    (run.reports_dir / "replay_calibration.md").write_text("\n".join(lines), encoding="utf-8")


def _linear_variants() -> list[VariantSpec]:
    return [VariantSpec(label=f"linear-{int(strength * 100):03d}", strength=strength) for strength in LINEAR_STRENGTHS]


def _shape_variants(best_strength: float) -> list[VariantSpec]:
    return [
        VariantSpec(label="plateau-090", strength=0.50, shape="plateau", extreme_start=0.90, extreme_cap=1.0),
        VariantSpec(
            label="plateau-090-on-best-linear",
            strength=best_strength,
            shape="plateau",
            extreme_start=0.90,
            extreme_cap=1.0,
        ),
        VariantSpec(
            label="soft-shoulder-090",
            strength=best_strength,
            shape="soft_shoulder",
            extreme_start=0.90,
            extreme_cap=1.0,
        ),
    ]


def _variant_signal_stats(events: list[dict], spec: VariantSpec) -> dict[str, float]:
    baseline_weights = event_weight_frame(events)
    variant_weights = event_weight_frame(events, spec)
    delta = variant_weights.drop(columns=["signal_date"]) - baseline_weights.drop(columns=["signal_date"])
    return {
        "mean_abs_weight_delta": float(delta.abs().to_numpy().mean()),
        "max_abs_weight_delta": float(delta.abs().to_numpy().max()),
    }


def build_phase2_scan(
    events: list[dict],
    frames: PriceFrames,
    baseline_returns: pd.Series,
    calibration: dict[str, object],
) -> tuple[pd.DataFrame, list[ReplayResult]]:
    """Build the strength scan, with metrics gated by replay calibration."""

    rows = []
    results: list[ReplayResult] = []
    baseline_local_raw = calibration["baseline_local_raw"]
    baseline_cloud = calibration["baseline_cloud"]
    for spec in _linear_variants():
        signal_stats = _variant_signal_stats(events, spec)
        row = {"variant": spec.label, "strength": spec.strength, **signal_stats}
        if calibration["passed"]:
            result = replay_variant(events, frames.close.reindex(columns=list(ETF_CODES)), baseline_returns, spec)
            summary = summarize_variant_vs_baseline(baseline_returns, result)
            anchored_metrics = _anchor_metrics(
                result.metrics,
                local_baseline=baseline_local_raw,
                cloud_baseline=baseline_cloud,
            )
            row.update({**anchored_metrics, **summary, "metrics_status": "available"})
            results.append(result)
        else:
            row["metrics_status"] = "blocked_replay_not_calibrated"
        rows.append(row)
    return pd.DataFrame(rows), results


def evaluate_phase2_gate(scan: pd.DataFrame) -> dict[str, object]:
    """Decide whether local evidence supports a cloud batch A."""

    available = scan[scan["metrics_status"] == "available"].copy()
    if available.empty:
        return {"passed": False, "reason": "replay_not_calibrated"}
    baseline = available.loc[available["variant"] == "linear-050"].iloc[0]
    candidates = available[available["variant"] != "linear-050"]
    better = candidates[
        (candidates["sharpe"] > baseline["sharpe"])
        & (candidates["annual_return"] > baseline["annual_return"])
    ]
    weak_end = available.loc[available["variant"] == "linear-025"].iloc[0]
    midpoint_candidates = available[available["variant"].isin(["linear-045", "linear-040", "linear-035"])]
    midpoint_better_than_ends = midpoint_candidates[
        (midpoint_candidates["sharpe"] > baseline["sharpe"])
        & (midpoint_candidates["sharpe"] > weak_end["sharpe"])
    ]
    return {
        "passed": not better.empty,
        "reason": "candidate_found" if not better.empty else "no_strength_candidate",
        "best_variant": None if better.empty else better.sort_values("sharpe", ascending=False).iloc[0]["variant"],
        "shape_stage_ready": not midpoint_better_than_ends.empty,
        "best_midpoint_variant": (
            None
            if midpoint_better_than_ends.empty
            else midpoint_better_than_ends.sort_values("sharpe", ascending=False).iloc[0]["variant"]
        ),
    }


def write_phase2_outputs(
    run: ResearchRunLayout,
    scan: pd.DataFrame,
    results: list[ReplayResult],
    calibration: dict[str, object],
    *,
    events: list[dict],
    frames: PriceFrames,
    baseline_returns: pd.Series,
) -> dict[str, object]:
    """Persist strength-scan and candidate-shape outputs."""

    scan.to_csv(run.tables_dir / "momentum_strength_scan.csv", index=False)
    gate = evaluate_phase2_gate(scan)
    lines = [
        "# 动量倾斜强度扫描",
        "",
        f"- **Replay 校准**: `{'通过' if calibration['passed'] else '未通过'}`",
        f"- **Phase 2 gate**: `{'通过' if gate['passed'] else '未通过'}`",
        f"- **判定原因**: `{gate['reason']}`",
        "",
    ]
    display_cols = [
        col
        for col in [
            "variant",
            "strength",
            "metrics_status",
            "annual_return",
            "sharpe",
            "max_drawdown",
            "rolling_sharpe_win_rate",
            "dominant_etf_share",
        ]
        if col in scan.columns
    ]
    display = scan[display_cols].copy()
    for column in ["annual_return", "max_drawdown", "rolling_sharpe_win_rate", "dominant_etf_share"]:
        if column in display.columns:
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else f"{abs(value):.2%}"
            )
    if "sharpe" in display.columns:
        display["sharpe"] = display["sharpe"].map(lambda value: "" if pd.isna(value) else f"{value:.3f}")
    lines.extend([markdown_table(display), ""])

    shape_rows = []
    if gate["shape_stage_ready"] and results:
        best_linear = max(
            (result for result in results if result.spec.label in {"linear-045", "linear-040", "linear-035"}),
            key=lambda item: item.metrics["sharpe"],
        )
        for spec in _shape_variants(best_linear.spec.strength):
            result = replay_variant(
                events,
                frames.close.reindex(columns=list(ETF_CODES)),
                baseline_returns,
                spec,
            )
            summary = summarize_variant_vs_baseline(baseline_returns, result)
            anchored_metrics = _anchor_metrics(
                result.metrics,
                local_baseline=calibration["baseline_local_raw"],
                cloud_baseline=calibration["baseline_cloud"],
            )
            shape_rows.append(
                {
                    "variant": spec.label,
                    "strength": spec.strength,
                    **anchored_metrics,
                    **summary,
                }
            )
    shape_frame = pd.DataFrame(shape_rows)
    shape_frame.to_csv(run.tables_dir / "momentum_shape_candidates.csv", index=False)
    if shape_frame.empty:
        lines.extend(
            [
                "## 形状候选",
                "",
                "_当前未进入形状候选阶段；只有当中间 strength 同时优于 `0.50` 与 `0.25` 时才继续比较非线性形状。_",
                "",
            ]
        )
    else:
        shape_display = shape_frame[
            ["variant", "strength", "annual_return", "sharpe", "max_drawdown", "rolling_sharpe_win_rate"]
        ].copy()
        for column in ["annual_return", "max_drawdown", "rolling_sharpe_win_rate"]:
            shape_display[column] = shape_display[column].map(lambda value: f"{abs(value):.2%}")
        shape_display["sharpe"] = shape_display["sharpe"].map(lambda value: f"{value:.3f}")
        lines.extend(["## 形状候选", "", markdown_table(shape_display), ""])
    (run.reports_dir / "momentum_shape_candidate_summary.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return gate


def write_final_decision(
    run: ResearchRunLayout,
    *,
    phase1_gate: dict[str, object],
    calibration: dict[str, object],
    phase2_gate: dict[str, object],
) -> dict[str, object]:
    """Persist the staged local decision and cloud-gate status."""

    ab_ready = bool(phase1_gate["passed"] and calibration["passed"] and phase2_gate["passed"])
    decision = {
        "ab_ready": ab_ready,
        "phase1_passed": bool(phase1_gate["passed"]),
        "replay_passed": bool(calibration["passed"]),
        "phase2_passed": bool(phase2_gate["passed"]),
        "phase2_reason": phase2_gate["reason"],
        "best_linear_variant": phase2_gate.get("best_variant"),
        "shape_stage_ready": bool(phase2_gate.get("shape_stage_ready", False)),
        "best_midpoint_variant": phase2_gate.get("best_midpoint_variant"),
    }
    write_json(run.tables_dir / "local_decision.json", decision)
    lines = [
        "# 动量倾斜下一阶段决策",
        "",
        f"- **Phase 1**: `{'通过' if phase1_gate['passed'] else '未通过'}`",
        f"- **Replay 校准**: `{'通过' if calibration['passed'] else '未通过'}`",
        f"- **Phase 2**: `{'通过' if phase2_gate['passed'] else '未通过'}`",
        f"- **是否允许生成云端批次 A**: `{'是' if ab_ready else '否'}`",
        "",
        "## 当前判定",
        "",
    ]
    if ab_ready:
        lines.append(
            f"- 本地闸门已通过，可生成云端批次 A；当前最佳线性候选为 `{phase2_gate.get('best_variant')}`。"
        )
        if not phase2_gate.get("shape_stage_ready", False):
            lines.append("- 中间 strength 尚未同时优于 `0.50` 与 `0.25`，本轮不进入非线性形状确认。")
    elif not calibration["passed"]:
        lines.append("- replay 尚未校准通过，Phase 2 只能作为信号诊断，不进入正式决策链。")
    elif not phase1_gate["passed"]:
        lines.append("- discovery / holdout 未同时支持“中段优于高段”，暂不应继续放大研究复杂度。")
    else:
        lines.append("- 暂未发现稳定优于 baseline 的中间线性强度候选，先不送云。")
    lines.extend(
        [
            "",
            "## 闸门摘要",
            "",
            markdown_table(
                pd.DataFrame(
                    [
                        {"闸门": "Phase 1", "结果": phase1_gate["passed"]},
                        {"闸门": "Replay", "结果": calibration["passed"]},
                        {"闸门": "Phase 2", "结果": phase2_gate["passed"]},
                        {"闸门": "Shape Stage", "结果": phase2_gate.get("shape_stage_ready", False)},
                    ]
                )
            ),
            "",
        ]
    )
    (run.reports_dir / "momentum-next-stage-decision.md").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
    return decision


def write_manifest(
    run: ResearchRunLayout,
    *,
    raw_price_path: Path,
    audit_log_path: Path,
    baseline_returns_path: Path,
    outputs: Iterable[str],
) -> None:
    payload = {
        "strategy": STRATEGY,
        "run_id": run.run_id,
        "score_start": SCORE_START.isoformat(),
        "score_end": SCORE_END.isoformat(),
        "inputs": {
            "raw_price_path": raw_price_path.as_posix(),
            "audit_log_path": audit_log_path.as_posix(),
            "baseline_returns_path": baseline_returns_path.as_posix(),
        },
        "outputs": list(outputs),
    }
    write_json(run.manifest_path, payload)


def build_cloud_robustness_summary(
    *,
    baseline_run_id: str,
    variant_run_id: str,
    frames: PriceFrames,
) -> dict[str, object]:
    """Build robustness diagnostics from realized cloud return paths."""

    baseline_returns = parse_cumulative_returns_md(
        backtest_run_dir(baseline_run_id) / "tabs_raw" / "daily_returns.md"
    )
    variant_returns = parse_cumulative_returns_md(
        backtest_run_dir(variant_run_id) / "tabs_raw" / "daily_returns.md"
    )
    common = baseline_returns.index.intersection(variant_returns.index)
    baseline_returns = baseline_returns.loc[common]
    variant_returns = variant_returns.loc[common]
    baseline_metrics = performance_metrics(baseline_returns)
    variant_metrics = performance_metrics(variant_returns)
    baseline_cloud_metrics = _parse_cloud_summary(baseline_run_id)
    variant_cloud_metrics = _parse_cloud_summary(variant_run_id)
    bootstrap = paired_block_bootstrap(baseline_returns, variant_returns)

    rolling = pd.concat(
        [
            rolling_sharpe(baseline_returns).rename("baseline"),
            rolling_sharpe(variant_returns).rename("variant"),
        ],
        axis=1,
    ).dropna()
    rolling_win_rate = float((rolling["variant"] > rolling["baseline"]).mean())

    yearly = yearly_metrics(variant_returns).merge(
        yearly_metrics(baseline_returns),
        on="year",
        suffixes=("_variant", "_baseline"),
    )
    years_better = int((yearly["sharpe_variant"] > yearly["sharpe_baseline"]).sum())

    baseline_events = load_rebalance_events(
        backtest_run_dir(baseline_run_id) / "tabs_raw" / "audit_log.jsonl"
    )
    variant_events = load_rebalance_events(
        backtest_run_dir(variant_run_id) / "tabs_raw" / "audit_log.jsonl"
    )
    baseline_schedule = expand_weight_schedule(
        event_weight_frame(baseline_events),
        common,
        ETF_CODES,
    )
    variant_schedule = expand_weight_schedule(
        event_weight_frame(variant_events),
        common,
        ETF_CODES,
    )
    etf_returns = frames.close.reindex(columns=list(ETF_CODES)).pct_change().reindex(common).fillna(0.0)
    contributions = (variant_schedule - baseline_schedule) * etf_returns
    contribution_totals = contributions.sum()
    total_improvement = variant_metrics["total_return"] - baseline_metrics["total_return"]
    dominant_share = (
        float(contribution_totals.abs().max() / abs(total_improvement))
        if total_improvement != 0
        else 0.0
    )
    leave_one = {}
    for code in ETF_CODES:
        without_code = baseline_returns + (variant_returns - baseline_returns) - contributions[code]
        leave_one[code] = performance_metrics(without_code)["sharpe"] - baseline_metrics["sharpe"]

    decision = {
        "sharpe_higher": variant_cloud_metrics["sharpe"] > baseline_cloud_metrics["sharpe"],
        "annual_within_threshold": (
            variant_cloud_metrics["annual_return"] >= baseline_cloud_metrics["annual_return"] - 0.003
        ),
        "drawdown_within_threshold": (
            abs(variant_cloud_metrics["max_drawdown"])
            <= abs(baseline_cloud_metrics["max_drawdown"]) + 0.002
        ),
        "rolling_win_rate_pass": rolling_win_rate > 0.55,
        "years_better_pass": years_better >= 4,
        "dominant_share_pass": dominant_share <= 0.70,
        "leave_one_pass": all(value >= 0 for value in leave_one.values()),
    }
    decision["all_passed"] = all(decision.values())
    return {
        "baseline_metrics": baseline_metrics,
        "variant_metrics": variant_metrics,
        "baseline_cloud_metrics": baseline_cloud_metrics,
        "variant_cloud_metrics": variant_cloud_metrics,
        "bootstrap": bootstrap,
        "rolling_win_rate": rolling_win_rate,
        "yearly": yearly,
        "years_better": years_better,
        "contribution_totals": contribution_totals.to_dict(),
        "dominant_share": dominant_share,
        "leave_one": leave_one,
        "decision": decision,
    }


def write_cloud_robustness_report(
    *,
    baseline_run_id: str,
    variant_run_id: str,
    label: str,
    frames: PriceFrames,
) -> Path:
    """Persist realized-cloud robustness diagnostics next to the variant run."""

    summary = build_cloud_robustness_summary(
        baseline_run_id=baseline_run_id,
        variant_run_id=variant_run_id,
        frames=frames,
    )
    baseline_cloud = summary["baseline_cloud_metrics"]
    variant_cloud = summary["variant_cloud_metrics"]
    bootstrap = summary["bootstrap"]
    yearly = summary["yearly"].copy()
    yearly_display = yearly[
        [
            "year",
            "sharpe_baseline",
            "sharpe_variant",
            "annual_return_baseline",
            "annual_return_variant",
            "max_drawdown_baseline",
            "max_drawdown_variant",
        ]
    ].copy()
    for column in yearly_display.columns:
        if column.startswith("annual_return") or column.startswith("max_drawdown"):
            yearly_display[column] = yearly_display[column].map(lambda value: f"{abs(value):.2%}")
        elif column.startswith("sharpe"):
            yearly_display[column] = yearly_display[column].map(lambda value: f"{value:.3f}")
    contrib_display = pd.DataFrame(
        [
            {
                "ETF": ETF_LABELS[code],
                "贡献(bp近似)": round(value * 10000, 1),
                "leave-one-out Sharpe差": round(summary["leave_one"][code], 4),
            }
            for code, value in summary["contribution_totals"].items()
        ]
    )
    decision_display = pd.DataFrame(
        [{"门槛": key, "结果": value} for key, value in summary["decision"].items()]
    )
    lines = [
        f"# 稳健性验证：{label}",
        "",
        f"- **对比**: `{baseline_run_id}` -> `{variant_run_id}`",
        "- **方法**: 配对 block bootstrap + 滚动 `252` 日 Sharpe + 年度分解 + ETF 贡献拆解",
        "",
        "## 总体指标",
        "",
        markdown_table(
            pd.DataFrame(
                [
                    {
                        "方案": "baseline",
                        "年化": f"{baseline_cloud['annual_return']:.2%}",
                        "Sharpe": f"{baseline_cloud['sharpe']:.3f}",
                        "最大回撤": f"{abs(baseline_cloud['max_drawdown']):.2%}",
                    },
                    {
                        "方案": label,
                        "年化": f"{variant_cloud['annual_return']:.2%}",
                        "Sharpe": f"{variant_cloud['sharpe']:.3f}",
                        "最大回撤": f"{abs(variant_cloud['max_drawdown']):.2%}",
                    },
                ]
            )
        ),
        "",
        "## 配对 Bootstrap",
        "",
        markdown_table(
            pd.DataFrame(
                [
                    {
                        "variant-baseline 日均差(bp)": round(bootstrap["observed"] * 10000, 3),
                        "CI95低(bp)": round(bootstrap["ci_low"] * 10000, 3),
                        "CI95高(bp)": round(bootstrap["ci_high"] * 10000, 3),
                        "p-value": round(bootstrap["p_value"], 4),
                    }
                ]
            )
        ),
        "",
        f"- **滚动 Sharpe 胜率**: `{summary['rolling_win_rate']:.1%}`",
        f"- **年度 Sharpe 改善**: `{summary['years_better']}/6`",
        f"- **单一 ETF 最大解释占比**: `{summary['dominant_share']:.1%}`",
        "",
        "## 年度分解",
        "",
        markdown_table(yearly_display),
        "",
        "## ETF 贡献拆解",
        "",
        markdown_table(contrib_display),
        "",
        "## 决策门槛",
        "",
        markdown_table(decision_display),
        "",
    ]
    report_path = backtest_run_dir(variant_run_id) / "report" / "robustness-verification.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def analyze_project(
    *,
    project_dir: str | Path,
    run_id: str,
    stage: str,
    raw_price_path: str | Path | None = None,
    audit_log_path: str | Path | None = None,
    baseline_returns_path: str | Path | None = None,
) -> dict[str, object]:
    """Run one or more staged local analyses and persist outputs."""

    project = ResearchProjectLayout.from_path(project_dir)
    project.ensure_project_dirs()
    run = project.run(run_id)
    run.ensure_dirs()
    raw_path = Path(raw_price_path) if raw_price_path else default_raw_price_path()
    audit_path = Path(audit_log_path) if audit_log_path else default_audit_log_path()
    returns_path = Path(baseline_returns_path) if baseline_returns_path else default_baseline_returns_path()

    frames = load_price_bundle(raw_path, ETF_CODES)
    events = load_rebalance_events(audit_path)
    params = load_run_start_params(audit_path)
    baseline_returns = parse_cumulative_returns_md(returns_path)
    samples = build_response_samples(events, frames)
    curve = build_response_curve(samples)
    zone_summary = build_zone_summary(samples)
    phase1_gate = evaluate_phase1_gate(zone_summary)
    calibration = calibrate_replay(events, frames, baseline_returns)

    if stage in {"phase0", "all"}:
        write_phase0_outputs(
            run,
            audit_log_path=audit_path,
            raw_price_path=raw_path,
            baseline_returns_path=returns_path,
            events=events,
            params=params,
        )
    if stage in {"phase1", "all"}:
        write_phase1_outputs(run, samples, curve, zone_summary, phase1_gate)
    write_calibration_outputs(run, calibration)

    phase2_gate = {"passed": False, "reason": "not_run"}
    if stage in {"phase2", "all"}:
        scan, results = build_phase2_scan(events, frames, baseline_returns, calibration)
        phase2_gate = write_phase2_outputs(
            run,
            scan,
            results,
            calibration,
            events=events,
            frames=frames,
            baseline_returns=baseline_returns,
        )
    decision = write_final_decision(
        run,
        phase1_gate=phase1_gate,
        calibration=calibration,
        phase2_gate=phase2_gate,
    )

    outputs = [
        "reports/baseline_snapshot.md",
        "reports/sample_split.md",
        "reports/momentum_response_curve.md",
        "reports/replay_calibration.md",
        "reports/momentum_shape_candidate_summary.md",
        "reports/momentum-next-stage-decision.md",
        "tables/momentum_response_curve.csv",
        "tables/momentum_zone_summary.csv",
        "tables/replay_calibration.json",
        "tables/momentum_strength_scan.csv",
        "tables/momentum_shape_candidates.csv",
        "tables/local_decision.json",
    ]
    write_manifest(
        run,
        raw_price_path=raw_path,
        audit_log_path=audit_path,
        baseline_returns_path=returns_path,
        outputs=outputs,
    )
    return {
        "phase1_gate": phase1_gate,
        "calibration": calibration,
        "phase2_gate": phase2_gate,
        "decision": decision,
    }
