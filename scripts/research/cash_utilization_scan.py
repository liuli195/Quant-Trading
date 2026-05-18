"""Local scan for cash-utilization changes driven by portfolio-vol controls."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.momentum_tilt_research.replay import (
    apply_weight_constraints,
    event_weight_frame,
    expand_weight_schedule,
)
from scripts.research.research_core.audit import load_rebalance_events
from scripts.research.research_core.layout import ResearchProjectLayout
from scripts.research.research_core.metrics import (
    paired_block_bootstrap,
    parse_cumulative_returns_md,
    performance_metrics,
    rolling_sharpe,
    yearly_metrics,
)
from scripts.research.research_core.prices import load_price_bundle
from scripts.research.research_core.reporting import markdown_table, write_json


CODES = ("159819.XSHE", "513100.XSHG", "518880.XSHG")
LABELS = {
    "159819.XSHE": "AI",
    "513100.XSHG": "纳指",
    "518880.XSHG": "黄金",
}
WINDOWS = (20, 40, 60, 90, 120)
TARGETS = tuple(round(value, 2) for value in np.arange(0.06, 0.141, 0.01))
MIX_BASES = ((40, 0.07), (40, 0.08), (60, 0.08))
MIX_STEPS = (0.0, 0.1, 0.2, 0.3)


@dataclass(frozen=True)
class ScanContext:
    events: list[dict]
    close: pd.DataFrame
    asset_returns: pd.DataFrame
    baseline_returns: pd.Series
    baseline_schedule: pd.DataFrame
    baseline_metrics: dict[str, float]
    baseline_cloud_metrics: dict[str, float]
    params: dict
    portfolio_vol_cache: dict[int, list[float]]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _parse_cloud_summary(path: Path) -> dict[str, float]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {
        "annual_return": float(str(raw["策略年化收益"]).rstrip("%")) / 100,
        "volatility": float(raw["策略波动率"]),
        "sharpe": float(raw["夏普比率"]),
        "max_drawdown": -float(str(raw["最大回撤"]).rstrip("%")) / 100,
    }


def _portfolio_vol(
    returns: pd.DataFrame,
    raw_weights: np.ndarray,
    previous_date: str,
    window: int,
) -> float:
    history = (
        returns.loc[: pd.Timestamp(previous_date).normalize()]
        .tail(window)
        .dropna(how="all")
    )
    if len(history) < 5:
        return 0.0
    covariance = history.cov().to_numpy() * 252
    return float(np.sqrt(raw_weights @ covariance @ raw_weights))


def load_context(
    *,
    baseline_run_dir: Path,
    raw_price_path: Path,
) -> ScanContext:
    audit_log_path = baseline_run_dir / "tabs_raw" / "audit_log.jsonl"
    baseline_returns_path = baseline_run_dir / "tabs_raw" / "daily_returns.md"
    summary_path = baseline_run_dir / "summary_metrics.json"

    events = load_rebalance_events(audit_log_path)
    frames = load_price_bundle(raw_price_path, CODES)
    close = frames.close.reindex(columns=list(CODES))
    returns = close.pct_change()
    baseline_returns = parse_cumulative_returns_md(baseline_returns_path)
    asset_returns = returns.reindex(baseline_returns.index).fillna(0.0)
    baseline_schedule = expand_weight_schedule(
        event_weight_frame(events),
        baseline_returns.index,
        CODES,
    )
    portfolio_vol_cache = {
        window: [
            _portfolio_vol(
                returns,
                np.asarray(event["raw_weights"], dtype=float),
                event["previous_date"],
                window,
            )
            for event in events
        ]
        for window in WINDOWS
    }
    return ScanContext(
        events=events,
        close=close,
        asset_returns=asset_returns,
        baseline_returns=baseline_returns,
        baseline_schedule=baseline_schedule,
        baseline_metrics=performance_metrics(baseline_returns),
        baseline_cloud_metrics=_parse_cloud_summary(summary_path),
        params=dict(events[0]["params"]),
        portfolio_vol_cache=portfolio_vol_cache,
    )


def _variant_schedule(
    ctx: ScanContext,
    *,
    window: int,
    target: float,
    gold_bonus: float = 0.0,
    ai_penalty: float = 0.0,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    ai_idx = CODES.index("159819.XSHE")
    gold_idx = CODES.index("518880.XSHG")

    for event, portfolio_vol in zip(
        ctx.events,
        ctx.portfolio_vol_cache[window],
        strict=True,
    ):
        raw = np.asarray(event["raw_weights"], dtype=float)
        raw_total = float(raw.sum())
        ai_share = float(raw[ai_idx] / raw_total) if raw_total > 0 else 0.0
        gold_share = float(raw[gold_idx] / raw_total) if raw_total > 0 else 0.0
        effective_target = target * (1.0 + gold_bonus * gold_share - ai_penalty * ai_share)
        effective_target = float(np.clip(effective_target, 0.04, 0.16))
        scale = 1.0 if portfolio_vol <= 0 else min(1.0, effective_target / portfolio_vol)
        final = apply_weight_constraints(raw * scale, ctx.params)
        rows.append(
            {
                "signal_date": pd.Timestamp(event["current_dt"]).normalize(),
                **{code: float(weight) for code, weight in zip(CODES, final, strict=True)},
            }
        )
    weekly = pd.DataFrame(rows)
    return expand_weight_schedule(weekly, ctx.baseline_returns.index, CODES)


def _evaluate_variant(
    ctx: ScanContext,
    *,
    label: str,
    family: str,
    window: int,
    target: float,
    gold_bonus: float = 0.0,
    ai_penalty: float = 0.0,
) -> tuple[dict[str, float | str], pd.Series, pd.DataFrame]:
    schedule = _variant_schedule(
        ctx,
        window=window,
        target=target,
        gold_bonus=gold_bonus,
        ai_penalty=ai_penalty,
    )
    contributions = (schedule - ctx.baseline_schedule) * ctx.asset_returns
    returns = ctx.baseline_returns.add(contributions.sum(axis=1), fill_value=0.0)
    metrics = performance_metrics(returns)
    row: dict[str, float | str] = {
        "label": label,
        "family": family,
        "window": window,
        "target": target,
        "gold_bonus": gold_bonus,
        "ai_penalty": ai_penalty,
        "avg_position": float(schedule.sum(axis=1).mean()),
        **metrics,
        "annual_delta": metrics["annual_return"] - ctx.baseline_metrics["annual_return"],
        "volatility_delta": metrics["volatility"] - ctx.baseline_metrics["volatility"],
        "sharpe_delta": metrics["sharpe"] - ctx.baseline_metrics["sharpe"],
        "max_drawdown_delta": metrics["max_drawdown"] - ctx.baseline_metrics["max_drawdown"],
    }
    return row, returns, contributions


def build_global_scan(ctx: ScanContext) -> pd.DataFrame:
    rows = []
    for window in WINDOWS:
        for target in TARGETS:
            row, _, _ = _evaluate_variant(
                ctx,
                label=f"global-w{window}-t{target:.2f}",
                family="global",
                window=window,
                target=target,
            )
            rows.append(row)
    return pd.DataFrame(rows)


def build_mix_scan(ctx: ScanContext) -> pd.DataFrame:
    rows = []
    for window, target in MIX_BASES:
        for gold_bonus in MIX_STEPS:
            for ai_penalty in MIX_STEPS:
                row, _, _ = _evaluate_variant(
                    ctx,
                    label=(
                        f"mix-w{window}-t{target:.2f}"
                        f"-g{gold_bonus:.1f}-a{ai_penalty:.1f}"
                    ),
                    family="mix_aware",
                    window=window,
                    target=target,
                    gold_bonus=gold_bonus,
                    ai_penalty=ai_penalty,
                )
                rows.append(row)
    return pd.DataFrame(rows)


def _anchored_metrics(
    ctx: ScanContext,
    row: pd.Series,
) -> dict[str, float]:
    delta_columns = {
        "annual_return": "annual_delta",
        "volatility": "volatility_delta",
        "sharpe": "sharpe_delta",
        "max_drawdown": "max_drawdown_delta",
    }
    return {
        key: ctx.baseline_cloud_metrics[key] + float(row[delta_columns[key]])
        for key in delta_columns
    }


def build_shortlist(ctx: ScanContext) -> pd.DataFrame:
    specs = [
        ("global-w40-t0.08", "global", 40, 0.08, 0.0, 0.0),
        ("global-w40-t0.07", "global", 40, 0.07, 0.0, 0.0),
        ("mix-w40-t0.07-g0.2-a0.3", "mix_aware", 40, 0.07, 0.2, 0.3),
        ("mix-w40-t0.08-g0.0-a0.3", "mix_aware", 40, 0.08, 0.0, 0.3),
    ]
    rows = []
    for label, family, window, target, gold_bonus, ai_penalty in specs:
        row, returns, contributions = _evaluate_variant(
            ctx,
            label=label,
            family=family,
            window=window,
            target=target,
            gold_bonus=gold_bonus,
            ai_penalty=ai_penalty,
        )
        bootstrap = paired_block_bootstrap(ctx.baseline_returns, returns)
        rolling = pd.concat(
            [
                rolling_sharpe(ctx.baseline_returns).rename("baseline"),
                rolling_sharpe(returns).rename("variant"),
            ],
            axis=1,
        ).dropna()
        yearly = yearly_metrics(returns).merge(
            yearly_metrics(ctx.baseline_returns),
            on="year",
            suffixes=("_variant", "_baseline"),
        )
        contribution_totals = contributions.sum()
        improvement = float(row["total_return"]) - ctx.baseline_metrics["total_return"]
        dominant_share = (
            float(contribution_totals.abs().max() / abs(improvement))
            if improvement != 0
            else 0.0
        )
        anchored = _anchored_metrics(ctx, pd.Series(row))
        rows.append(
            {
                **row,
                **{f"anchored_{key}": value for key, value in anchored.items()},
                "bootstrap_observed": bootstrap["observed"],
                "bootstrap_ci_low": bootstrap["ci_low"],
                "bootstrap_ci_high": bootstrap["ci_high"],
                "bootstrap_p_value": bootstrap["p_value"],
                "rolling_sharpe_win_rate": (
                    float((rolling["variant"] > rolling["baseline"]).mean())
                    if not rolling.empty
                    else np.nan
                ),
                "years_better": int(
                    (yearly["sharpe_variant"] > yearly["sharpe_baseline"]).sum()
                ),
                "dominant_etf_share": dominant_share,
                **{
                    f"contrib_{code}": float(value)
                    for code, value in contribution_totals.items()
                },
            }
        )
    return pd.DataFrame(rows)


def _percent(value: float) -> str:
    return f"{value:.2%}"


def _pp(value: float) -> str:
    return f"{value * 100:+.2f}pp"


def _pp_abs(value: float) -> str:
    return f"{abs(value) * 100:.2f}pp"


def _with_anchored_metrics(ctx: ScanContext, frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for key in ("annual_return", "volatility", "sharpe", "max_drawdown"):
        delta_column = {
            "annual_return": "annual_delta",
            "volatility": "volatility_delta",
            "sharpe": "sharpe_delta",
            "max_drawdown": "max_drawdown_delta",
        }[key]
        display[f"anchored_{key}"] = (
            ctx.baseline_cloud_metrics[key] + display[delta_column]
        )
    return display


def _format_scan_table(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    for column in [
        "target",
        "avg_position",
        "anchored_annual_return",
        "anchored_volatility",
        "anchored_max_drawdown",
    ]:
        if column in display.columns:
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else _percent(abs(float(value)))
            )
    for column in ["annual_delta", "volatility_delta", "max_drawdown_delta"]:
        if column in display.columns:
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else _pp(float(value))
            )
    for column in ["anchored_sharpe", "sharpe_delta"]:
        if column in display.columns:
            display[column] = display[column].map(
                lambda value: "" if pd.isna(value) else f"{float(value):.3f}"
            )
    return display


def render_report(
    *,
    ctx: ScanContext,
    global_scan: pd.DataFrame,
    mix_scan: pd.DataFrame,
    shortlist: pd.DataFrame,
) -> str:
    top_global = _with_anchored_metrics(
        ctx,
        global_scan.sort_values(
            ["sharpe", "annual_return"],
            ascending=False,
        ).head(10),
    )
    top_mix = _with_anchored_metrics(
        ctx,
        mix_scan.sort_values(
            ["sharpe", "annual_return"],
            ascending=False,
        ).head(10),
    )
    global_best_balance = global_scan.loc[
        (global_scan["window"] == 40) & (global_scan["target"] == 0.08)
    ].iloc[0]
    global_low_risk = global_scan.loc[
        (global_scan["window"] == 40) & (global_scan["target"] == 0.07)
    ].iloc[0]
    mix_best = mix_scan.loc[
        (mix_scan["window"] == 40)
        & (mix_scan["target"] == 0.07)
        & (mix_scan["gold_bonus"] == 0.2)
        & (mix_scan["ai_penalty"] == 0.3)
    ].iloc[0]
    ai_only = mix_scan.loc[
        (mix_scan["window"] == 40)
        & (mix_scan["target"] == 0.08)
        & (mix_scan["gold_bonus"] == 0.0)
        & (mix_scan["ai_penalty"] == 0.3)
    ].iloc[0]

    shortlist_display = shortlist[
        [
            "label",
            "anchored_annual_return",
            "anchored_volatility",
            "anchored_sharpe",
            "anchored_max_drawdown",
            "rolling_sharpe_win_rate",
            "years_better",
            "bootstrap_ci_low",
            "bootstrap_ci_high",
            "bootstrap_p_value",
            "dominant_etf_share",
        ]
    ].copy()
    for column in [
        "anchored_annual_return",
        "anchored_volatility",
        "anchored_max_drawdown",
        "rolling_sharpe_win_rate",
        "dominant_etf_share",
    ]:
        shortlist_display[column] = shortlist_display[column].map(
            lambda value: _percent(abs(float(value)))
        )
    shortlist_display["anchored_sharpe"] = shortlist_display["anchored_sharpe"].map(
        lambda value: f"{float(value):.3f}"
    )
    for column in ["bootstrap_ci_low", "bootstrap_ci_high"]:
        shortlist_display[column] = shortlist_display[column].map(
            lambda value: f"{float(value) * 10000:+.3f} bp"
        )
    shortlist_display["bootstrap_p_value"] = shortlist_display[
        "bootstrap_p_value"
    ].map(lambda value: f"{float(value):.4f}")

    return "\n".join(
        [
            "# 组合波动率全量本地扫描",
            "",
            "- **研究主题**: 先处理现金利用率中的最大来源 `PortfolioVolScale`",
            "- **基线 run**: `20260517-1724-bt580e16e5a3f1bf99d197cea88889da1a`",
            "- **基线云端指标**: 年化 `15.76%`，波动率 `8.10%`，Sharpe `1.447`，最大回撤 `8.09%`",
            "- **扫描范围**:",
            f"  - 组合层: `{len(global_scan)}` 组 = `5` 个窗口 × `9` 个目标波动率",
            f"  - ETF 组合感知层: `{len(mix_scan)}` 组 = `3` 个基点 × `4` 个黄金加成 × `4` 个 AI 惩罚",
            "",
            "说明：本地 replay 以云端基线真实日收益为锚，只估计目标权重变化带来的相对差异；",
            "绝对指标使用云端基线加本地差值锚定，适合筛选，不替代最终云端 A/B。",
            "",
            "## 结论",
            "",
            "1. **收益怎么变化**",
            f"   - 只改组合层时，`40 日 + 8%` 相对当前基线年化约 `{_pp(float(global_best_balance['annual_delta']))}`，是最实用的增收点。",
            f"   - 继续放到 `40 日 + 9%` 还能加收益，但 Sharpe 已低于 `40 日 + 8%`，收益换来的风险开始变贵。",
            "2. **风险怎么变化**",
            f"   - `40 日 + 8%` 的波动率约 `{_pp(float(global_best_balance['volatility_delta']))}`，最大回撤基本不变。",
            f"   - `40 日 + 7%` 则把波动率约压低 `{_pp_abs(float(global_low_risk['volatility_delta']))}`，回撤约改善 `{_pp(float(global_low_risk['max_drawdown_delta']))}`，但年化约少 `{_pp_abs(float(global_low_risk['annual_delta']))}`。",
            "3. **收益和风险的最佳平衡**",
            "   - 若只允许一个简单、可解释的主线方案，优先选 `PortfolioVolWindow=40`、`TargetVol=0.08`。",
            "   - 它在短名单中同时具备正收益、接近不变的回撤、较高滚动胜率和最清楚的 bootstrap 证据。",
            "4. **是否需要 ETF 差异化控制**",
            f"   - 需要继续研究，但不应先于组合层改造上线。当前最强局部信号不是“所有 ETF 都配专属规则”，而是“高波动 AI 需要更紧，黄金可以在 AI 被压住时适度放松”。",
            f"   - `40 日 + 7% + 黄金加成 20% + AI 惩罚 30%` 的本地点估计最好：年化 `{_pp(float(mix_best['annual_delta']))}`、波动率 `{_pp(float(mix_best['volatility_delta']))}`、回撤改善 `{_pp(float(mix_best['max_drawdown_delta']))}`、Sharpe 提升 `{float(mix_best['sharpe_delta']):+.3f}`。",
            f"   - 但更适合作为下一阶段分支的是更小改动的 `AI 惩罚 30%`：年化 `{_pp(float(ai_only['annual_delta']))}`、波动率 `{_pp(float(ai_only['volatility_delta']))}`、回撤改善 `{_pp(float(ai_only['max_drawdown_delta']))}`。",
            "",
            "## 组合层扫描前 10",
            "",
            markdown_table(
                _format_scan_table(
                    top_global[
                        [
                            "label",
                            "window",
                            "target",
                            "avg_position",
                            "anchored_annual_return",
                            "anchored_volatility",
                            "anchored_sharpe",
                            "anchored_max_drawdown",
                            "annual_delta",
                            "volatility_delta",
                            "sharpe_delta",
                        ]
                    ]
                )
            ),
            "",
            "## ETF 组合感知扫描前 10",
            "",
            markdown_table(
                _format_scan_table(
                    top_mix[
                        [
                            "label",
                            "window",
                            "target",
                            "gold_bonus",
                            "ai_penalty",
                            "avg_position",
                            "anchored_annual_return",
                            "anchored_volatility",
                            "anchored_sharpe",
                            "anchored_max_drawdown",
                            "annual_delta",
                            "volatility_delta",
                            "sharpe_delta",
                        ]
                    ]
                )
            ),
            "",
            "## 短名单稳健性",
            "",
            markdown_table(shortlist_display),
            "",
            "## 执行建议",
            "",
            "1. 第一优先级改为组合层：先用云端 A/B 确认 `40 日 + 8%`。",
            "2. 若云端确认通过，再研究 ETF 差异化；优先从 `AI-only tightening` 做最小实验。",
            "3. 只有当 AI 单独收紧的云端结果也稳定，再考虑加入黄金加成分支；不要直接上三资产全量异质化。",
            "",
        ]
    )


def write_outputs(
    *,
    project_dir: Path,
    run_id: str,
    baseline_run_dir: Path,
    raw_price_path: Path,
    ctx: ScanContext,
    global_scan: pd.DataFrame,
    mix_scan: pd.DataFrame,
    shortlist: pd.DataFrame,
) -> Path:
    project = ResearchProjectLayout.from_path(project_dir)
    project.ensure_project_dirs()
    run = project.run(run_id)
    run.ensure_dirs()

    global_scan.to_csv(run.tables_dir / "portfolio_vol_global_scan.csv", index=False)
    mix_scan.to_csv(run.tables_dir / "portfolio_vol_mix_scan.csv", index=False)
    shortlist.to_csv(run.tables_dir / "portfolio_vol_shortlist_robustness.csv", index=False)
    (run.reports_dir / "portfolio-volatility-full-scan.md").write_text(
        render_report(
            ctx=ctx,
            global_scan=global_scan,
            mix_scan=mix_scan,
            shortlist=shortlist,
        ),
        encoding="utf-8",
    )
    write_json(
        run.manifest_path,
        {
            "schema_version": 1,
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "inputs": {
                "baseline_run_dir": baseline_run_dir.as_posix(),
                "raw_price_path": raw_price_path.as_posix(),
            },
            "scan": {
                "global_windows": list(WINDOWS),
                "global_targets": list(TARGETS),
                "mix_bases": [list(item) for item in MIX_BASES],
                "mix_steps": list(MIX_STEPS),
            },
            "outputs": [
                "reports/portfolio-volatility-full-scan.md",
                "tables/portfolio_vol_global_scan.csv",
                "tables/portfolio_vol_mix_scan.csv",
                "tables/portfolio_vol_shortlist_robustness.csv",
            ],
        },
    )
    write_json(
        run.status_path,
        {
            "run_id": run_id,
            "status": "completed",
            "global_variants": int(len(global_scan)),
            "mix_variants": int(len(mix_scan)),
            "shortlist_variants": int(len(shortlist)),
        },
    )
    return run.root


def analyze(
    *,
    project_dir: Path,
    run_id: str,
    baseline_run_dir: Path,
    raw_price_path: Path,
) -> Path:
    ctx = load_context(
        baseline_run_dir=baseline_run_dir,
        raw_price_path=raw_price_path,
    )
    global_scan = build_global_scan(ctx)
    mix_scan = build_mix_scan(ctx)
    shortlist = build_shortlist(ctx)
    return write_outputs(
        project_dir=project_dir,
        run_id=run_id,
        baseline_run_dir=baseline_run_dir,
        raw_price_path=raw_price_path,
        ctx=ctx,
        global_scan=global_scan,
        mix_scan=mix_scan,
        shortlist=shortlist,
    )


def main() -> None:
    repo_root = _repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        default=repo_root
        / "strategies"
        / "etf_factor_rotation"
        / "reports"
        / "research"
        / "cash_utilization",
        type=Path,
    )
    parser.add_argument("--run-id", default="2026-05-18-volscale-full-scan")
    parser.add_argument(
        "--baseline-run-dir",
        default=repo_root
        / "strategies"
        / "etf_factor_rotation"
        / "backtest_runs"
        / "20260517-1724-bt580e16e5a3f1bf99d197cea88889da1a",
        type=Path,
    )
    parser.add_argument(
        "--raw-price-path",
        default=repo_root
        / "strategies"
        / "etf_factor_rotation"
        / "reports"
        / "research"
        / "window_heterogeneity"
        / "inputs"
        / "raw"
        / "etf_window_research_prices.json",
        type=Path,
    )
    args = parser.parse_args()
    output_dir = analyze(
        project_dir=args.project_dir,
        run_id=args.run_id,
        baseline_run_dir=args.baseline_run_dir,
        raw_price_path=args.raw_price_path,
    )
    print(output_dir)


if __name__ == "__main__":
    main()
