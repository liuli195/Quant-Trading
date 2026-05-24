# 数据完整性报告

- 状态：incomplete
- 生成时间：2026-05-24T13:04:32.188134+00:00

## 问题
- research_bundle: research get_backtest bundle is required
- audit_log: audit log is missing

## 检查项

| 检查项 | 必须 | 状态 | 来源 | 记录数 | partial | 说明 |
| --- | --- | --- | --- | ---: | --- | --- |
| research_bundle | 是 | fail | api_export.json |  |  | research get_backtest bundle is required |
| detail_api_bundle | 是 | pass | api_export.json |  |  | detail API bundle is required |
| metadata | 是 | pass | metadata.json |  |  |  |
| summary_metrics | 是 | pass | summary_metrics.json |  |  |  |
| detail_results | 是 | pass | api_export.json | 2 | False |  |
| detail_transactions | 是 | pass | api_export.json | 1 | False |  |
| detail_positions | 是 | pass | api_export.json | 4 | False |  |
| detail_risk_tabs | 是 | pass | api_export.json | 10 |  |  |
| platform_logs | 否 | pass | api_export.json | 16 | False | platform logs may be partial; audit_log is canonical |
| audit_log | 是 | fail | tabs_raw/audit_log.jsonl | 0 | True | audit log is missing |
