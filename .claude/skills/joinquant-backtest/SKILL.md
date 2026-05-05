---
name: joinquant-backtest
description: 旧版 JoinQuant 回测技能兼容入口。仅当用户明确调用 joinquant-backtest 时使用；云端回测转到 jq-run，本地结果分析转到 jq-analyze，本地策略修复转到 jq-fix。
---

# JoinQuant Backtest

已拆成三个短技能：

- `jq-run`：云端上传、编译、回测、抓取、落盘。
- `jq-analyze`：本地报告和多场景对比。
- `jq-fix`：本地策略修复和验证。

用户继续调用 `/joinquant-backtest` 时，按意图路由到对应新技能，不再执行旧的端到端流程。
