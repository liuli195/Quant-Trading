---
name: jq-run
description: 执行 JoinQuant 云端回测流程。用于上传本地 Python 策略到聚宽、浏览器编译、启动正式云端回测、只读抓取已有回测详情、保存云端结果、更新批次与场景映射。该技能有浏览器副作用且可能消耗每日云端额度，正式回测前必须先计划并等待用户确认。
---

# JQ Run

只做云端动作：上传、编译、回测、抓取、落盘。不做结果分析，不修策略代码。

## 使用

1. 先读 [references/workflow.md](references/workflow.md) <!-- pathref: jq_run_skill/references/workflow.md -->。
2. 操作聚宽页面或抓取数据时，再读 [references/browser-contracts.md](references/browser-contracts.md) <!-- pathref: jq_run_skill/references/browser-contracts.md -->。
3. 上传前用 [scripts/strip_comments.py](scripts/strip_comments.py) <!-- pathref: jq_run_skill/scripts/strip_comments.py --> 生成上传版。
4. 抓取后用 [scripts/save_backtest_data.py](scripts/save_backtest_data.py) <!-- pathref: jq_run_skill/scripts/save_backtest_data.py --> 落盘。

## 边界

- 正式云端回测前，先输出计划并等用户确认。
- 浏览器操作前先跑本地 `py_compile`。
- 每日云端额度按 60 分钟保护。
- 一次确认只跑用户批准的场景。
- 编译失败或策略问题交给 `jq-fix`。
- 报告和多场景对比交给 `jq-analyze`。
