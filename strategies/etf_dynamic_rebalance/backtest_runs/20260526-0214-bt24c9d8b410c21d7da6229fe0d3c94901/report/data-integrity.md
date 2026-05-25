# 数据完整性报告

- 状态：complete
- 生成时间：2026-05-25T18:17:32.222154+00:00

## 问题
- 无

## 检查项

| 检查项 | 必须 | 状态 | 来源 | 记录数 | partial | 说明 |
| --- | --- | --- | --- | ---: | --- | --- |
| research_bundle | 是 | pass | api_export.json |  |  | research get_backtest bundle is required |
| detail_api_bundle | 是 | pass | detail_api_export.json |  |  | detail API bundle is required |
| metadata | 是 | pass | metadata.json |  |  |  |
| summary_metrics | 是 | pass | summary_metrics.json |  |  |  |
| research_results | 是 | pass | api_export.json | 1289 | False |  |
| research_positions | 是 | pass | api_export.json | 3867 | False |  |
| research_orders | 是 | pass | api_export.json | 501 | False |  |
| research_risk | 是 | pass | api_export.json | 31 | False |  |
| detail_results | 是 | pass | detail_api_export.json | 1485 | False |  |
| detail_transactions | 是 | pass | detail_api_export.json | 501 | False |  |
| detail_positions | 是 | pass | detail_api_export.json | 5156 | False |  |
| detail_risk_tabs | 是 | pass | detail_api_export.json | 640 |  |  |
| platform_logs | 否 | warn | detail_api_export.json | 1000 | True | platform logs may be partial; audit_log is canonical |
| audit_log | 是 | pass | tabs_raw/audit_log.jsonl | 3120 | False |  |
