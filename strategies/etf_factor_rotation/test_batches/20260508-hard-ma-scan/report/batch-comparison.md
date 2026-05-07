# 硬门槛 MA_long 参数扫描报告

**批次**: `20260508-hard-ma-scan`  
**策略**: `etf_factor_rotation`  
**场景**: `s01-ma-long-scan`  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**扫描参数**: `MA_long` = 20 / 40 / 60 / 80 / 100 / 120 / 140 / 160，其中 120 日均线为对照组。  
**数据来源**: [manifest.json](../manifest.json) <!-- pathref: test_batch(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/manifest.json -->、[scenario.json](../scenarios/s01-ma-long-scan/scenario.json) <!-- pathref: test_scenario(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan, scenario_id=s01-ma-long-scan)/scenario.json -->、各 run 的 `summary_metrics.json` / `all_data.json`。  
**云端耗时**: 实际合计 12.13 分钟。额度账本见 [20260508.json](../../../../../docs/joinquant-data/quota_ledger/20260508.json) <!-- pathref: joinquant_quota_ledger/20260508.json -->。

## 1. 扫描目的

本轮只改变硬趋势门槛参数 `MA_long`，也就是“价格必须高于 N 日均线才可入选”的判断窗口。策略源码默认值没有被改动；每个候选值都由 batch 工具生成临时上传代码完成回测。

## 2. 核心指标

| MA_long | 角色 | 策略收益 | 年化收益 | 超额收益 | 最大回撤 | Sharpe | Sortino | Calmar | 信息比率 | 波动率 | 胜率 | 盈亏比 | 交易笔数 | 最大回撤区间 | run_id |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 120 | 对照组 | 70.15% | 10.86% | 84.45% | 6.97% | 0.851 | 1.168 | 1.558 | 0.716 | 0.081 | 76.9% | 2.932 | 360 | 2022-03-09 ~ 2022-12-16 | [20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a](../../../backtest_runs/20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a)/summary_metrics.json --> |
| 20 | 候选组 | 74.82% | 11.44% | 89.51% | 9.74% | 0.960 | 1.428 | 1.175 | 0.762 | 0.078 | 66.0% | 2.557 | 434 | 2021-11-22 ~ 2022-07-14 | [20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3](../../../backtest_runs/20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3)/summary_metrics.json --> |
| 40 | 候选组 | 82.99% | 12.43% | 98.37% | 7.97% | 1.079 | 1.586 | 1.560 | 0.810 | 0.078 | 68.4% | 2.800 | 401 | 2023-07-19 ~ 2023-12-05 | [20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994](../../../backtest_runs/20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994)/summary_metrics.json --> |
| 60 | 候选组 | 63.72% | 10.03% | 77.48% | 8.24% | 0.777 | 1.132 | 1.217 | 0.674 | 0.078 | 68.6% | 2.386 | 384 | 2023-07-19 ~ 2023-12-05 | [20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502](../../../backtest_runs/20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502)/summary_metrics.json --> |
| 80 | 候选组 | 63.68% | 10.03% | 77.44% | 6.55% | 0.748 | 1.043 | 1.531 | 0.671 | 0.081 | 74.2% | 2.472 | 363 | 2021-08-04 ~ 2022-12-23 | [20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d](../../../backtest_runs/20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d)/summary_metrics.json --> |
| 100 | 候选组 | 69.68% | 10.80% | 83.94% | 8.91% | 0.843 | 1.139 | 1.212 | 0.712 | 0.081 | 78.0% | 2.838 | 344 | 2021-11-22 ~ 2022-12-16 | [20260508-0023-bt595479372f9c3d54da84c2f826894688](../../../backtest_runs/20260508-0023-bt595479372f9c3d54da84c2f826894688/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0023-bt595479372f9c3d54da84c2f826894688)/summary_metrics.json --> |
| 140 | 候选组 | 59.87% | 9.53% | 73.30% | 9.24% | 0.683 | 0.908 | 1.031 | 0.638 | 0.081 | 75.6% | 2.558 | 360 | 2021-01-04 ~ 2022-12-16 | [20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49](../../../backtest_runs/20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49)/summary_metrics.json --> |
| 160 | 候选组 | 69.91% | 10.83% | 84.18% | 6.93% | 0.840 | 1.123 | 1.563 | 0.716 | 0.081 | 76.6% | 2.926 | 348 | 2021-11-22 ~ 2022-12-16 | [20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212](../../../backtest_runs/20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/summary_metrics.json --> |

> 基准为沪深 300 (`000300.XSHG`)。基准区间收益 -7.75%，基准波动率 0.179。本轮所有参数组合均显著跑赢基准。

## 3. 相对 120 日对照组

| MA_long | 年化收益变化 | 策略收益变化 | 最大回撤变化 | Sharpe变化 | Calmar变化 | 交易笔数变化 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 120 | 0.00pp | 0.00pp | 0.00pp | 0.000 | 0.000 | 0 | 对照组 |
| 20 | +0.58pp | +4.67pp | +2.77pp | +0.109 | -0.384 | +74 | 收益提高，但回撤和换手上升过多 |
| 40 | +1.57pp | +12.84pp | +1.00pp | +0.228 | +0.001 | +41 | 收益和 Sharpe 最优，回撤增加可控 |
| 60 | -0.83pp | -6.43pp | +1.27pp | -0.074 | -0.341 | +24 | 未优于对照组或 40 日候选 |
| 80 | -0.83pp | -6.47pp | -0.42pp | -0.103 | -0.027 | +3 | 回撤最低，但收益和 Sharpe 让步明显 |
| 100 | -0.06pp | -0.47pp | +1.94pp | -0.008 | -0.346 | -16 | 未优于对照组或 40 日候选 |
| 140 | -1.33pp | -10.28pp | +2.27pp | -0.168 | -0.527 | +0 | 收益、Sharpe、回撤均弱于对照 |
| 160 | -0.03pp | -0.24pp | -0.04pp | -0.011 | +0.005 | -12 | 回撤略低、收益基本持平，优势很薄 |

## 4. 关键发现

- `MA_long=40` 是本轮最强收益/Sharpe 候选：年化收益 12.43%、策略收益 82.99%、Sharpe 1.079 均为最高。相对 120 日对照组，年化收益提高 +1.57pp，最大回撤增加 +1.00pp。
- `MA_long=80` 最大回撤最低，为 6.55%，但年化收益降至 10.03%，Sharpe 降至 0.748，属于偏防守但收益代价较高的备选。
- `MA_long=160` 的 Calmar 最高，为 1.563，但相对 120 日只是回撤小幅下降 -0.04pp，年化收益低 -0.03pp，优势很薄。
- `MA_long=20` 提高收益，但最大回撤升至 9.74%，交易笔数比对照组多 74 笔，短窗口更敏感但换手和回撤代价偏高。
- `MA_long=140` 在收益、Sharpe、回撤三项上都弱于对照组，不构成候选。

## 5. 边际变化

| 区间 | 年化收益变化 | 最大回撤变化 | Sharpe变化 | 边际观察 |
| --- | ---: | ---: | ---: | --- |
| 20 -> 40 | +0.99pp | -1.77pp | +0.119 | 最有效提升段：收益和 Sharpe 上升，同时回撤下降 |
| 40 -> 60 | -2.40pp | +0.27pp | -0.302 | 40 日之后继续放长窗口，收益出现明显反转 |
| 60 -> 80 | +0.00pp | -1.69pp | -0.029 | 边际效果不稳定 |
| 80 -> 100 | +0.77pp | +2.36pp | +0.095 | 边际效果不稳定 |
| 100 -> 120 | +0.06pp | -1.94pp | +0.008 | 边际效果不稳定 |
| 120 -> 140 | -1.33pp | +2.27pp | -0.168 | 边际效果不稳定 |
| 140 -> 160 | +1.30pp | -2.31pp | +0.157 | 长期窗口修复回撤，但收益只回到对照附近 |

## 6. Pareto 前沿

按“年化收益最大化、Sharpe 最大化、最大回撤最小化”三维判断，Pareto 前沿为：MA=40, MA=80, MA=120, MA=160。

| MA_long | 年化收益 | 最大回撤 | Sharpe | Calmar | 说明 |
| --- | ---: | ---: | ---: | ---: | --- |
| 40 | 12.43% | 7.97% | 1.079 | 1.560 | 收益和 Sharpe 领先，主候选 |
| 80 | 10.03% | 6.55% | 0.748 | 1.531 | 回撤最低，防守备选 |
| 120 | 10.86% | 6.97% | 0.851 | 1.558 | 当前默认值，综合表现稳健 |
| 160 | 10.83% | 6.93% | 0.840 | 1.563 | Calmar 略优，但优势很薄 |

## 7. 结论与建议

本轮不建议只因为一次参数扫描就直接修改主策略默认值。最值得进入下一轮确认的是 `MA_long=40`：它同时提升年化收益、Sharpe、Sortino 和信息比率，回撤增幅相对可控。若目标是单纯压低最大回撤，`MA_long=80` 可以作为防守备选，但收益牺牲明显。

建议下一步做 `MA_long=40` 对 120 日 baseline 的聚焦 A/B，重点检查 2023-07-19 ~ 2023-12-05 回撤段，以及 2021-2022 熊市段的换手、持仓切换和信号稳定性。

## 8. run_id 映射

| MA_long | label | run_id | 本地报告 |
| --- | --- | --- | --- |
| 120 | `MA=120_baseline` | `20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a` | [strategy-analysis](../../../backtest_runs/20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a)/performance-analysis.md --> |
| 20 | `MA=20` | `20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3` | [strategy-analysis](../../../backtest_runs/20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3)/performance-analysis.md --> |
| 40 | `MA=40` | `20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994` | [strategy-analysis](../../../backtest_runs/20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994)/performance-analysis.md --> |
| 60 | `MA=60` | `20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502` | [strategy-analysis](../../../backtest_runs/20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502)/performance-analysis.md --> |
| 80 | `MA=80` | `20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d` | [strategy-analysis](../../../backtest_runs/20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d)/performance-analysis.md --> |
| 100 | `MA=100` | `20260508-0023-bt595479372f9c3d54da84c2f826894688` | [strategy-analysis](../../../backtest_runs/20260508-0023-bt595479372f9c3d54da84c2f826894688/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0023-bt595479372f9c3d54da84c2f826894688)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0023-bt595479372f9c3d54da84c2f826894688/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0023-bt595479372f9c3d54da84c2f826894688)/performance-analysis.md --> |
| 140 | `MA=140` | `20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49` | [strategy-analysis](../../../backtest_runs/20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49)/performance-analysis.md --> |
| 160 | `MA=160` | `20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212` | [strategy-analysis](../../../backtest_runs/20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212/report/strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/strategy-analysis.md --> / [performance-analysis](../../../backtest_runs/20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212/report/performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/performance-analysis.md --> |

## 9. 数据完整性

8 个 run 均已完成，均包含 `metadata.json`、`summary_metrics.json`、`all_data.json`、`tabs_raw/`、`report/backtest_report.md`，并已补齐 `strategy-analysis.md` 与 `performance-analysis.md`。

报告生成时间：2026-05-08 00:45:42。
