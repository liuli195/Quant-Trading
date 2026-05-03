# ETF 动态调仓策略 — 性能分析报告（偏离度阈值 5%）

> 回测 ID：`8c080de9278b81da01bf7ab3d5281680`
> 回测区间：2023-01-01 至 2026-04-30 | 策略代码总耗时：~76.5s
> [聚宽回测详情](https://www.joinquant.com/algorithm/backtest/detail?backtestId=8c080de9278b81da01bf7ab3d5281680)

## 1. 性能分析概览

- 策略名称：ETF动态调仓_阈值005
- 是否启用 `enable_profile()`：是
- 数据来源：聚宽 profile 面板

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占比 | 核心瓶颈 |
| --- | --- | --- | --- |
| `daily_check` | 76.512s | ~99.9% | 因子计算 + jqlib 技术指标调用 |
| `compute_nasdaq_factors` | ~17.9s | ~23.4% | ROC(3次) + BIAS + 滚动波动率 |
| `compute_gold_factors` | ~13.9s | ~18.2% | BIAS + ROC + 滚动波动率 |
| `compute_ai_factors` | ~10.8s | ~14.1% | ROC + BIAS + 滚动波动率 |
| `zscore_clip` | ~0.69s | <1% | 标准化裁剪 |
| `apply_weight_constraints` | ~0.07s | <1% | Duchi 投影 |
| `compute_target_weights` | ~0.02s | <1% | 权重公式计算 |
| `initialize` | 0.004s | <0.01% | 一次性初始化 |
| `set_parameter` | 0s | 0% | 参数赋值 |

## 3. 热点路径解读

- **最耗时函数**：`daily_check` 占据几乎全部运行时间，内部因子计算（三个 `compute_*_factors`）合计占比 >55%。
- **重复调用热点**：每个因子函数独立调用 `BIAS` 和 `ROC`，这些聚宽内置指标内部会重复拉取历史数据，造成大量重复 I/O。
- **滚动波动率瓶颈**：每个因子函数内部用 Python 循环计算滚动波动率（`for i in range(window, len(closes))`），而非向量化，是大数据量下的主要性能杀手。

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

- 当前最大性能问题：三个因子函数的独立 BIAS/ROC/波动率计算造成大量重复工作
- 最值得优先处理的改动：合并技术指标调用，缓存共享结果
- 预计总体可节省 15-20% 的策略代码执行时间
