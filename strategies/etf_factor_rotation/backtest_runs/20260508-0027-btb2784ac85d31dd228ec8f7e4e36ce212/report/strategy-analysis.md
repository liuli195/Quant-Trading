# 策略分析报告：MA_long=160

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 69.91% |
| 年化收益 | 10.83% |
| 超额收益 | 84.18% |
| 最大回撤 | 6.93% |
| 最大回撤区间 | 2021-11-22 ~ 2022-12-16 |
| Sharpe | 0.840 |
| Sortino | 1.123 |
| Calmar | 1.563 |
| 信息比率 | 0.716 |
| 波动率 | 0.081 |
| Alpha | 0.076 |
| Beta | 0.136 |
| 胜率 | 76.6% |
| 盈亏比 | 2.926 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 -0.03pp，最大回撤 -0.04pp，Sharpe -0.011。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 348 |
| 持仓记录数 | 2444 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 54.7% |
| 盈利次数 | 128 |
| 亏损次数 | 39 |

## 4. 判断

本 run 的 Calmar 略高，但收益没有优于对照组，改善幅度偏薄。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
