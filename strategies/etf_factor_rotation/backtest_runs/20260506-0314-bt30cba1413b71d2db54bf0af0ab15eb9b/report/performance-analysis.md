# 性能分析报告

> 冒烟测试回测 | 区间仅 1 个月，profile 数据有限但可用

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是（profile 记录 3067 条）
- 数据来源：聚宽云端 profile 标签页（tabs_raw/profile.md）
- 回测链接：<https://www.joinquant.com/algorithm/backtest/detail?backtestId=30cba1413b71d2db54bf0af0ab15eb9b>

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占总比（估算） | 调用次数（推算） | 主要瓶颈 |
| --- | --- | --- | --- | --- |
| `weekly_check` | 1.5105s | ~38.0% | 4 次（周调仓） | 主调度函数，包含所有子调用，时间 = 子函数之和 |
| `get_history_data` | 0.819953s | ~20.6% | 4 次 | `get_price` / `get_extras` 云端数据拉取 |
| `fetch_field` | 0.780616s | ~19.6% | 4 次 | 金融字段批量查询，聚宽数据 API |
| `compute_rsrs_multipliers` | 0.283207s | ~7.1% | 4 次 | RSRS 回归计算（N=18, M=600 标准化窗口），OLS 回归 |
| `compute_crowd_penalties` | 0.274293s | ~6.9% | 4 次 | 拥挤度：量价指标计算 + 百分位排名 |
| `percentile_rank` | 0.062852s | ~1.6% | 多次 | 排序 + 百分位映射 |
| `compute_momentum_scores` | 0.042100s | ~1.1% | 4 次 | 多周期动量加权（20/60/120 日） |
| `execute_rebalance` | 0.037628s | ~0.9% | 4 次 | 订单生成与委托（聚宽 order 开销） |
| `compute_trend_gates` | 0.018785s | ~0.5% | 4 次 | MA120 趋势判断 |
| `_log_step` | 0.012093s | ~0.3% | 多次 | 日志格式化与输出 |
| `compute_rp_weights` | 0.008345s | ~0.2% | 4 次 | 风险平价：协方差矩阵 + 权重优化 |
| `initialize` | 0.006331s | ~0.2% | 1 次 | 初始化（仅回测启动时一次） |
| `compute_portfolio_vol_scale` | 0.004405s | ~0.1% | 4 次 | 组合波动率缩放计算 |
| `snapshot_params` | 0.000395s | <0.1% | 1 次 | 参数快照 |
| `select_topk` | 0.000166s | <0.1% | 4 次 | TopK 筛选 |
| `apply_weight_constraints` | 0.000155s | <0.1% | 4 次 | 权重裁剪与归一化 |
| `compose_raw_weights` | 0.000102s | <0.1% | 4 次 | 初始权重组合 |
| `compute_history_count` | 0.000055s | <0.1% | 1 次 | 历史数据条数计算 |
| `set_parameter` | 0s | 0% | 1 次 | 参数设置 |
| `validate_params` | 0s | 0% | 1 次 | 参数校验 |
| `normalize_field_frame` | 0s | 0% | 1 次 | 数据框规范化 |

## 3. 热点路径解读

### 最耗时函数：`weekly_check`（1.511s）

`weekly_check` 是策略的主调度函数，其时间实际由子函数累加构成。去除子调用后，`weekly_check` 自身的纯调度开销极小（<5ms）。

实际热点函数为：

1. **`get_history_data`（0.820s）** — 数据拉取最耗时
   - 包含对聚宽 `get_price`（日线行情）和 `get_extras`（额外金融数据）的调用
   - 每次调仓需拉取 MA120 趋势判断所需的历史数据（至少 120 个交易日的日线 + 额外字段）
   - 这是 I/O 密集型开销，受聚宽云端 API 响应时间制约，代码层面优化空间有限

2. **`fetch_field`（0.781s）** — 金融字段查询第二耗时
   - 聚宽 `get_extras` 或自定义字段的批量查询
   - 与 `get_history_data` 合计约 1.6s，占总耗时约 40%
   - 同属数据获取层，优化空间小

