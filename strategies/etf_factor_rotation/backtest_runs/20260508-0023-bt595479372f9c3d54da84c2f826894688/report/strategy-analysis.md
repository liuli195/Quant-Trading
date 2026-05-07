# 策略分析报告：MA_long=100

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0023-bt595479372f9c3d54da84c2f826894688`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0023-bt595479372f9c3d54da84c2f826894688)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0023-bt595479372f9c3d54da84c2f826894688)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0023-bt595479372f9c3d54da84c2f826894688) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 69.68% |
| 年化收益 | 10.80% |
| 超额收益 | 83.94% |
| 最大回撤 | 8.91% |
| 最大回撤区间 | 2021-11-22 ~ 2022-12-16 |
| Sharpe | 0.843 |
| Sortino | 1.139 |
| Calmar | 1.212 |
| 信息比率 | 0.712 |
| 波动率 | 0.081 |
| Alpha | 0.075 |
| Beta | 0.131 |
| 胜率 | 78.0% |
| 盈亏比 | 2.838 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 -0.06pp，最大回撤 +1.94pp，Sharpe -0.008。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 344 |
| 持仓记录数 | 2361 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 54.1% |
| 盈利次数 | 131 |
| 亏损次数 | 37 |

## 4. 判断

本 run 未形成比 40 日候选更强的综合优势。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
