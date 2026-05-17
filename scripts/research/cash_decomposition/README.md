# cash_decomposition — 现金来源拆解分析

纯函数库，从研究数据集的 Parquet 主存储中读取 `rebalance_signals` 审计事件，
将总现金归因到四个来源：趋势门槛、拥挤度惩罚、组合波动率缩放、交易约束。

**调用入口**：

```python
from scripts.research.cash_decomposition.analysis import decompose_from_dataset, \
    yearly_summary, position_quantile_breakdown, build_summary_report, write_phase0_artifacts
```

## API

### decompose_from_dataset(dataset_id, snapshot_id, *, datasets_root="research_datasets")

从指定数据集快照的 Parquet 主存储读取数据，计算四层现金归因。

返回 `(DataFrame, dict)`：
- `DataFrame` — 272 行调仓信号，含 `trend_gate_cash`、`crowd_cash`、`vol_scale_cash`、`constraint_cash`、`total_cash` 等列
- `dict` — 全样本摘要：`n_signals`、`avg_position`、`avg_total_cash`、`cash_by_source`、`identity_holds`

```python
df, summary = decompose_from_dataset(
    "etf_factor_rotation_baseline_audit",
    "2026-05-17T17-36-27Z_56361cf8a32e",
)
# summary["avg_position"]  → 0.5716
# summary["cash_by_source"]["vol_scale_cash"]  → 0.251518
```

### yearly_summary(df) → pd.DataFrame

按年分组统计现金来源。返回列：`year`、`n_signals`、`n_all_cash`、`avg_position` 及四类现金来源均值。

### position_quantile_breakdown(df) → pd.DataFrame

按 `年份 × 仓位分位 × 全空仓状态` 切片统计。仓位分位：`all_cash`（0%）、`low`（0%-33%）、`mid`（33%-66%）、`high`（66%+）。

### build_summary_report(df, summary, yearly) → str

生成 `cash_decomposition_summary.md` 格式的 Markdown 报告字符串。

### write_phase0_artifacts(df, summary, yearly, breakdown, output_dir) → Path

将 Phase 0 全套产物写入指定目录：

| 产物 | 路径 |
|---|---|
| `cash_decomposition.csv` | `output_dir/tables/` |
| `cash_state_breakdown.csv` | `output_dir/tables/` |
| `cash_decomposition_summary.md` | `output_dir/reports/` |
| `manifest.json` | `output_dir/` |
| `status.json` | `output_dir/` |

## 现金归因口径

四类现金来源满足恒等式验证（`atol=1e-8`）：

| 来源 | 计算 |
|---|---|
| 趋势门槛现金 | `1.0 - sum(tilted_weights)` |
| 拥挤度惩罚现金 | `sum(tilted) - sum(raw_weights)` |
| 组合波动率现金 | `sum(raw) - sum(final_weights_before_constraints)` |
| 交易约束现金 | `sum(before_constraints) - sum(final_weights)` |
| **总现金** | `1.0 - sum(final_weights)` |

## 示例：完整 Phase 0 工作流

```python
from scripts.research.cash_decomposition.analysis import (
    decompose_from_dataset, yearly_summary,
    position_quantile_breakdown, write_phase0_artifacts,
)

df, summary = decompose_from_dataset(
    "etf_factor_rotation_baseline_audit",
    "2026-05-17T17-36-27Z_56361cf8a32e",
)
yearly = yearly_summary(df)
breakdown = position_quantile_breakdown(df)

write_phase0_artifacts(
    df, summary, yearly, breakdown,
    output_dir="strategies/etf_factor_rotation/reports/research/cash_utilization/runs/my-phase0-run",
    dataset_id="etf_factor_rotation_baseline_audit",
    snapshot_id="2026-05-17T17-36-27Z_56361cf8a32e",
)
```

## 依赖

- `pandas`、`numpy`
- `scripts.research.platform.datasets.load_snapshot`（读取数据集快照）
- `scripts.research.research_core.reporting`（Markdown 表格、JSON 写入）
