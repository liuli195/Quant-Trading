# ETF 波动缩减 A/B 实验

## Why
设计并执行 ETF 因子轮动策略的组合波控现金再利用云端 A/B 回测，比较当前基准、固定黄金弱缩放、动态低边际风险弱缩放三组结果。

## What Changes
- 策略端增加可关闭的组合波控弱缩放模式（baseline / fixed_gold / dyn_marginal）
- 3 组云端完整回测：baseline_current、fixed_gold_f50_r2、dyn_marginal_f100_r1.5_mom
- 新增审计字段：portfolio_vol_relief_mode、portfolio_vol_ratio 等
- 深度归因报告：持仓变化、收益与回撤 delta、决策规则

## Impact
正式策略默认值保持当前行为。候选逻辑只能通过参数打开，不能默认启用。如果候选不通过决策规则，保持默认策略不变并记录原因。

---
source: docs/superpowers/plans/2026-05-26-etf-vol-relief-ab-test.md
