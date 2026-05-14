# ETF 专属 MA_long 混合参数确认扫描

**批次**: `20260514-etf-ma-mixed-confirmation`  
**策略**: `etf_factor_rotation`  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**新跑组合**: 3 组 ETF 专属趋势均线。  
**复用对照**: 统一 `MA_long=120` 与统一 `MA_long=40` 直接引用 `20260508-hard-ma-scan` 既有 run，不重复消耗额度。  

## 1. 结论

`AI20_NQ40_Gold100` 是本轮最强组合：策略收益 93.13%、年化 13.62%、Sharpe 1.223，均高于统一 40 日对照；但最大回撤升至 8.54%，高于统一 40 日的 7.97% 和统一 120 日的 6.97%。

若优先追求收益和 Sharpe，应进入下一轮 A/B 或更长区间验证 `AI20_NQ40_Gold100`。若优先控制回撤和换手，`AI100_NQ40_Gold100` 与 `AI120_NQ40_Gold100` 相比统一 120 日有明显收益提升，但没有超过统一 40 日。

## 2. 横向指标

| 组合 | AI MA | 纳指 MA | 黄金 MA | 策略收益 | 年化收益 | 最大回撤 | Sharpe | Sortino | 信息比率 | 订单数 | 手续费 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `AI20_NQ40_Gold100` | 20 | 40 | 100 | 93.13% | 13.62% | 8.54% | 1.223 | 1.789 | 0.888 | 399 | 773.09 |
| `AI100_NQ40_Gold100` | 100 | 40 | 100 | 81.10% | 12.21% | 6.99% | 1.046 | 1.494 | 0.793 | 345 | 661.41 |
| `AI120_NQ40_Gold100` | 120 | 40 | 100 | 80.24% | 12.10% | 6.80% | 1.036 | 1.492 | 0.789 | 358 | 668.30 |
| `uniform_MA120_baseline` | 120 | 120 | 120 | 70.15% | 10.86% | 6.97% | 0.851 | 1.168 | 0.716 | 360 | 609.63 |
| `uniform_MA40_control` | 40 | 40 | 40 | 82.99% | 12.43% | 7.97% | 1.079 | 1.586 | 0.810 | 401 | 887.83 |

## 3. 相对对照

| 组合 | 相对统一 120 收益差 | 相对统一 120 年化差 | 相对统一 120 回撤差 | 相对统一 120 Sharpe差 | 相对统一 40 收益差 | 相对统一 40 年化差 | 相对统一 40 回撤差 | 相对统一 40 Sharpe差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `AI20_NQ40_Gold100` | +22.98pp | +2.76pp | +1.57pp | +0.372 | +10.14pp | +1.19pp | +0.57pp | +0.144 |
| `AI100_NQ40_Gold100` | +10.95pp | +1.35pp | +0.02pp | +0.195 | -1.89pp | -0.22pp | -0.98pp | -0.033 |
| `AI120_NQ40_Gold100` | +10.09pp | +1.24pp | -0.17pp | +0.185 | -2.75pp | -0.33pp | -1.17pp | -0.043 |

## 4. 解读

- `AI20_NQ40_Gold100` 验证了归因报告中的主假设：AI 使用短均线、纳指使用 40 日、黄金使用 100 日的混合配置，能超过本轮已知最强的统一 40 日组合。
- `AI100_NQ40_Gold100` 和 `AI120_NQ40_Gold100` 表明，如果放弃 AI 短均线，组合收益会回落到统一 40 日以下；AI=20 是本轮超额收益的关键变量。
- 交易代价方面，`AI20_NQ40_Gold100` 的订单数 399，接近统一 40 日的 401，但手续费 773.09 低于统一 40 日的 887.83；因此收益提升不是单纯靠更高换手换来的。
- 风险代价同样清楚：`AI20_NQ40_Gold100` 最大回撤 8.54%，为五组最高。下一轮需要重点检查 2021-11-22 ~ 2022-10-21 回撤区间的持仓和仓位缩放。

## 5. run_id 映射

| 组合 | run_id | 数据 |
| --- | --- | --- |
| `AI20_NQ40_Gold100` | `20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315` | [summary_metrics.json](../../../backtest_runs/20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315)/summary_metrics.json --> |
| `AI100_NQ40_Gold100` | `20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a` | [summary_metrics.json](../../../backtest_runs/20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a)/summary_metrics.json --> |
| `AI120_NQ40_Gold100` | `20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28` | [summary_metrics.json](../../../backtest_runs/20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28)/summary_metrics.json --> |
| `uniform_MA120_baseline` | `20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a` | [summary_metrics.json](../../../backtest_runs/20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a)/summary_metrics.json --> |
| `uniform_MA40_control` | `20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994` | [summary_metrics.json](../../../backtest_runs/20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994)/summary_metrics.json --> |

报告生成日期：2026-05-14。
