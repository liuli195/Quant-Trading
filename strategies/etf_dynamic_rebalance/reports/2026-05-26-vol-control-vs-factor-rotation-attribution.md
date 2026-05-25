# ETF 动态再平衡波控后 vs ETF 多因子轮动对比与归因

生成日期：2026-05-26

## 口径

本报告只使用仓库内已有数据与报告，未发起新的聚宽云端回测。

主比较口径：

- 动态再平衡默认波控：`target_vol=0.08 / portfolio_vol_window=40`，run `20260526-0229-btee809d4cea8f278df764d8dd0c195e5f`，作为“波控后默认结果”。证据：[param-scan-summary.json](../test_batches/20260526-vol-control-calmar-confirm/report/param-scan-summary.json) <!-- pathref: strategies/etf_dynamic_rebalance/test_batches/20260526-vol-control-calmar-confirm/report/param-scan-summary.json -->、[summary_metrics.json](../backtest_runs/20260526-0229-btee809d4cea8f278df764d8dd0c195e5f/summary_metrics.json) <!-- pathref: strategies/etf_dynamic_rebalance/backtest_runs/20260526-0229-btee809d4cea8f278df764d8dd0c195e5f/summary_metrics.json -->
- 动态再平衡高目标波动候选：`target_vol≈0.296684`，run `20260526-0214-bt24c9d8b410c21d7da6229fe0d3c94901`，只作为收益上限候选，不作为默认建议。证据同上。
- ETF 多因子轮动：执行时序正式比较里的 `baseline`，run `20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718`，作为代码定义口径的正式基线。证据：[dataset.json](../../../research_datasets/etf_factor_rotation_backtest_runs/20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718/dataset.json) <!-- pathref: research_datasets/etf_factor_rotation_backtest_runs/20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718/dataset.json -->、[cloud_comparison.md](../../etf_factor_rotation/reports/research/execution_timing/runs/2026-05-18-cloud-confirmation/reports/cloud_comparison.md) <!-- pathref: strategies/etf_factor_rotation/reports/research/execution_timing/runs/2026-05-18-cloud-confirmation/reports/cloud_comparison.md -->

## 核心结论

在默认波控口径下，ETF 多因子轮动整体优于动态再平衡波控版：年化更高、回撤更低、Sharpe 和 Calmar 都更好。动态再平衡默认波控把原策略风险压下来了，但压仓后没有超过多因子轮动的风险收益效率。

动态再平衡高目标波动候选能拿到更高收益，但本质接近满仓，风险画像接近波控前旧策略。它相对默认波控的 Calmar 只高 `0.009`，却多承担 `4.48pct` 最大回撤和 `4.30pct` 年化波动，不适合作为稳健默认值。

## 指标对比

| 指标 | 动态默认波控 | 动态高目标候选 | 多因子轮动 baseline |
| --- | ---: | ---: | ---: |
| 总收益 | 109.85% | 171.73% | 118.32% |
| 年化收益 | 15.46% | 21.40% | 16.35% |
| 最大回撤 | 11.95% | 16.43% | 7.99% |
| Calmar | 1.294 | 1.302 | 约 2.05 |
| Sharpe | 1.261 | 1.297 | 1.498 |
| 策略波动率 | 9.10% | 13.40% | 8.20% |
| Alpha | 0.129 | 0.195 | 0.131 |
| Beta | 0.252 | 0.387 | 0.137 |
| 平均目标仓位 | 68.95% | 98.70% | 57.91% |
| 平均现金 | 31.05% | 1.30% | 42.09% |
| 调仓信号 | 1289 | 1289 | 272 |
| 实际下单事件 | 426 | 540 | 377 |

解读：

- 多因子轮动比动态默认波控年化高 `0.89pct`，最大回撤低 `3.96pct`，Sharpe 高 `0.237`，Calmar 高约 `0.75`。
- 动态默认波控的 Beta 是多因子轮动的约 `1.84` 倍，但收益没有更高，说明 8% 波控后的风险预算使用效率不如多因子轮动。
- 动态高目标候选比多因子轮动年化高 `5.05pct`，但最大回撤高 `8.44pct`，Beta 约 `2.82` 倍，Sharpe 和 Calmar 都更低。

## 动态再平衡波控归因

波控前旧动态再平衡几乎长期满仓。新增 `target_vol=0.08` 后，风险下降明显：

| 指标 | 波控前旧策略 | 默认波控后 | 变化 |
| --- | ---: | ---: | ---: |
| 总收益 | 175.56% | 109.85% | -65.71pct |
| 年化收益 | 21.73% | 15.46% | -6.27pct |
| 最大回撤 | 16.82% | 11.95% | -4.87pct |
| 年化波动率 | 13.55% | 9.09% | -4.46pct |
| Beta | 0.396 | 0.252 | -0.144 |
| 平均 ETF 仓位 | 98.49% | 69.89% | -28.60pct |

