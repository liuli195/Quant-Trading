# 性能分析报告 — RMM=1.5 (Best)

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是
- 数据来源：`profile.md`（tabs_raw）
- 回测链接：[聚宽详情](https://www.joinquant.com/algorithm/backtest/detail?backtestId=736ee37bca600a5d26239e618b0bb7a3)

## 2. 主要耗时函数

性能分布与 RMM=1.0 baseline 一致（策略代码结构相同，仅参数值不同）：

| 函数名 | 占比 | 主要瓶颈 |
| --- | --- | --- |
| `weekly_check` | 100% | 主调仓循环 |
| `get_history_data` + `fetch_field` | ~50%+ | **数据 I/O** |
| `compute_rsrs_multipliers` | ~18% | OLS 回归计算 |
| `compute_crowd_penalties` | ~17% | 滚动窗口计算 |
| `execute_rebalance` | ~4% | 下单执行 |
| `compute_momentum_scores` | ~3% | 动量计算 |

## 3. 热点路径解读

逻辑和热点与 baseline 完全相同。唯一的差异在于 RMM=1.5 更多买入交易（196 vs 178），`execute_rebalance` 耗时可能略增，但绝对值仍在秒级，影响可忽略。

## 4. 优化建议

与 baseline 报告一致，详见 `backtest_runs/20260507-0509-.../report/performance-analysis.md`。

## 5. 结论

RMM 参数变化不引入性能差异。当前最大瓶颈仍是数据 I/O。
