# 性能分析报告 — RMM=1.0 (Baseline)

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是（聚宽内置 profiling）
- 数据来源：`profile.md`（tabs_raw）
- 回测链接：[聚宽详情](https://www.joinquant.com/algorithm/backtest/detail?backtestId=b4072def4c657fd2616313f5ac340f6e)

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占比 (weekly_check) | 调用特征 | 主要瓶颈 |
| --- | --- | --- | --- | --- |
| `weekly_check` | 44.75s | 100% | 主调仓循环 | 所有子函数之和 |
| `get_history_data` | 23.34s | 52.2% | 每次调仓调用 | **聚宽数据 API I/O** |
| `fetch_field` | 22.55s | 50.4% | 被 get_history_data 调用 | **聚宽字段提取 I/O** |
| `compute_rsrs_multipliers` | 8.16s | 18.2% | 每次调仓调用 | OLS 回归 + Z-score 计算 |
| `compute_crowd_penalties` | 7.53s | 16.8% | 每次调仓调用 | 滚动窗口计算 |
| `percentile_rank` | 1.86s | 4.2% | 被 crowd_penalties 调用 | 分位数排序 |
| `execute_rebalance` | 1.72s | 3.9% | 每次调仓调用 | 下单执行 |
| `compute_momentum_scores` | 1.53s | 3.4% | 每次调仓调用 | 多周期动量计算 |
| `_log_step` | 0.72s | 1.6% | 每次调仓调用 | 日志输出 |

## 3. 热点路径解读

- **最耗时路径**：数据获取链 `weekly_check → get_history_data → fetch_field` 耗时合计 45.89s（超过 weekly_check 自身耗时，因为包含上下文切换）。数据 I/O 占比超 50%，是最大瓶颈。
- **计算热点**：`compute_rsrs_multipliers`（8.16s）和 `compute_crowd_penalties`（7.53s）合计占计算时间的 ~65%。两者都涉及滚动窗口 + 每只 ETF 的逐标运算。
- **非热点函数**：`compute_rp_weights`（0.40s）、`compute_portfolio_vol_scale`（0.31s）、`select_topk`（0.01s）均在亚秒级，不是优化重点。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 缓存历史数据（单次回测内复用 get_history_data 结果） | 高（-10s+） | 低 | 同一次调仓中多次 get_history_data 应可复用 DataFrames |
| 减少 fetch_field 调用次数（一次获取多字段而非多次调用） | 高（-10s+） | 中 | 需评估聚宽 API 是否支持一次获取多字段 |
| RSRS 计算向量化优化（利用 numpy 批量运算替代逐标的 OLS 循环） | 中（-2~3s） | 中 | 当前 OLS 是逐 ETF 循环，可尝试全矩阵闭式解 |
| 拥挤度计算减少 percentile_rank 调用（缓存中间结果） | 中（-1~2s） | 低 | 滚动窗口中相邻两期大量重叠计算 |

## 5. 建议优先级

1. **缓存历史数据结果**（收益最大、难度最低、不改变计算语义）
2. **合并 fetch_field 调用**（与 #1 配合可减少 ~50% 的 I/O 时间）
3. **向量化 RSRS OLS 计算**（需要数学验证但收益可观）
4. **镜像优化拥挤度滚动计算**（较低优先级，收益递减）

## 6. 结论

- 当前最大性能问题：**数据 I/O 占超过一半的回测耗时**（get_history_data + fetch_field > 50%）
- 最值得优先处理的改动：缓存策略内复用历史数据，减少重复的 get_history_data 调用
- 预计对回测耗时的改善：优化数据 I/O 可减少 10-15s，总回测耗时从 ~45s 降至 ~30s（-33%）