归因判断：

- 风控有效：最大回撤、波动率、Beta 都明显下降。
- 主要代价是长期降仓：现金从约 `1.51%` 提高到约 `30%`，上涨阶段也被同步压缩。
- 这不是资产选择失效，更多是总风险预算被压低。原报告显示三类资产平均权重大致等比例下降，黄金、AI、纳指的收益贡献都被压缩。

证据：[vol-control-comparison-attribution.md](../backtest_runs/20260526-0041-bt4ff080af1035efa8930129872f3f644d/report/vol-control-comparison-attribution.md) <!-- pathref: strategies/etf_dynamic_rebalance/backtest_runs/20260526-0041-bt4ff080af1035efa8930129872f3f644d/report/vol-control-comparison-attribution.md -->。

## 多因子轮动归因

多因子轮动的优势来自更完整的“退出 + 降仓”链路，而不是单一因子：

- 趋势门槛：趋势不成立时资产权重归零，是低回撤的重要来源；深度归因里黄金趋势门最强，纳指其次，AI 方向为正但统计强度较弱。
- 风险平价与组合波动缩放：平均目标仓位约 `58%`，平均现金约 `42%`，Beta 只有 `0.137`。
- 拥挤惩罚：机制保留，但阈值仍是“机制有效、参数待继续确认”。黄金已提高阈值到 `0.80`，AI 和纳指保留 `0.60`。
- 动量和 RSRS：动量强度有改善迹象但不足以写回；RSRS 对 AI/纳指偏正，黄金接近中性偏负，不支持整体反向处理。

现金来源拆解显示，多因子轮动平均现金 `42.84%`，其中组合波动率缩放贡献 `25.15%`，占总现金 `58.7%`；拥挤惩罚贡献 `7.93%`，趋势门槛贡献 `6.99%`。这解释了它为什么回撤低，也解释了上涨弹性为什么弱于满仓动态策略。

证据：[cash_decomposition_summary.md](../../etf_factor_rotation/reports/research/cash_utilization/runs/2026-05-17-phase0-baseline/reports/cash_decomposition_summary.md) <!-- pathref: strategies/etf_factor_rotation/reports/research/cash_utilization/runs/2026-05-17-phase0-baseline/reports/cash_decomposition_summary.md -->、[2026-05-14-deep-attribution.md](../../etf_factor_rotation/reports/2026-05-14-deep-attribution.md) <!-- pathref: strategies/etf_factor_rotation/reports/2026-05-14-deep-attribution.md -->、[2026-05-17-momentum-strength-confirmation-decision.md](../../etf_factor_rotation/reports/2026-05-17-momentum-strength-confirmation-decision.md) <!-- pathref: strategies/etf_factor_rotation/reports/2026-05-17-momentum-strength-confirmation-decision.md -->。

## 对比判断

### 默认波控 vs 多因子轮动

多因子轮动更好。它用更低仓位、更低 Beta 拿到了更高年化和更低回撤。动态默认波控虽然已经降风险，但还停留在“满仓投影后再整体缩放”的框架，缺少多因子轮动那种趋势门、TopK、拥挤惩罚和不归一化留现金的组合约束。

### 高目标候选 vs 多因子轮动

动态高目标候选适合解释收益上限，不适合解释稳健默认。它的收益更高，但风险接近旧的满仓动态再平衡；相对多因子轮动，Sharpe 和 Calmar 都落后。

### 策略角色

- 多因子轮动：更适合作为当前稳健主线，优点是低回撤、低 Beta、风险收益效率高；缺点是现金多，上涨段弹性不足。
- 动态默认波控：适合作为动态再平衡的稳健版，但目前被多因子轮动在主要风险收益指标上压过。
- 动态高目标候选：适合高收益偏好或收益上限观察，不适合作为默认风险控制结果。

## 数据限制

- 本报告没有新跑云端回测，只复用本地已有导出、数据中心镜像和既有报告。
- 动态 `20260526-0041...` 归因报告有用，但数据集标记为 `partial=true`，缺 `audit_log.jsonl`；因此只作为收益、仓位、交易层归因辅助，不作为主代表 run。
- 多因子轮动 `baseline` 是代码定义口径，不等于真实人工延迟执行口径；已有执行时序报告显示延迟执行会让最大回撤明显变差。
- 两个策略调仓频率不同：动态再平衡日频，多因子轮动周频；平均仓位和订单数量不能直接当作同口径交易成本结论。
