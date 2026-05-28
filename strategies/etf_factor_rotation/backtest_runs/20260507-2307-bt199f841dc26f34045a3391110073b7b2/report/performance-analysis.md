# 性能分析

## 回测概况

- 回测对象：ETF 因子轮动策略，`main` 分支硬趋势门槛版本。
- 回测区间：2021-01-01 至 2026-04-30。
- 回测 ID：`199f841dc26f34045a3391110073b7b2`。
- 实际云端计算时间：1.96 分钟。
- 数据来源：[profile.md](../tabs_raw/profile.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260507-2307-bt199f841dc26f34045a3391110073b7b2)/profile.md -->、[metadata.json](../metadata.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2307-bt199f841dc26f34045a3391110073b7b2)/metadata.json -->、[backtest_report.md](backtest_report.md) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2307-bt199f841dc26f34045a3391110073b7b2)/report/backtest_report.md -->。

## 主要耗时函数

| 函数名 | 总耗时 | 主要瓶颈 |
|---|---:|---|
| `weekly_check` | 64.3524s | 周度主链路总耗时 |
| `get_history_data` | 34.4418s | 历史行情读取与字段拼装 |
| `fetch_field` | 33.2638s | 多字段行情拉取 |
| `compute_rsrs_multipliers` | 11.6416s | RSRS 滚动回归与标准化 |
| `compute_crowd_penalties` | 10.5148s | 拥挤度指标分位数计算 |
| `percentile_rank` | 2.52193s | 分位数辅助计算 |
| `execute_rebalance` | 2.30559s | 下单与目标仓位调整 |
| `compute_momentum_scores` | 2.17631s | 多周期动量排名 |
| `compute_trend_gates` | 0.8629s | 硬趋势门槛计算 |

## 热点路径解读

性能热点集中在历史数据获取、RSRS 和拥挤度计算。`compute_trend_gates` 仅占 0.86 秒，不是瓶颈；硬门槛逻辑本身对计算开销影响很小。

`get_history_data` 与 `fetch_field` 时间接近，说明主要成本来自云端行情接口访问和数据框组装，而不是后续权重合成。RSRS 与拥挤度合计约 22 秒，是可优化的第二梯队。

## 优化建议

| 建议 | 预期收益 | 难度 | 备注 |
|---|---|---|---|
| 缓存周度所需历史字段，减少重复 `fetch_field` | 高 | 中 | 优先检查同一调仓日内字段是否重复拉取 |
| 对 RSRS 回归结果做滚动缓存 | 中 | 中 | 当前 ETF 池较小，但长周期累计明显 |
| 将拥挤度分位数计算向量化 | 中 | 中 | `percentile_rank` 是热点辅助函数 |
| 控制日志与 profile 开关 | 低 | 低 | `_log_step` 耗时不足 1 秒，暂非主瓶颈 |

## 结论

硬门槛版本的云端耗时可接受，主要开销不在趋势门槛本身。后续若要优化，应优先处理历史数据拉取、RSRS 和拥挤度计算链路。
