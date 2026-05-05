# 性能分析报告 — ma_crossover (s01-baseline)

## 1. 性能分析概览

- 策略名称：ma_crossover（双均线交叉策略）
- 是否启用 `enable_profile()`：否
- 数据来源：`profile.md`（回测详情页性能标签页）
- 回测链接：https://www.joinquant.com/algorithm/backtest/detail?backtestId=48ef4a644906d1ada69ba04637aa4bb6

## 2. 主要耗时函数

无性能剖析数据 — 策略未启用 `enable_profile()`，且 `profile.md` 为空。

策略代码极简（35 行），主要计算操作为：
- `attribute_history()` — 每周期拉取 21 天收盘价
- `pandas.mean()` — 计算短/长均线

## 3. 热点路径解读

- 最耗时函数：`attribute_history` 为唯一外部数据调用，预计占总耗时 90%+
- 重复调用热点：`handle_data` 每分钟触发一次，但策略逻辑极简（两次 mean 计算 + 两次比较），单次调用 < 1ms
- 可能的瓶颈：当前回测区间仅 3 个月 56 个交易日，数据量极小，无法观测到性能瓶颈

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 启用 `enable_profile()` | 无性能提升，但可观测瓶颈 | 低 | 加一行代码即可 |
| 改用 `run_daily` 替代 `handle_data` | 消除每分钟冗余调用 | 低 | 从 ~240次/天 降至 1次/天 |
| 无额外优化需求 | — | — | 当前策略计算量微不足道 |

## 5. 建议优先级

1. 改用 `run_daily` 替代 `handle_data`（消除 99.6% 冗余调用）
2. （可选）启用 `enable_profile()` 以便后续性能观测

## 6. 结论

- 当前最大性能问题：`handle_data` 每分钟触发导致无意义的重复空仓检查（产生 32 条 WARNING 日志）
- 最值得优先处理的改动：改用 `run_daily(market_open, time='open')` 每天仅运行一次
- 预计对回测耗时的改善：微乎其微（当前策略计算开销可忽略），主要收益是日志清洁和语义清晰
