# ETF 动态调仓策略 — 性能分析报告（偏离度阈值 10%）

> 回测 ID：`cedcd4140dac2e6fee07a59ef4f0f1ea`
> 回测区间：2023-01-01 至 2026-04-30 | 策略代码总耗时：~58.4s
> [聚宽回测详情](https://www.joinquant.com/algorithm/backtest/detail?backtestId=cedcd4140dac2e6fee07a59ef4f0f1ea)

## 1. 性能分析概览

- 策略名称：ETF动态调仓_阈值010
- 是否启用 `enable_profile()`：是
- 数据来源：聚宽 profile 面板

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占比 | 核心瓶颈 |
| --- | --- | --- | --- |
| `daily_check` | 58.416s | ~99.9% | 因子计算 + jqlib 技术指标调用 |
| `compute_nasdaq_factors` | ~17.9s | ~30.7% | ROC(3次) + BIAS + 滚动波动率 |
| `compute_gold_factors` | ~13.9s | ~23.9% | BIAS + ROC + 滚动波动率 |
| `compute_ai_factors` | ~10.8s | ~18.5% | ROC + BIAS + 滚动波动率 |
| `zscore_clip` | ~0.69s | ~1.2% | 标准化裁剪 |
| `apply_weight_constraints` | ~0.07s | ~0.1% | Duchi 投影 |
| `compute_target_weights` | ~0.02s | <0.1% | 权重公式计算 |
| `initialize` | 0.002s | <0.01% | 一次性初始化 |
| `set_parameter` | 0s | 0% | 参数赋值 |

## 3. 热点路径解读

- **最耗时函数**：`daily_check` 占据几乎全部运行时间（58.4s），三个因子计算函数合计占约 73%。
- **compute_nasdaq_factors 最重**：17.9s 占 30.7%，ROC 调用 3 次 + BIAS + 波动率循环是主要开销。
- **compute_gold_factors**：13.9s 占 23.9%，黄金因子因使用 RS + RiskOff 额外指标，计算路径更复杂。
- **阈值对性能的影响**：10% 阈值相比 5% 阈值（76.5s）节省约 24% 的总耗时，因为调仓频率降低减少了 `order_target_value` 的执行次数。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 合并 BIAS/ROC 调用，缓存共享结果 | ~60ms/次，约节省 9% | 低 | 三个因子函数共用同一批技术指标 |
| 滚动波动率向量化（numpy） | ~15ms/次 | 中 | 替换 Python 循环 |
| 批量 `get_price` 一次拉取 | 减少 API 调用次数 | 低 | 当前每个因子函数独立调用 |

## 5. 建议优先级

1. 合并 BIAS/ROC 调用 — 收益明确、风险低
2. 批量 `get_price` — 减少网络开销
3. 滚动波动率向量化 — 中等收益、中等难度

## 6. 结论

- 当前最大性能问题：三个因子函数的独立技术指标计算造成重复工作
- 最值得优先处理的改动：合并技术指标调用，缓存共享结果
- 预计总体可节省 15-20% 的策略代码执行时间
