# 策略分析报告：MA_long=60

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0019-bt91c62e12c5cc7fd16dd43466b0b7d502) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 63.72% |
| 年化收益 | 10.03% |
| 超额收益 | 77.48% |
| 最大回撤 | 8.24% |
| 最大回撤区间 | 2023-07-19 ~ 2023-12-05 |
| Sharpe | 0.777 |
| Sortino | 1.132 |
| Calmar | 1.217 |
| 信息比率 | 0.674 |
| 波动率 | 0.078 |
| Alpha | 0.068 |
| Beta | 0.131 |
| 胜率 | 68.6% |
| 盈亏比 | 2.386 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 -0.83pp，最大回撤 +1.27pp，Sharpe -0.074。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 384 |
| 持仓记录数 | 2265 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 52.8% |
| 盈利次数 | 131 |
| 亏损次数 | 60 |

## 4. 判断

本 run 未形成比 40 日候选更强的综合优势。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
