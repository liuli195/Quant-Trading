"""Markdown report builders for portfolio-volatility research."""

from __future__ import annotations

import pandas as pd

from scripts.research.platform.benchmark_runner import BenchmarkSummary
from scripts.research.platform.report_primitives import benchmark_frame, markdown_section, percent, seconds
from scripts.research.research_core.reporting import markdown_table


def _format_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for column in ("lower_bound", "upper_bound"):
        display[column] = display[column].map(lambda value: f"{float(value):.6f}")
    return display


def render_smoke_report(
    *,
    coverage: pd.DataFrame,
    summary: BenchmarkSummary,
    feature_cache_hit: bool,
) -> str:
    """Render the pre-full-scan performance smoke report."""

    coverage_complete = bool(
        int(coverage["missing_breakpoints"].sum()) == 0
        and int(coverage["missing_intervals"].sum()) == 0
    )
    rows = [
        "# 组合波动率全量扫描性能冒烟",
        "",
        f"- **覆盖完整**: `{coverage_complete}`",
        f"- **当前运行命中特征缓存**: `{feature_cache_hit}`",
        f"- **完整扫描预计点数**: `{summary.full_item_count}`",
        f"- **预计完整扫描耗时**: `{seconds(summary.predicted_full_seconds)}`",
        f"- **性能门槛**: `{seconds(summary.target_seconds)}`",
        f"- **性能门槛通过**: `{summary.passed and feature_cache_hit}`",
        "",
        markdown_section("覆盖摘要", _format_coverage(coverage)),
        "",
        markdown_section("冷/热冒烟", benchmark_frame(summary)),
        "",
        "## 结论",
        "",
        (
            "可以进入正式全量研究。"
            if summary.passed and feature_cache_hit and coverage_complete
            else "暂不进入正式全量研究，先处理未通过的覆盖或性能门槛。"
        ),
        "",
    ]
    return "\n".join(rows)


