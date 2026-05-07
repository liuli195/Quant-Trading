# 策略分析报告：MA_long=80

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0021-bt5ce8b6f11fe037f9780b2e051ed2979d) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 63.68% |
| 年化收益 | 10.03% |
| 超额收益 | 77.44% |
| 最大回撤 | 6.55% |
| 最大回撤区间 | 2021-08-04 ~ 2022-12-23 |
| Sharpe | 0.748 |
| Sortino | 1.043 |
| Calmar | 1.531 |
| 信息比率 | 0.671 |
| 波动率 | 0.081 |
| Alpha | 0.068 |
| Beta | 0.136 |
| 胜率 | 74.2% |
| 盈亏比 | 2.472 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 -0.83pp，最大回撤 -0.42pp，Sharpe -0.103。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 363 |
| 持仓记录数 | 2336 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 54.1% |
| 盈利次数 | 132 |
| 亏损次数 | 46 |

## 4. 判断

本 run 的最大回撤最低，但收益和 Sharpe 低于对照组，适合防守目标。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
