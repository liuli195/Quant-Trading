# 性能分析报告

> run_id: `20260505-2023-bt41b9a777fa2e2f1ce80858aec7d140aa`
> 场景: s03-fix-data-pipeline（数据管道修复验证）

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 是否启用 `enable_profile()`：是
- 数据来源：API 全量（joinquant_detail_readonly_api）
- 回测链接：https://www.joinquant.com/algorithm/backtest/detail?backtestId=41b9a777fa2e2f1ce80858aec7d140aa
- 回测区间：2024-01-01 ~ 2024-06-30（约 26 周调仓）

## 2. 主要耗时函数

| 函数名 | 总耗时 | 占 weekly_check | 说明 |
| --- | --- | --- | --- |
| weekly_check | 4.356s | 100% | 26 次周调仓总耗时 |
| get_history_data | 2.207s | 50.7% | 数据拉取（12 次 get_price/周） |
| fetch_field | 2.122s | 48.7% | 逐 ETF 拉取 4 字段 |
| compute_rsrs_multipliers | 0.851s | 19.5% | 滚动窗口 β 回归 |
| compute_crowd_penalties | 0.740s | 17.0% | 五指标分位计算 |
| execute_rebalance | 0.196s | 4.5% | 下单与停牌检查 |
| percentile_rank | 0.191s | 4.4% | 分位排名（拥挤度子函数） |
| compute_momentum_scores | 0.154s | 3.5% | 多周期排名分数 |
| compute_trend_gates | 0.057s | 1.3% | MA120 计算 |
| compute_rp_weights | 0.036s | 0.8% | 逆波动率权重 |
| compute_portfolio_vol_scale | 0.029s | 0.7% | 协方差 + 缩放 |

## 3. 热点路径解读

- **最耗时路径**：`weekly_check → get_history_data → fetch_field → get_price`（占 50.7%）。逐 ETF 拉取将 API 调用从 4 次/周增到 12 次/周，是主要时间开销。
- **计算热点**：`compute_rsrs_multipliers`（19.5%）和 `compute_crowd_penalties`（17.0%）合计占 36.5%。两者都涉及大窗口滚动计算（RSRS_M=600, CrowdWindow=500）。
- **percentile_rank 被高频调用**：拥挤度计算中对每只 ETF 的 5 个指标各调一次，每周期 15 次调用，累计 0.191s。
- **单次调仓耗时**：~0.168s/周（4.356s ÷ 26 周），在合理范围内。
- **对比修复前**：修复前回测 1 年仅 10 CPU 秒（空仓，数据拉取直接失败），修复后 6 个月约 4.36s，主要增量来自真实数据拉取和计算。

## 4. 逐 ETF 拉取的性能影响

| 指标 | 修复前（整池拉取） | 修复后（逐 ETF） | 变化 |
|------|-------------------|-----------------|------|
| get_price 调用/周 | 4 次 | 12 次 | +200% |
| 数据拉取总耗时 | ~0s（失败） | 2.122s | 从失败到正常 |
| 实际数据可用性 | 0（空 DataFrame） | 717 行/ETF | 修复核心问题 |

逐 ETF 拉取的可维护性和确定性远超性能开销。12 次 API 调用对于聚宽免费额度（每日数万次）完全可承受。

## 5. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 缩短 RSRS_M 从 600 到 250 | 减少 ~40% RSRS 耗时 | 低 | 需回测验证信号质量不变 |
| 缩短 CrowdWindow 从 500 到 250 | 减少 ~50% 拥挤度耗时 | 低 | 对拥挤度指标敏感度有影响 |
| percentile_rank 向量化 | 减少 50%+ 分位计算耗时 | 中 | 需要改为 scipy.percentileofscore |
| 一次性拉取 OHLC + amount | 减少 API 调用 12→3 | 高 | 需处理多字段返回格式 |

## 6. 建议优先级

1. **缩短 RSRS_M 和 CrowdWindow**（低难度、低风险）— 当前窗口 600/500 天约 2.5 年，缩短到 250 天仍覆盖 1 年市场周期，可减少 40~50% 计算时间。需先在云端回测对比信号差异。
2. **percentile_rank 向量化**（中难度）— 当前逐 ETF 调用的 for 循环可改为 scipy.stats.percentileofscore 批量计算。
3. **合并 API 调用**（高难度、高风险）— 一次 get_price 拉 all fields，但需要验证多字段返回格式兼容性。建议保持现有方案，除非回测时间成为瓶颈。

## 7. 结论

- **当前最大性能问题**：数据拉取占 50% 耗时，但这是数据管道修复的必然代价，优先级低。
- **最值得优先处理的改动**：缩短 RSRS_M 和 CrowdWindow 参数，降低滚动窗口计算量，预计可减少 30% 总耗时。
- **预计对回测耗时的改善**：参数调整后每次调仓约 0.12s（当前 0.17s），全年 52 次约 6.2s（当前 8.7s 推算），减少约 30%。
- **数据管道修复结论**：逐 ETF 拉取方案性能可接受，信号质量已验证，建议保持当前架构。
