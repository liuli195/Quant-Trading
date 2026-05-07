# 策略分析报告：MA_long=20

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0014-bt9bb4faba66f1fb565ad2783fb33147c3) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 74.82% |
| 年化收益 | 11.44% |
| 超额收益 | 89.51% |
| 最大回撤 | 9.74% |
| 最大回撤区间 | 2021-11-22 ~ 2022-07-14 |
| Sharpe | 0.960 |
| Sortino | 1.428 |
| Calmar | 1.175 |
| 信息比率 | 0.762 |
| 波动率 | 0.078 |
| Alpha | 0.082 |
| Beta | 0.139 |
| 胜率 | 66.0% |
| 盈亏比 | 2.557 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 +0.58pp，最大回撤 +2.77pp，Sharpe +0.109。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 434 |
| 持仓记录数 | 2060 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 53.3% |
| 盈利次数 | 140 |
| 亏损次数 | 72 |

## 4. 判断

本 run 未形成比 40 日候选更强的综合优势。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