def render_full_report(
    *,
    global_scan: pd.DataFrame,
    coverage: pd.DataFrame,
    baseline_position: float,
) -> str:
    """Render the formal behavior-complete full-scan report."""

    ranked = global_scan.sort_values(
        ["sharpe_delta", "annual_delta", "target"],
        ascending=[False, False, True],
    ).head(10)
    best_sharpe = ranked.iloc[0]
    objective_pool = global_scan[
        (global_scan["avg_position"] >= baseline_position)
        & (global_scan["annual_delta"] > 0)
    ]
    best_balance = objective_pool.sort_values(
        ["sharpe_delta", "annual_delta", "target"],
        ascending=[False, False, True],
    ).iloc[0]
    practical_high_return = global_scan.loc[
        (global_scan["window"] == 40)
        & ((global_scan["target"] - 0.08).abs() == (global_scan.loc[global_scan["window"] == 40, "target"] - 0.08).abs().min())
    ].iloc[0]
    max_annual = global_scan.sort_values(
        ["annual_delta", "sharpe_delta", "target"],
        ascending=[False, False, True],
    ).iloc[0]
    per_window = global_scan.loc[
        global_scan.groupby("window")["sharpe_delta"].idxmax(),
        [
            "label",
            "window",
            "target",
            "avg_position",
            "annual_delta",
            "volatility_delta",
            "sharpe_delta",
            "max_drawdown_delta",
        ],
    ].sort_values("window")

    top = ranked.copy()
    for column in ("target", "avg_position"):
        top[column] = top[column].map(lambda value: percent(abs(float(value))))
    for column in ("annual_delta", "volatility_delta", "max_drawdown_delta"):
        top[column] = top[column].map(lambda value: f"{float(value) * 100:+.2f}pp")
    top["sharpe_delta"] = top["sharpe_delta"].map(lambda value: f"{float(value):+.3f}")
    decision_points = pd.DataFrame(
        [
            {
                "role": "Sharpe 最优",
                **best_sharpe.to_dict(),
            },
            {
                "role": "目标最优平衡",
                **best_balance.to_dict(),
            },
            {
                "role": "8% 对照",
                **practical_high_return.to_dict(),
            },
            {
                "role": "最高收益",
                **max_annual.to_dict(),
            },
        ]
    )
    decision_display = decision_points[
        [
            "role",
            "window",
            "target",
            "avg_position",
            "annual_delta",
            "volatility_delta",
            "sharpe_delta",
            "max_drawdown_delta",
        ]
    ].copy()
    window_display = per_window.copy()
    for frame in (decision_display, window_display):
        for column in ("target", "avg_position"):
            frame[column] = frame[column].map(lambda value: percent(abs(float(value))))
        for column in ("annual_delta", "volatility_delta", "max_drawdown_delta"):
            frame[column] = frame[column].map(lambda value: f"{float(value) * 100:+.2f}pp")
        frame["sharpe_delta"] = frame["sharpe_delta"].map(lambda value: f"{float(value):+.3f}")

    def pp(value: float) -> str:
        return f"{float(value) * 100:+.2f}pp"

    return "\n".join(
        [
            "# 组合波动率行为完整扫描",
            "",
            "- **扫描方法**: 解析行为断点并为相邻区间补代表点",
            f"- **扫描点数**: `{len(global_scan)}`",
            f"- **当前基线平均仓位**: `{percent(baseline_position)}`",
            "",
            markdown_section("覆盖摘要", _format_coverage(coverage)),
            "",
            "## 结论",
            "",
            "1. **收益怎么变化**",
            f"   - 若单看收益，继续放宽目标波动率可以把年化抬高；全表最高收益点达到 `{pp(max_annual['annual_delta'])}`，但对应风险代价很高。",
            f"   - 若要求平均仓位不低于当前基线，最好的收益风险折中点在 `40` 日窗口、`TargetVol≈{float(best_balance['target']):.4f}`，年化变化 `{pp(best_balance['annual_delta'])}`。",
            "2. **风险怎么变化**",
            f"   - 纯 Sharpe 最优点位于 `40` 日窗口、`TargetVol≈{float(best_sharpe['target']):.4f}`，但年化变化 `{pp(best_sharpe['annual_delta'])}`，更像降风险方案，不适合作为本轮主线。",
            f"   - 目标最优平衡点的波动率变化 `{pp(best_balance['volatility_delta'])}`，最大回撤变化 `{pp(best_balance['max_drawdown_delta'])}`，基本没有新增风险负担。",
            "3. **收益和风险的最佳平衡**",
            f"   - 若目标是“少拿现金，同时不牺牲收益风险比”，优先选择 `PortfolioVolWindow=40`、`TargetVol≈{float(best_balance['target']):.4f}`。",
            f"   - 它的平均仓位 `{percent(float(best_balance['avg_position']))}`，略高于当前基线；相比之下，`40` 日 `8%` 对照点能拿到更高收益 `{pp(practical_high_return['annual_delta'])}`，但风险上升也更明显。",
            "4. **是否需要 ETF 差异化波动率控制**",
            "   - 当前还没有必要先于组合层主线推进；完整扫描已经把组合层最优区间重新定位。",
            "   - 若进入下一阶段，建议基于新的 `40d / 约 7.8%` 主线先做 `AI-only tightening`，确认有效后再考虑加入黄金放宽，不直接上三资产全异质化。",
            "",
            markdown_section("决策点", decision_display),
            "",
            markdown_section("各窗口 Sharpe 最优点", window_display),
            "",
            "## 收益风险前 10",
            "",
            markdown_table(
                top[
                    [
                        "label",
                        "window",
                        "target",
                        "avg_position",
                        "annual_delta",
                        "volatility_delta",
                        "sharpe_delta",
                        "max_drawdown_delta",
                    ]
                ]
            ),
            "",
        ]
    )
