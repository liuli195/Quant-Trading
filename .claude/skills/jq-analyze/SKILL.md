---
name: jq-analyze
description: 本地分析已保存的 JoinQuant 回测结果。用于读取 api_export.json、summary_metrics.json、tabs_raw、backtest_runs 目录或 test_batches manifest，生成 strategy-analysis.md、performance-analysis.md、batch-comparison.md 或 issue-log.md。支持 fix-missing（补全缺失报告）、trend（多运行趋势跟踪）、cross-strategy（跨策略对比）三种扩展模式。该技能不启动云端回测，不修改策略代码。
---

# JQ Analyze

只做本地分析：单次回测报告、性能分析、批次对比、趋势跟踪、跨策略对比。

## 使用

1. 先读 [references/workflow.md](references/workflow.md) <!-- pathref: jq_analyze_skill/references/workflow.md -->。
2. 单次策略分析用 [templates/analysis-report.md](templates/analysis-report.md) <!-- pathref: jq_analyze_skill/templates/analysis-report.md -->。
3. 单次性能分析用 [templates/performance-report.md](templates/performance-report.md) <!-- pathref: jq_analyze_skill/templates/performance-report.md -->。
4. 批次对比必须通过 `manifest.json` 的 `primary_run_id` 映射结果。

## 扩展模式

### --fix-missing

扫描 `strategies/<strategy>/backtest_runs/` 下所有运行，对缺少 `report/strategy-analysis.md` 或 `report/performance-analysis.md` 的目录自动补全。不覆盖已有报告。

### --trend <run_id> <run_id> ...

在同一策略的多个运行间检测 5 项核心指标的时序趋势（年化收益、Sharpe、最大回撤、平均仓位、换手率）。产出 [templates/batch-trend-report.md](templates/batch-trend-report.md) <!-- pathref: jq_analyze_skill/templates/batch-trend-report.md -->，标注改善/恶化方向。

### --cross-strategy <strategy_a>:<run_id> <strategy_b>:<run_id>

对比两个不同策略在相同区间的表现。按仓位差异（择时贡献）和持仓差异（选股贡献）分解收益差。产出 [templates/cross-strategy-report.md](templates/cross-strategy-report.md) <!-- pathref: jq_analyze_skill/templates/cross-strategy-report.md -->。

## 边界

- 不打开聚宽，不消耗云端额度。
- 不修改策略代码。
- 缺数据时建议 `jq-run` 补抓。
- 发现代码问题时建议 `jq-fix`。
