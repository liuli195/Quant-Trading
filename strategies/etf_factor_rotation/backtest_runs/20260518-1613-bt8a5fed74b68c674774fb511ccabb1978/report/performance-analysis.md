# 性能分析报告

> 回测运行：`20260518-1613-bt8a5fed74b68c674774fb511ccabb1978`
> 策略：ETF 多因子轮动策略（相对倾斜版）

## 1. 性能分析概览

- 策略名称：ETF 多因子轮动策略（相对倾斜版）
- 是否启用 `enable_profile()`：是（`enable_profile()` 在第 1 行）
- 数据来源：`tabs_raw/profile.md`（5,342 条记录）
- 回测区间：2021-01-01 ~ 2026-04-30（1,289 个交易日）
- 云端实际计算时间：1.70 分钟

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占比 | 调用说明 | 主要瓶颈 |
| --- | --- | --- | --- | --- |
| `weekly_check` | 71.258s | 100% | 每周一次，约 280 次 | 调仓主函数，包含所有子模块 |
| `get_history_data` | 27.630s | 38.8% | 每周 4 次字段拉取 | 逐 ETF 串行拉取 OHLC + 成交额 |
| `fetch_field` | 26.572s | 37.3% | 每次 get_history_data 调用 4 次 | `get_price()` API 逐 ETF 调用 |
| `audit_event` | 19.233s | 27.0% | 每次调仓 + 每笔订单 | `write_file()` JSONL 磁盘写入 |
| `execute_rebalance` | 16.167s | 22.7% | 每周一次 | `order_target_value()` + 审计事件写入 |
| `compute_rsrs_tilt_multipliers` | 9.284s | 13.0% | 每周一次 | 委托 `compute_rsrs_adjusted_scores` |
| `compute_rsrs_adjusted_scores` | 9.220s | 12.9% | 每周一次 | 逐 ETF 滚动回归（N=18, M=600） |
| `compute_crowd_penalties` | 8.439s | 11.8% | 每周一次 | DataFrame 级批量计算 + 逐 ETF 分位排名 |
| `percentile_rank` | 2.026s | 2.8% | 拥挤度计算每次 15 次 | 被 `compute_crowd_penalties` 内部调用 |
| `compute_momentum_scores` | 1.718s | 2.4% | 每周一次 | 多周期排名计算 |
| `_log_step` | 0.818s | 1.1% | 每次调仓 7-8 次 | `log.info()` 字符串格式化 |
| `compute_trend_gates` | 0.700s | 1.0% | 每周一次 | 逐 ETF 均线计算 |
| `compute_rp_weights` | 0.415s | 0.6% | 每周一次 | 逆波动率计算 |
| `compute_portfolio_vol_scale` | 0.329s | 0.5% | 每周一次 | 协方差矩阵 + 组合波动率 |

> 注：占比累加超过 100%，因为 `weekly_check` 包含了子函数调用时间。子函数耗时反映各自内部的纯计算开销。

## 3. 热点路径解读

### 最耗时路径：数据拉取（~39%）
`get_history_data` → `fetch_field` 链占用近 40% 总耗时。根本原因是**逐 ETF 串行调用 `get_price()`**：
```python
for etf in pool:  # 3 ETFs × 4 fields = 12 次串行 get_price() 调用
    df = get_price(etf, count=needed, ...)
```
每次调用涉及聚宽服务端查询，串行化导致网络往返时间累加。若改为批量拉取（一次 `get_price` 传多个标的），可减少 2/3 的 API 调用次数。

### 次热路径：审计事件写入（~27%）
`audit_event` 占用 19.2 秒，通过 `write_file(..., append=True)` 逐条追加 JSONL。每次调仓产生约 5-10 条审计事件（信号 + 每笔订单），每条事件都触发一次独立文件 I/O。批量积累后一次性写入可显著减少磁盘操作。

### RSRS 计算（~13%）
`compute_rsrs_adjusted_scores` 逐 ETF 执行 `high.rolling(N).cov(l)` 和 `low.rolling(N).var()`。`rolling()` 操作本身已向量化，但外围仍是逐 ETF Python 循环。考虑到 `N=18, M=600` 的参数，每个 ETF 需要约 618 天数据，计算本身不算特别重，主要开销在 pandas rolling 操作的内部开销。

### 拥挤度惩罚（~12%）
`compute_crowd_penalties` 虽然是 DataFrame 级批量计算，但内层 `percentile_rank` 对每只 ETF 的 5 个指标分别调用，产生了 15 次 / 周 × 280 周 ≈ 4,200 次调用。每次 `percentile_rank` 涉及 `(series < value).mean()` 的全序列比较。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 数据拉取改为批量 `get_price()` | 减少 ~20s（28%） | 中 | 需要验证批量 `get_price` 返回格式，可能需要适配 `normalize_field_frame` |
| 审计事件批量写入 | 减少 ~12s（17%） | 低 | 积累到调仓结束后一次 `write_file`，但需注意聚宽研究环境文件写入限制 |
| RSRS 改为纯 numpy 向量化 | 减少 ~4s（6%） | 高 | 需要将 pandas rolling 替换为 numpy 滑动窗口，涉及较多底层代码 |
| `percentile_rank` 内联 | 减少 ~1s（1.5%） | 低 | 将 `percentile_rank` 逻辑内联到 `compute_crowd_penalties` 减少函数调用开销 |
| `get_history_data` end_date 预计算 | 边际 | 低 | 避免每次 `fetch_field` 都构建参数 |

## 5. 建议优先级

1. **数据拉取批量化**（预期收益最大，直接减少 28% 耗时）——将 3 只 ETF 的 `get_price` 合并为单次调用
2. **审计事件批量写入**（实施难度最低，收益 17%）——累积后写入替代逐条追加
3. **`percentile_rank` 内联**（低难度优化）——减少 Python 函数调用开销
4. **RSRS numpy 向量化**（收益中等、难度高，可延后）——在更长回测区间时更有价值

## 6. 结论

- **当前最大性能问题**：数据拉取（`fetch_field`）和审计事件（`audit_event`）合计占用约 65% 总耗时，都不是计算密集型任务，而是 I/O 密集型
- **最值得优先处理的改动**：将 3 只 ETF × 4 字段的 12 次串行 `get_price()` 合并为批量拉取，可直接节省约 20 秒。这个改动对策略逻辑无影响，风险低
- **预计对回测耗时的改善**：若数据拉取和审计写入两项优化均实施，预计 5.3 年回测耗时从 71 秒降至 ~40 秒（减少约 44%），云端计费时间从 1.70 分钟降至约 1.0 分钟
