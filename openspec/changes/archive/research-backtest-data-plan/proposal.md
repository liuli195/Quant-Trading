# jq_automation 研究环境回测结果主数据源改造计划

## Why
当前 jq_automation 通过聚宽详情页内部 XHR 接口抓取回测结果。详情页接口是网页内部契约，分页参数和字段结构可能随页面调整变化。聚宽官方研究环境提供 get_backtest() 可读取回测结果类数据。

## What Changes
- 将回测完成后的结果数据主数据源迁移到研究环境 get_backtest()
- 保持现有本地产物契约不变
- 保留详情页接口作为补充源和 fallback
- 新增 --result-source auto|research|detail 选项
- 新增 Bundle Schema v3

## Impact
契约稳定性提升，从私有网页接口切换到官方研究环境 API。平台日志仍不可通过研究环境获取完整版本，继续由详情页补充 runtime/profile/source/logs_partial。

---
source: docs/design/RESEARCH_BACKTEST_DATA_PLAN.md
