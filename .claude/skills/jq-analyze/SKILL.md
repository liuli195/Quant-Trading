---
name: jq-analyze
description: 本地分析已保存的 JoinQuant 回测结果。用于读取 api_export.json、summary_metrics.json、tabs_raw、backtest_runs 目录或 test_batches manifest，生成 strategy-analysis.md、performance-analysis.md、batch-comparison.md 或 issue-log.md。该技能不启动云端回测，不修改策略代码。
---

# JQ Analyze

只做本地分析：单次回测报告、性能分析、批次对比。

## 使用

1. 先读 [references/workflow.md](references/workflow.md) <!-- pathref: jq_analyze_skill/references/workflow.md -->。
2. 单次策略分析用 [templates/analysis-report.md](templates/analysis-report.md) <!-- pathref: jq_analyze_skill/templates/analysis-report.md -->。
3. 单次性能分析用 [templates/performance-report.md](templates/performance-report.md) <!-- pathref: jq_analyze_skill/templates/performance-report.md -->。
4. 批次对比必须通过 `manifest.json` 的 `primary_run_id` 映射结果。

## 边界

- 不打开聚宽，不消耗云端额度。
- 不修改策略代码。
- 缺数据时建议 `jq-run` 补抓。
- 发现代码问题时建议 `jq-fix`。
