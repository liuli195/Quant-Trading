# 性能分析报告 — R4 长周期基线

## 1. 性能分析概览

- 策略名称：ETF 多因子轮动策略（线性乘数版）
- 是否启用 `enable_profile()`：是
- 数据来源：`tabs_raw/profile.md`（3065 条记录）
- 回测链接：<https://www.joinquant.com/algorithm/backtest/detail?backtestId=ac5a03b99d8722f55b0a05a57554abf0>
- 云端实际计算：**2.13 分钟**（8.3 年全区间）
- 总调用：`weekly_check` 累计耗时 69.62s（约 400+ 次周级调仓检查）

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占比 | 主要瓶颈 |
|--------|--------|------|----------|
| `get_history_data` | 37.65s | 54.1% | 聚宽 `get_price` 批量取数（日线 OHLC + amount） |
| `fetch_field` | 36.30s | 52.1% | 被 `get_history_data` 调用，单字段批次取数 |
| `compute_rsrs_multipliers` | 12.25s | 17.6% | 滚动回归计算（N×M 窗口），向量化但仍重 |
| `compute_crowd_penalties` | 11.46s | 16.5% | 五指标多窗口分位数计算 |
| `percentile_rank` | 2.71s | 3.9% | 滚动分位数（被拥挤度模块频繁调用） |
| `execute_rebalance` | 2.51s | 3.6% | `order_target_value` 下单执行 |
| `compute_momentum_scores` | 2.42s | 3.5% | 多周期排名计算 |
| `_log_step` | 0.96s | 1.4% | 格式化日志输出 |
| `compute_trend_gates` | 0.93s | 1.3% | MA120 均线比较 |
| `compute_rp_weights` | 0.51s | 0.7% | 逆波动率权重 |
| `compute_portfolio_vol_scale` | 0.39s | 0.6% | 组合波动率缩放 |

> 注：`fetch_field` 的耗时已包含在 `get_history_data` 内；两者占比超过 100% 是因 profile 的累计方式（子函数调用时间计入父函数）。

## 3. 热点路径解读

### 最耗时函数：`get_history_data` / `fetch_field`（54.1%）

数据获取是最大的时间消耗。每次周级调仓需要取约 800-1000 根日线 K 线的 OHLC + amount（4-5 个字段），3 个 ETF 标的约需取 15 个字段序列。聚宽的 `get_price` 是纯内存/磁盘查询，但 8 年 × 52 周 × 3 标的的数据拉取累计量仍然可观。

### 第二热点：`compute_rsrs_multipliers` (17.6%)

RSRS 计算对每个标的需要做 RSRS_N×RSRS_M 窗口（默认 N=18, M=600）的滚动 OLS 回归（High ~ Low），计算 β 和 R²。8 年约 2000+ 个交易日的滚动均值，纯向量化 numpy 运算虽快但窗口大、频次高。

### 第三热点：`compute_crowd_penalties` (16.5%)

拥挤度五指标（短期收益、中期收益、成交额偏离、价格偏离、波动率拥挤）在 CrowdWindow=200 窗口内计算分位数。每个指标需要独立的 `percentile_rank` 调用。

### I/O 瓶颈分析

- 聚宽 API 数据获取占绝对主导（>54%），优化空间有限（已是批量 `get_price` 调用）
- 计算函数全部向量化，在 400+ 次调用下累计耗时合理
- 单次 `weekly_check` 平均 ~0.17s，属于高效水平

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
|------|----------|----------|------|
| 缓存 `get_price` 数据：跨周复用以周为单位的日线仓位 | 节省 30-40% 取数时间 | 中 | 同一标的重复拉取历史日线，可缓存 |
| 降低 RSRS_M 默认值（800→400） | 节省 ~8% RSRS 计算时间 | 低 | 需回测验证信号差异 |
| 使用 `get_bars` 替代 `get_price` 的部分字段查询 | 节省 10-15% 取数时间 | 低 | `get_bars` 对 OHLC 字段更高效 |
| `percentile_rank` 预计算：同一窗口内数据可跨标的复用 | 节省 20-30% 分位数计算 | 中 | 拥挤度五指标的窗口相同时可合并 |
| 降低日志输出级别或采样写入 | 节省 ~1% | 低 | 当前日志量已较小（858 INFO） |

## 5. 建议优先级

1. **缓存 `get_price` 数据** — 最大单一收益，周级调仓天然适合缓存历史日线
2. **`get_bars` 替代 `get_price`** — 改动小，聚宽 `get_bars` 对日线 OHLC 直接返回，无需字段映射
3. **`percentile_rank` 跨标的复用** — 减少滚动分位数重复计算

## 6. 结论

- 当前最大性能问题：**数据获取（get_price）** 占 54% 的总耗时，是唯一值得优化的瓶颈
- 最值得优先处理的改动：引入日线数据缓存，跨周复用（单次拉取约 800 天 × 3 标的，多周完全重合）
- 预计对回测耗时的改善：引入缓存后 8 年回测可从 2.13 min 降至约 1.3-1.5 min
- 整体评价：**策略计算效率优秀**，8 年全区间仅 2.13 分钟云端 CPU 时间，远低于 35 分钟的预算上限