3. **`compute_rsrs_multipliers`（0.283s）** — 计算最密集
   - RSRS 计算包含对每只 ETF 做 OLS 回归（N=18 的回归窗口，M=600 的标准化窗口）
   - 3 只 ETF，每只需滚动回归和标准化，计算量大但聚宽上均为向量化，通常不是主要瓶颈

4. **`compute_crowd_penalties`（0.274s）** — 计算第三密集
   - 包含成交量 MA、价格偏离度、波动率等量价指标计算
   - 涉及 `percentile_rank` 排序操作，在 Pandas 上效率尚可

### 重复调用热点

- 所有 `compute_*` 函数每周期调用 1 次，4 周共 4 次，调用频率低无重复问题。
- `percentile_rank` 被 `compute_crowd_penalties` 调用，1 个月区间内调用次数有限。
- `_log_step` 在每个计算步骤后调用，4 周约产生 76 条日志，单条开销约 0.16ms，可忽略。

### 可能的 I/O 或数据处理瓶颈

- **聚宽数据 API 响应延迟**：`get_history_data` + `fetch_field` 合计 ~1.6s 是本策略单次调仓的主要耗时来源，占总时间约 40%。这是聚宽云端的固有延迟，代码无法消除。
- **1 个月回测的 profile 代表性不足**：仅 4 次调仓、3067 条 profile 记录，总耗时约 4 秒，各函数统计稳定性有限。更长时间区间的 profile 才能提供更可靠的瓶颈定位。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 缓存历史数据结果 | 中（减少 10-20%） | 中 | 若多只 ETF 共享同一数据源，可在 `get_history_data` 内缓存已拉取的 `get_price` 结果，避免重复调用。当前代码每只 ETF 独立拉取，存在冗余。 |
| 精简 profile 记录 | 低（<5%） | 低 | 3067 条 profile 中可能包含重复或过于细粒度的统计，可适当放宽 profile 采样间隔，但生产回退不太关键。 |
| 合并 `get_history_data` 和 `fetch_field` | 中（10-15%） | 高 | 若两只函数的数据源有重叠，可合并为一次批量查询。需仔细分析数据依赖并可能需改动策略数据流架构。 |
| RSRS 计算降采样 | 低（<5%） | 低 | `compute_rsrs_multipliers` 的 M=600 标准化窗口可用更粗粒度近似，但精度损失可能影响信号质量。 |
| WARNING 日志优化 | 低（功能层面） | 低 | 11 条 "positions 中不存在" WARNING 可通过下单前检查持仓来消除，减少噪音日志，但对性能影响可忽略。 |

## 5. 建议优先级

1. **缓存数据拉取结果**（收益中，难度中）— 在 `get_history_data` 中对同一批 ETF 共享的 `get_price` 调用做内存缓存，减少重复的云端 API 调用。这是当前最可行的优化手段。
2. **合并数据获取步骤**（收益中，难度高）— 审视 `get_history_data` 和 `fetch_field` 的数据依赖，若可合并，单次调仓可节省约 0.3-0.5s。
3. **延长回测区间的 profile 数据收集** — 本回测仅 1 个月，建议在 R1 级回测（1 年以上）中收集更充分的 profile 数据，以得到更精准的热点定位。

## 6. 结论

- **当前最大性能问题**：数据获取层（`get_history_data` + `fetch_field`）占单次调仓耗时约 40%，受聚宽云端 API 响应延迟制约。
- **最值得优先处理的改动**：缓存历史数据拉取结果，减少重复的 `get_price` 调用。
- **预计对回测耗时的改善**：在 1 个月区间内总耗时约 4s（4 次调仓），优化后预计可节省 0.5-1.0s。对于更长区间的回测，节省效果线性放大。但需注意，本回测区间的 profile 样本量有限，优化效果的量化估计不可靠，建议在更长回测中重新评估。
