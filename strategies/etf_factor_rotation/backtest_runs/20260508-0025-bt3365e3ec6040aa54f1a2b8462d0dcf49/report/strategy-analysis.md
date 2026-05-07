# 策略分析报告：MA_long=140

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0025-bt3365e3ec6040aa54f1a2b8462d0dcf49) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 59.87% |
| 年化收益 | 9.53% |
| 超额收益 | 73.30% |
| 最大回撤 | 9.24% |
| 最大回撤区间 | 2021-01-04 ~ 2022-12-16 |
| Sharpe | 0.683 |
| Sortino | 0.908 |
| Calmar | 1.031 |
| 信息比率 | 0.638 |
| 波动率 | 0.081 |
| Alpha | 0.063 |
| Beta | 0.131 |
| 胜率 | 75.6% |
| 盈亏比 | 2.558 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 -1.33pp，最大回撤 +2.27pp，Sharpe -0.168。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 360 |
| 持仓记录数 | 2424 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 54.0% |
| 盈利次数 | 133 |
| 亏损次数 | 43 |

## 4. 判断

本 run 未形成比 40 日候选更强的综合优势。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
