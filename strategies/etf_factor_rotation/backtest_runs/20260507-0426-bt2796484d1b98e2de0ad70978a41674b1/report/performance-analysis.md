# 性能分析报告 — TopK=3

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是
- 数据来源：JoinQuant 详情页只读 API
- 回测链接：https://www.joinquant.com/algorithm/backtest/detail?backtestId=2796484d1b98e2de0ad70978a41674b1

## 2. 主要耗时函数

| 函数名 | 总耗时(s) | 占比 | 调用次数 | 主要瓶颈 |
| --- | --- | --- | --- | --- |
| weekly_check | 46.67 | ~38% | ~277 次(周) | 回测主循环 |
| get_history_data | 23.87 | ~20% | — | 数据查询 I/O |
| fetch_field | 23.00 | ~19% | — | 字段获取 |
| compute_rsrs_multipliers | 8.35 | ~7% | ~277 次 | RSRS 回归计算 |
| compute_crowd_penalties | 7.70 | ~6% | ~277 次 | 拥挤度分位数 |
| execute_rebalance | 2.22 | ~2% | — | 下单执行（多一只 ETF） |
| percentile_rank | 1.87 | ~2% | — | 排序计算 |
| compute_momentum_scores | 1.54 | ~1% | ~277 次 | 多周期动量 |
| compute_trend_gates | 0.62 | ~1% | ~277 次 | 均线判断 |

## 3. 热点路径解读

- 最耗时函数：`weekly_check`（46.67s），与 TopK=2（46.37s）几乎相同，说明增加一只 ETF 对主循环影响不大。
- `execute_rebalance`：从 1.89s → 2.22s（+17%），因为持仓多一只，下单量增加，与交易笔数增幅（18%）一致。
- `compute_rp_weights`：从 0.34s → 0.40s（+18%），风险平价权重矩阵从 2×2 → 3×3。
- 数据查询 I/O 部分基本相同，因为拉取的是同一批 ETF 数据。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 数据缓存 — 同 TopK=2 方案 | 中 | 中 | 与持仓数量无关 |
| RSRS 计算批量优化 | 低-中 | 中 | TopK 增加不影响 RSRS 计算量（按全池计算） |
| 风险平价矩阵求逆缓存 | 低 | 低 | 3×3 矩阵求逆开销可忽略 |

## 5. 建议优先级

1. 数据缓存 — 与 TopK=2 相同，收益最大
2. RSRS 增量计算 — 与 TopK=2 相同
3. 无 TopK=3 特定优化项 — 增加一只 ETF 对性能影响极小（+0.3%）

## 6. 结论

- 当前最大性能问题：与 TopK=2 一致，数据 I/O 占主导。
- TopK=3 相比 TopK=2 的性能增量可忽略（total +0.3%），无需因性能原因限制 TopK 参数。
- 预计对回测耗时的改善：与 TopK=2 相同，数据缓存为主攻方向。
