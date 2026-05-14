# 性能分析报告

## 1. 性能分析概览

- 策略名称：etf_factor_rotation（动量RSRS相对倾斜版）
- 是否启用 `enable_profile()`：是（代码第 1 行）
- 实际计算耗时：1.41 分钟（云端回测，含数据获取）
- 回测链接：<https://www.joinquant.com/algorithm/backtest/detail?backtestId=775e3d35921112503655717fa185f106>
- 数据来源：profile.md（总耗时追踪）

## 2. 主要耗时函数

| 函数名 | 总耗时(s) | 占比 | 说明 |
| --- | --- | --- | --- |
| `get_history_data` | 23.89 | 52.0% | 4 字段 × 3 ETF 数据拉取 |
| `fetch_field` | 23.01 | 50.1% | 逐 ETF 调用 get_price |
| `compute_rsrs_tilt_multipliers` | 8.42 | 18.3% | RSRS 倾斜（含 adjusted_scores） |
| `compute_rsrs_adjusted_scores` | 8.36 | 18.2% | rolling β/R² 向量化计算 |
| `compute_crowd_penalties` | 7.71 | 16.8% | 五指标分位数计算 |
| `percentile_rank` | 1.89 | 4.1% | 拥挤度分位排名 |
| `execute_rebalance` | 1.85 | 4.0% | 下单与订单审计 |
| `compute_momentum_scores` | 1.56 | 3.4% | 多周期排名动量 |
| `_log_step` | 0.78 | 1.7% | 中间量诊断日志 |
| `compute_trend_gates` | 0.63 | 1.4% | 趋势均线判断 |
| `compute_rp_weights` | 0.38 | 0.8% | 逆波动率权重 |
| `compute_portfolio_vol_scale` | 0.31 | 0.7% | 组合协方差缩放 |
| 其他（<0.1s） | 0.26 | 0.6% | 参数、合成、约束等 |

## 3. 热点路径解读

### 最耗时路径：数据获取（~52%）
`get_history_data` → `fetch_field` 占半数以上耗时。每次调仓拉取 4 个字段（close/high/low/amount）× 3 只 ETF = 12 次 `get_price` 调用。这是云端 I/O 瓶颈，非本地计算可优化。

### 第二大热点：RSRS 计算（~18%）
`compute_rsrs_adjusted_scores` 对每只 ETF 执行 pandas rolling + cov/var 向量化计算。虽然已优化（一次 rolling 计算全部 β/R²），但 3 只 ETF × 600 期滚动的 pct_change 开销仍然可观。这是正确的性能特征，无需优化。

### 第三大热点：拥挤度惩罚（~17%）
`compute_crowd_penalties` 中的 `percentile_rank` 逐 ETF 逐指标调用，是函数级调用次数最多的路径。已做 DataFrame 级批量计算优化（5 个指标 × 3 ETF），剩余开销来自 `percentile_rank` 的逐值比较。

### 新函数性能
- `compute_rsrs_tilt_multipliers`(8.42s) = `compute_rsrs_adjusted_scores`(8.36s) + 倾斜转换(0.06s)：倾斜转换本身开销极低，主体仍是 RSRS 原始信号计算
- `compute_momentum_tilt_multipliers`：0.023s，极轻量
- `apply_relative_tilts`：0.012s，极轻量
- 新增三个函数合计 <0.05s 额外开销，对总耗时几乎无影响

### 旧函数状态
- `select_topk`：0s（已从主流程移除，未被调用）
- `compute_rsrs_multipliers`：0s（旧接口未被主流程调用，保留兼容）

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 减少 `fetch_field` 调用频率（双周调仓替代周频） | 总耗时减半 | 低 | 需评估策略收益影响 |
| 缓存 close_ret 避免各模块重复 pct_change | ~5% | 低 | 已在 get_history_data 中预计算一次 |
| percentile_rank 用 scipy.percentileofscore 替代 | ~2-3% | 中 | 需聚宽环境支持 scipy |
| RSRS 计算改用更小的 M 窗口（如 252 替代 600） | ~30% RSRS 耗时 | 中 | 需回测验证信号质量是否受影响 |

## 5. 建议优先级

1. **保持当前性能**——总耗时 1.41 分钟在 5.3 年回测中表现优异，无性能瓶颈需要立即处理
2. 如有需要缩短回测时间，优先考虑**降低调仓频率**（周频→双周频），可直接将数据获取减半
3. 长期可考虑**减小 RSRS_M 窗口**（600→252），但需先做 A/B 对比验证信号质量不变

## 6. 结论

- 当前最大耗时环节：数据获取（52%），属云端 I/O 限制，非代码优化可改善
- 计算密集环节 RSRS(18%) 和拥挤度(17%) 已做向量化优化，性能合理
- 新增倾斜函数（MomentumTilt、RSRSTilt、apply_relative_tilts）合计 <0.05s，改造未引入性能退化
- 总回测耗时 1.41 分钟在行业标准中表现良好，无需立即优化
