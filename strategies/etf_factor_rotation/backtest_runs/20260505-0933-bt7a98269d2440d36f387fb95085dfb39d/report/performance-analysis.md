# 性能分析报告

> run_id: `20260505-0933-bt7a98269d2440d36f387fb95085dfb39d`
> 场景: s02-default-baseline (R1 默认基线)

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是（策略第一行）
- 数据来源：`/algorithm/backtest/profile?backtestId=7a98269d2440d36f387fb95085dfb39d&ajax=1`
- 回测链接：https://www.joinquant.com/algorithm/backtest/detail?backtestId=7a98269d2440d36f387fb95085dfb39d
- 总耗时：**10.93 CPU 秒 / 8.71 墙钟秒**（1 年回测）

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占比 | 说明 |
| --- | --- | --- | --- |
| weekly_check | 3.241s | ~30% | 主调仓循环，装配各模块 |
| fetch_field | 2.302s | ~21% | `get_price` 数据拉取 × 4 字段 |
| normalize_field_frame | 0.763s | ~7% | 数据归一化（空 DataFrame 处理） |
| _log_step | 0.080s | ~1% | 8 次 × 52 周 = 416 次日志调用 |
| compose_raw_weights | 0.001s | <0.1% | 权重合成（几乎零开销） |
| snapshot_params | 0.003s | <0.1% | 参数快照 |
| initialize | 0.002s | <0.1% | 初始化（一次调用） |
| compute_history_count | 0.000s | <0.1% | 计算所需历史长度 |
| set_parameter | 0.000s | <0.1% | 参数设置 |
| validate_params | 0.000s | <0.1% | 参数校验 |

> 注：除以上函数外，其余 ~4.5s（~41%）为框架开销和未单独 profile 的计算函数（compute_trend_gates, compute_momentum_scores, compute_rp_weights, compute_rsrs_multipliers, compute_crowd_penalties, compute_portfolio_vol_scale 等）。

## 3. 热点路径解读

- **最耗时函数**：`weekly_check` (3.24s) 和 `fetch_field` (2.30s) 合计占 ~51%。数据拉取是最大瓶颈。
- **数据拉取特征**：每周 4 次 `get_price` 调用（close/high/low/amount），52 周 × 4 = 208 次 API 调用。`fetch_field` 单次约 11ms，属于正常范围。
- **数据归一化开销**：`normalize_field_frame` 累�7 0.76s，因为数据为空时仍执行了列操作，可考虑空数据快速返回优化。
- **日志开销**：`_log_step` 0.08s 占比很低，日志量合理。
- **信号计算函数**：compute_* 系列函数（趋势门槛、动量、RSRS、拥挤度等）未被 profile 单独捕获，估计合计约 4~5s，其中 RSRS 滚动窗口计算（rolling + cov/var）可能是主要开销。

## 4. 性能评估（闸门检查）

按照 batch-plan.md 闸门标准：

| 闸门指标 | 阈值 | 实际 | 通过 |
|----------|------|------|------|
| 1 个月回测耗时 | — | ~1s | ✅ |
| 1 年回测耗时（R1） | < 30S | 10s | ✅ |
| 编译耗时 | < 10s | < 2s | ✅ |
| 日志量是否异常增长 | — | 672 行/年 | ✅ |

**结论**：性能表现优秀，1 年完整回测仅 10 CPU 秒，远超预期。即使包含 RSRS 高窗口计算和拥挤度多指标计算，整体耗时在预算内。

## 5. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 空数据快速返回 | 0.5~0.7s | 低 | `normalize_field_frame` 检查空数据后直接返回，跳过 reindex 操作 |
| 减少 fetch_field 调用 | 0.5~1s | 中 | 将 `fields=['close','high','low','money']` 一次性拉取，而非 4 次独立调用 |
| close_ret 复用已生效 | — | — | 当前已实现 `pct_change()` 只算一次 |
| 目前无需优化 | — | — | 10 CPU 秒/年超出性能预期，优化收益有限 |

## 6. 建议优先级

1. **暂不优化** — 10s/年的性能远低于 60min/日的额度上限，性能不是当前瓶颈
2. 如果未来 ETF 池扩展到 10+ 标的或 5 年以上回测，再考虑合并 `get_price` 字段拉取
3. 如果未来发现 `compute_rsrs_multipliers` 高窗口计算成为热点，可考虑将 rolling + OLS 改为增量算法

## 7. 结论

- 当前最大性能问题：无明显性能问题。1 年回测 10 CPU 秒在预算内非常充裕
- 最值得优先处理的改动：无需处理。应先集中精力解决数据管道问题（history end_date=None）和趋势门槛过严导致的全年空仓
- 预计对回测耗时的改善：优化空间约 1~2s，对 60min/日额度影响可忽略
