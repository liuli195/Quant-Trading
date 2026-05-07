# JQ Analyze 流程

## 单次回测

读取 `backtest_runs/<run_id>/`：

- `metadata.json`
- `summary_metrics.json`
- `all_data.json`
- `tabs_raw/*.md`

生成：

```text
report/strategy-analysis.md
report/performance-analysis.md
```

若 `profile.md` 为空，明确写“无性能剖析数据”。

## 批次对比

读取：

```text
strategies/<strategy>/test_batches/<batch_id>/manifest.json
```

只比较各场景 `primary_run_id` 指向的回测结果。

生成：

```text
strategies/<strategy>/test_batches/<batch_id>/report/batch-comparison.md
```

问题追加到：

```text
strategies/<strategy>/test_batches/<batch_id>/report/issue-log.md
```

不要把原始回测数据复制到批次目录。

## fix-missing（补全缺失报告）

1. 扫描 `<strategy>/backtest_runs/` 下所有包含 `metadata.json` 的目录。
2. 检查 `report/strategy-analysis.md` 和 `report/performance-analysis.md` 是否存在。
3. 对缺失的报告，读取 `metadata.json` + `summary_metrics.json` + `all_data.json` + `tabs_raw/*.md`。
4. 按 [analysis-report.md](../templates/analysis-report.md) 和 [performance-report.md](../templates/performance-report.md) 模板生成。
5. 记录补全状态（已补全 / 跳过-数据不足）。

## 趋势跟踪（--trend）

1. 按 run_id 的 metadata 日期排序。
2. 从每个运行的 `summary_metrics.json` 提取：annual_return、sharpe、max_drawdown、avg_position、turnover_rate。
3. 计算时序趋势（线性回归斜率 / r²）。
4. 标注方向：↑ 改善（Sharpe 升/回撤降）、↓ 恶化、→ 平稳（r² < 0.3）。
5. 产出 [batch-trend-report.md](../templates/batch-trend-report.md)。

## 跨策略对比（--cross-strategy）

1. 校验两个运行的 start_date/end_date，不一致时警告但继续。
2. 分别读取 summary_metrics.json + all_data.json + tabs_raw。
3. 对齐交易日计算日收益序列的相关系数。
4. 分解收益差：
   - **择时差异**：仓位不同的时间段的收益差
   - **选股差异**：持仓标的不同的时间段的收益差
5. 按市场状态（上涨月 / 下跌月 / 震荡月）分段对比。
6. 产出 [cross-strategy-report.md](../templates/cross-strategy-report.md)。
