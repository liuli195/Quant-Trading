# 性能分析报告

## 1. 性能分析概览

- 策略名称：etf_factor_rotation（ETF 因子轮动）
- 是否启用 `enable_profile()`：是（profile 数据共 3,065 条记录，覆盖所有策略函数）
- 数据来源：聚宽云端 `enable_profile()` 输出
- 回测链接：<https://www.joinquant.com/algorithm/backtest/detail?backtestId=c3196b4b03d329d6f426ef7b43ca7a17>
- 回测区间：2025-04-01 至 2026-04-30，约 54 个调仓周

## 2. 主要耗时函数

| 函数名 | 总耗时 (s) | 占比 | 调用次数 | 主要瓶颈 |
| --- | --- | --- | --- | --- |
| `weekly_check` | 9.33621 | 72.6% | ~54 | 调仓主入口，包含完整信号链 |
| `get_history_data` | 4.57503 | 35.6% | ~54 | 逐 ETF 拉取多字段 OHLC |
| `fetch_field` | 4.39297 | 34.1% | ~216 (4 fields x 54) | `get_price` 网络 IO |
| `compute_rsrs_multipliers` | 1.90355 | 14.8% | ~54 | OLS 回归（RSRS_M=600） |
| `compute_crowd_penalties` | 1.68529 | 13.1% | ~54 | 滚动窗口 percentile_rank |
| `percentile_rank` | 0.440231 | 3.4% | ~54 (被 crowd 调用) | 逐行滚动 rank 计算 |
| `execute_rebalance` | 0.386149 | 3.0% | ~54 | 下单执行与 order_target_value |
| `compute_momentum_scores` | 0.341065 | 2.7% | ~54 | 多周期动量计算 |
| `compute_trend_gates` | 0.126165 | 1.0% | ~54 | MA120 计算 |
| `_log_step` | 0.120746 | 0.9% | ~432 (8 x 54) | 逐 ETF 格式化字符串 |
| `compute_rp_weights` | 0.075252 | 0.6% | ~54 | 协方差矩阵 + 逆波动率 |
| `compute_portfolio_vol_scale` | 0.052422 | 0.4% | ~54 | 组合波动率计算 |
| `compose_raw_weights` | 0.00084 | <0.01% | ~54 | numpy 逐元素乘法 |
| `apply_weight_constraints` | 0.001241 | <0.01% | ~54 | 阈值裁剪 |
| `snapshot_params` | 0.00297 | <0.01% | ~54 | 参数快照 |
| `initialize` | 0.00204 | <0.01% | 1 | 初始化配置 |
| `compute_history_count` | 0.00039 | <0.01% | ~54 | max 计算 |
| `validate_params` | 0 | 0% | 1 | 无操作 |
| `set_parameter` | 0 | 0% | 0 | 未调用 |
| `normalize_field_frame` | 0 | 0% | 0 | 未调用 |
| **合计** | **12.85909** | **100%** | | |

## 3. 热点路径解读

### 3.1 最耗时函数：数据拉取（fetch_field + get_history_data）

`fetch_field` 和 `get_history_data` 合计 **8.97s**，占总耗时 69.7%，是压倒性的性能瓶颈。

根本原因在于当前实现逐 ETF 拉取数据：

```python
for etf in pool:
    df = get_price(etf, count=count, ...)  # 每个 ETF 一次网络往返
```

3 只 ETF x 4 个字段（close/high/low/money）= **12 次 `get_price` 网络调用**，每次调仓均重复此过程。聚宽的 `get_price` 调用存在显著的序列化/网络开销。

改进方向：聚宽 API 支持一次传入多只 ETF 代码，理论上可将 12 次调用压缩为 4 次（一次多标的拉取一个字段）。

### 3.2 重复调用热点：逐 ETF 数据逐步拉取

`fetch_field` 被 `get_history_data` 调用 4 次（每个字段一次），每次内部再对 pool 中每个 ETF 调用一次 `get_price`。这种两层循环导致了 3 x 4 = 12 次网络 IO。

同时，`weekly_check` 中还调用了 `_log_step` 8 次（每个调仓步骤一次），每次内部又循环 pool 逐 ETF 格式化，产生了 8 x 3 = 24 次字符串格式化操作，虽单次耗时低但累计可观。

