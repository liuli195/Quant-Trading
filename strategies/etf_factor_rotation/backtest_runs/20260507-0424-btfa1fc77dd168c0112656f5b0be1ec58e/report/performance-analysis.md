# 性能分析报告 — TopK=2

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是
- 数据来源：JoinQuant 详情页只读 API
- 回测链接：https://www.joinquant.com/algorithm/backtest/detail?backtestId=fa1fc77dd168c0112656f5b0be1ec58e

## 2. 主要耗时函数

| 函数名 | 总耗时(s) | 占比 | 调用次数 | 主要瓶颈 |
| --- | --- | --- | --- | --- |
| weekly_check | 46.37 | ~38% | ~277 次(周) | 回测主循环 |
| get_history_data | 24.29 | ~20% | — | 数据查询 I/O |
| fetch_field | 23.40 | ~19% | — | 字段获取 |
| compute_rsrs_multipliers | 8.42 | ~7% | ~277 次 | RSRS 回归计算 |
| compute_crowd_penalties | 7.73 | ~6% | ~277 次 | 拥挤度分位数 |
| percentile_rank | 1.91 | ~2% | — | 排序计算 |
| execute_rebalance | 1.89 | ~2% | — | 下单执行 |
| compute_momentum_scores | 1.56 | ~1% | ~277 次 | 多周期动量 |
| compute_trend_gates | 0.63 | ~1% | ~277 次 | 均线判断 |

## 3. 热点路径解读

- 最耗时函数：`weekly_check`（46.37s）是策略主循环，内部累加所有子模块耗时，本身不是优化目标。
- 数据获取瓶颈：`get_history_data`（24.29s）+ `fetch_field`（23.40s）合计约 47s，占 `weekly_check` 近一半。这是聚宽数据引擎的固有开销，本地优化空间有限。
- RSRS 计算：`compute_rsrs_multipliers`（8.42s）涉及 OLS 回归和滚动窗口，是除数据 I/O 外最重的计算模块。
- 拥挤度计算：`compute_crowd_penalties`（7.73s）需要对每个 ETF 计算五指标分位数，同样较重。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 缓存高频查询字段，减少聚宽 API 调用 | 中 | 中 | get_history_data 每次调仓都重新拉全量数据 |
| RSRS 滚动窗口复用前一周数据 | 低-中 | 中 | 目前每次从头计算滚动窗口 |
| 拥挤度分位数增量更新 | 低 | 高 | 分位数计算天然需要全量数据 |

## 5. 建议优先级

1. 数据缓存优化 — 减少重复 `get_history_data` 调用，收益最大
2. RSRS 增量计算 — 避免每次重算全窗口
3. 拥挤度指标缓存 — 非关键路径，酌情处理

## 6. 结论

- 当前最大性能问题：数据查询 I/O（`get_history_data` + `fetch_field`）占总耗时 ~40%，受限于聚宽平台，非纯 Python 层面可优化。
- 最值得优先处理的改动：数据缓存，减少重复字段拉取。
- 预计对回测耗时的改善：缓存后预计可节省 5-10s，总耗时从 ~120s 降至 ~110s，提升约 8%。考虑到实际计算仅 1.40 分钟（非 profile 模式），性能优化优先级不高。
