# 性能分析

## 回测概况

- 回测对象：ETF 因子轮动策略，`默认工作区` 分支软趋势门槛版本。
- 回测区间：2021-01-01 至 2026-04-30。
- 回测 ID：`fe11e835821438464da31fd4f4d995e1`。
- 实际云端计算时间：1.43 分钟。
- 数据来源：[profile.md](../tabs_raw/profile.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260507-2310-btfe11e835821438464da31fd4f4d995e1)/profile.md -->、[metadata.json](../metadata.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2310-btfe11e835821438464da31fd4f4d995e1)/metadata.json -->、[backtest_report.md](backtest_report.md) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2310-btfe11e835821438464da31fd4f4d995e1)/report/backtest_report.md -->。

## 主要耗时函数

| 函数名 | 总耗时 | 主要瓶颈 |
|---|---:|---|
| `weekly_check` | 46.8607s | 周度主链路总耗时 |
| `get_history_data` | 24.1162s | 历史行情读取与字段拼装 |
| `fetch_field` | 23.2281s | 多字段行情拉取 |
| `compute_rsrs_multipliers` | 8.4142s | RSRS 滚动回归与标准化 |
| `compute_crowd_penalties` | 7.73815s | 拥挤度指标分位数计算 |
| `execute_rebalance` | 2.1357s | 下单与目标仓位调整 |
| `percentile_rank` | 1.89768s | 分位数辅助计算 |
| `compute_momentum_scores` | 1.70117s | 多周期动量排名 |
| `compute_trend_gates` | 0.641163s | 软趋势门槛计算 |

## 热点路径解读

软门槛版本的主要热点仍然是历史数据读取、RSRS 和拥挤度计算。`compute_trend_gates` 只有 0.64 秒，线性映射没有引入可见性能问题。

本次软门槛实际云端计算时间低于硬门槛，但这更可能来自云端运行环境和执行路径差异，不应仅凭单次 A/B 推断软门槛天然更快。可确定的是，软门槛新增逻辑不是性能瓶颈。

## 优化建议

| 建议 | 预期收益 | 难度 | 备注 |
|---|---|---|---|
| 优先缓存历史行情字段 | 高 | 中 | `fetch_field` 与 `get_history_data` 仍是最大热点 |
| 缓存 RSRS 中间序列 | 中 | 中 | 长周期下累计耗时明显 |
| 向量化拥挤度分位数 | 中 | 中 | 可减少 `percentile_rank` 反复计算 |
| 保持软门槛实现简单 | 低 | 低 | 当前 `compute_trend_gates` 开销很小 |

## 结论

软门槛版本性能通过。它提升了交易参与度和收益表现，但没有把趋势门槛计算变成热点。后续优化应继续聚焦数据拉取、RSRS 和拥挤度链路，而不是软门槛公式本身。
