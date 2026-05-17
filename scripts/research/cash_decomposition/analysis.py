"""Phase 0 现金来源拆解 — 核心计算逻辑。

从审计日志数据集的 Parquet 主存储中读取 rebalance_signals 事件，
将总现金归因到四个来源：趋势门槛、拥挤度惩罚、波动率缩放、交易约束。

Usage:
    from scripts.research.cash_decomposition.analysis import decompose_from_dataset
    df, summary = decompose_from_dataset("etf_factor_rotation_baseline_audit", "2026-05-17T...")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.platform.datasets import load_snapshot
from scripts.research.research_core.reporting import markdown_table, write_json


def decompose_from_dataset(
    dataset_id: str,
    snapshot_id: str,
    *,
    datasets_root: str = "research_datasets",
) -> tuple[pd.DataFrame, dict]:
    """从数据集 Parquet 主存储读取 rebalance_signals 并计算现金拆解。"""
    snapshot = load_snapshot(dataset_id, snapshot_id, datasets_root=datasets_root)
    parquet_path = snapshot.root / "data" / "data.parquet"
    if not parquet_path.is_file():
        raise FileNotFoundError(f"数据集缺少主存储: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    df["date"] = pd.to_datetime(df["date"])

    n_etf = 3
    df["sum_tilted"] = sum(df[f"tilted_weights_{i}"] for i in range(n_etf))
    df["sum_raw"] = sum(df[f"raw_weights_{i}"] for i in range(n_etf))
    df["sum_before_constraints"] = sum(df[f"final_weights_before_constraints_{i}"] for i in range(n_etf))
    df["sum_final"] = sum(df[f"final_weights_{i}"] for i in range(n_etf))

    df["trend_gate_cash"] = 1.0 - df["sum_tilted"]
    df["crowd_cash"] = df["sum_tilted"] - df["sum_raw"]
    df["vol_scale_cash"] = df["sum_raw"] - df["sum_before_constraints"]
    df["constraint_cash"] = df["sum_before_constraints"] - df["sum_final"]
    df["total_cash"] = 1.0 - df["sum_final"]
    df["is_all_cash"] = df["n_active"] == 0

    # 恒等式验证
    calc_total = df["trend_gate_cash"] + df["crowd_cash"] + df["vol_scale_cash"] + df["constraint_cash"]
    if not np.allclose(calc_total, df["total_cash"], atol=1e-8):
        mismatch = ~np.isclose(calc_total, df["total_cash"], atol=1e-8)
        import warnings
        warnings.warn(f"恒等式不匹配: {mismatch.sum()} 行", stacklevel=2)

    summary = _build_summary(df)
    return df, summary


def _build_summary(df: pd.DataFrame) -> dict:
    n = len(df)
    n_all_cash = int(df["is_all_cash"].sum())
    avg_position = float(df["sum_final"].mean())
    sources = {
        "trend_gate_cash": float(df["trend_gate_cash"].mean()),
        "crowd_cash": float(df["crowd_cash"].mean()),
        "vol_scale_cash": float(df["vol_scale_cash"].mean()),
        "constraint_cash": float(df["constraint_cash"].mean()),
    }
    avg_total = float(df["total_cash"].mean())
    return {
        "n_signals": n,
        "n_all_cash": n_all_cash,
        "pct_all_cash": round(n_all_cash / n * 100, 1),
        "avg_position": round(avg_position, 4),
        "median_position": round(float(df["sum_final"].median()), 4),
        "avg_total_cash": round(avg_total, 4),
        "cash_by_source": {k: round(v, 6) for k, v in sources.items()},
        "identity_holds": abs(sum(sources.values()) - avg_total) < 1e-8,
    }


def yearly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """分年度现金拆解摘要。"""
    df_copy = df.copy()
    df_copy["year"] = df_copy["date"].dt.year
    grouped = df_copy.groupby("year")
    rows = []
    for year, grp in grouped:
        rows.append({
            "year": int(year),
            "n_signals": len(grp),
            "n_all_cash": int(grp["is_all_cash"].sum()),
            "avg_position": round(float(grp["sum_final"].mean()), 4),
            "trend_gate_cash": round(float(grp["trend_gate_cash"].mean()), 6),
            "crowd_cash": round(float(grp["crowd_cash"].mean()), 6),
            "vol_scale_cash": round(float(grp["vol_scale_cash"].mean()), 6),
            "constraint_cash": round(float(grp["constraint_cash"].mean()), 6),
        })
    return pd.DataFrame(rows)


def position_quantile_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """按年 × 仓位分位 × 全空仓状态切片。"""
    df_copy = df.copy()
    df_copy["year"] = df_copy["date"].dt.year

    def _label(pos: float) -> str:
        if pos == 0.0:
            return "all_cash"
        if pos <= 0.33:
            return "low"
        if pos <= 0.66:
            return "mid"
        return "high"

    df_copy["position_quantile"] = df_copy["sum_final"].apply(_label)
    grouped = df_copy.groupby(["year", "position_quantile"], observed=True)
    rows = []
    for (year, quantile), grp in grouped:
        rows.append({
            "year": int(year),
            "position_quantile": quantile,
            "count": len(grp),
            "avg_position": round(float(grp["sum_final"].mean()), 4),
            "trend_gate_cash": round(float(grp["trend_gate_cash"].mean()), 6),
            "crowd_cash": round(float(grp["crowd_cash"].mean()), 6),
            "vol_scale_cash": round(float(grp["vol_scale_cash"].mean()), 6),
            "constraint_cash": round(float(grp["constraint_cash"].mean()), 6),
        })
    return pd.DataFrame(rows)


def build_summary_report(df: pd.DataFrame, summary: dict, yearly: pd.DataFrame) -> str:
    """生成 cash_decomposition_summary.md Markdown 内容。"""
    lines = [
        "# 现金来源拆解摘要",
        "",
        "## 全样本摘要",
        "",
        f"- 调仓信号总数: **{summary['n_signals']}**",
        f"- 全空仓信号: **{summary['n_all_cash']}** 次 ({summary['pct_all_cash']}%)",
        f"- 平均目标仓位: **{summary['avg_position']:.2%}**",
        f"- 中位目标仓位: **{summary['median_position']:.2%}**",
        f"- 平均现金: **{summary['avg_total_cash']:.2%}**",
        "",
        "### 现金来源分解",
        "",
    ]
    sources = summary["cash_by_source"]
    total = summary["avg_total_cash"]
    source_names = {
        "trend_gate_cash": "趋势门槛",
        "crowd_cash": "拥挤度惩罚",
        "vol_scale_cash": "组合波动率缩放",
        "constraint_cash": "交易约束",
    }
    table_rows = []
    for key, name in source_names.items():
        val = sources[key]
        pct = val / total * 100 if total > 0 else 0
        table_rows.append({"现金来源": name, "平均贡献": f"{val:.2%}", "占总现金比例": f"{pct:.1f}%"})
    table_rows.append({"现金来源": "**合计**", "平均贡献": f"**{total:.2%}**", "占总现金比例": "100.0%"})
    lines.append(markdown_table(pd.DataFrame(table_rows)))
    lines.append("")
    if summary["identity_holds"]:
        lines.append("恒等式验证通过：四类现金之和 = 总现金 ✓")
    else:
        lines.append("⚠ 恒等式验证未通过，请检查数据。")
    lines.append("")

    ranked = sorted(sources.items(), key=lambda x: x[1], reverse=True)
    top2 = [(source_names.get(k, k), v) for k, v in ranked[:2]]
    top2_pct = sum(v for _, v in top2) / total * 100 if total > 0 else 0
    lines.append("## 关键结论")
    lines.append("")
    lines.append(
        f"主要现金来源是 **{top2[0][0]}**（{top2[0][1]:.2%}）和 "
        f"**{top2[1][0]}**（{top2[1][1]:.2%}），"
        f"合计解释 **{top2_pct:.1f}%** 的总现金。"
    )
    lines.append("")
    lines.append("## 分年度摘要")
    lines.append("")
    lines.append(markdown_table(yearly) if not yearly.empty else "_无分年度数据。_")
    lines.append("")
    return "\n".join(lines)


def write_phase0_artifacts(
    df: pd.DataFrame,
    summary: dict,
    yearly: pd.DataFrame,
    breakdown: pd.DataFrame,
    output_dir: str | Path,
    *,
    dataset_id: str = "",
    snapshot_id: str = "",
) -> Path:
    """将 Phase 0 三项产物 + manifest + status 写入 output_dir。"""
    root = Path(output_dir)
    tables_dir = root / "tables"
    reports_dir = root / "reports"
    tables_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    out_cols = [
        "date", "n_active", "is_all_cash",
        "sum_tilted", "sum_raw", "sum_before_constraints", "sum_final",
        "trend_gate_cash", "crowd_cash", "vol_scale_cash", "constraint_cash", "total_cash",
    ]
    df[out_cols].to_csv(tables_dir / "cash_decomposition.csv", index=False)
    breakdown.to_csv(tables_dir / "cash_state_breakdown.csv", index=False)

    report = build_summary_report(df, summary, yearly)
    (reports_dir / "cash_decomposition_summary.md").write_text(report, encoding="utf-8")

    write_json(root / "manifest.json", {
        "schema_version": 1,
        "run_id": root.name,
        "dataset_id": dataset_id,
        "snapshot_id": snapshot_id,
        "n_signals": summary["n_signals"],
        "avg_position": summary["avg_position"],
        "avg_total_cash": summary["avg_total_cash"],
        "identity_holds": summary["identity_holds"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    })
    write_json(root / "status.json", {
        "state": "completed",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    })
    return root