### 3.3 RSRS 计算：高窗口 OLS 回归

`compute_rsrs_multipliers` 耗时 **1.90s**（14.8%），主要消耗在 `RSRS_M=600` 天窗口的 OLS 回归。对每只入选资产计算 (high-low) ~ close 的线性回归斜率及 R^2，窗口越长，滚动回归开销越大。

### 3.4 拥挤度惩罚：长窗口滚动计算

`compute_crowd_penalties` 耗时 **1.69s**（13.1%），其中 `percentile_rank` 贡献 0.44s。`CrowdWindow=500` 天的滚动窗口 percentile 计算是主要开销，尤其是对 3 只 ETF 逐只进行滚动 rank。

### 3.5 可能的 I/O 或数据处理瓶颈

- **网络 IO**：12 次 `get_price` 调用是最大瓶颈（占 70%），且无法通过纯代码优化消除。减少调用次数是唯一出路。
- **滚动窗口计算**：RSRS（600 天窗口）和拥挤度（500 天窗口）分别在每只 ETF 上做滚动 OLS 和滚动 rank，计算量随窗口长度和 ETF 数量线性增长。
- **日志输出**：`_log_step` 虽单次耗时低（0.12s 总计），但 8 步 x 3 只 ETF 的逐行字符串格式化在 54 周中产生了约 432 次日志写操作，属于可避免的固定开销。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| `fetch_field` 改为多标的批量拉取 | **高**（预计减少 6-7s，约 50-55% 总耗时） | 低 | `get_price(pool, ...)` 一次传入多代码，将 12 次调用压缩为 4 次 |
| 合并 `_log_step` 输出 | 低（减少约 0.1s） | 低 | 8 行日志合并为 2 行，减少字符串格式化和 I/O 次数 |
| RSRS 窗口自适应 | 中（预计减少 0.5-1s） | 中 | 在可用数据不足 600 天时自动缩短窗口；或缓存回归中间量 |
| 拥挤度每日增量计算 | 中（预计减少 0.5-1s） | 高 | 当前每调仓日重新计算 500 天滚动 rank，可改为缓存上一期结果 + 增量更新 |
| 数据拉取增加缓存复用 | 中（预计减少 1-2s） | 中 | `close` 已在 `get_history_data` 中被拉取，可复用给不需要 OHLC 的模块；避免重复拉取 |
| 降低 `CrowdWindow` 从 500 到 250 | 中（预计减少 0.3-0.5s） | 低 | 需评估信号质量损失，若可接受则直接缩减窗口 |
| 降低 `RSRS_M` 从 600 到 400 | 低-中（预计减少 0.2-0.4s） | 低 | 需评估 RSRS 信号稳定性，若短窗口信号足够则调整 |

## 5. 建议优先级

1. **批量拉取数据（`fetch_field` 多标的化）** -- 投入产出比最高的优化。将当前 `for etf in pool: get_price(etf, ...)` 改为 `get_price(pool, ...)` 可一次性消除大部分网络 IO 等待，预计节省 50%+ 总耗时，实施难度低。

2. **RSRS 和拥挤度的窗口自适应/缓存** -- 当前两个模块合计占 28% 耗时。若能实现滚动计算的增量更新或自适应缩短窗口，可在不削弱信号质量的前提下再节省 1-2s。

3. **日志精简** -- 虽然收益小，但实施成本极低。将 8 步逐 ETF 日志合并为 1-2 行 JSON/CSV 格式，减少 I/O 开销的同时提升日志可读性和可解析性。

## 6. 结论

- **当前最大性能问题**：`fetch_field` 的逐 ETF 逐字段数据拉取模式，共产生 12 次 `get_price` 网络调用，占回测总耗时约 70%。
- **最值得优先处理的改动**：将 `fetch_field` 从单标的循环改为多标的一次性批量拉取，预计可减少 50% 以上耗时，实施简单且不改变策略逻辑。
- **预计对回测耗时的改善**：经过批量拉取 + RSRS/拥挤度增量计算 + 日志精简三项优化后，单次 13 月回测耗时预计可从约 13s 降至 3-5s（减少 60-75%），在批量测试场景下收益尤其显著。
