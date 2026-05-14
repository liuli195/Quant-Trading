# 策略分析报告：AI20_NQ40_Gold100

**策略**: `etf_factor_rotation`  
**run_id**: `20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315`  
**参数角色**: ETF 专属均线主候选  
**参数**: `MA_long_by_etf=[20, 40, 100]`  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 93.13% |
| 年化收益 | 13.62% |
| 超额收益 | 109.36% |
| 最大回撤 | 8.54% |
| 最大回撤区间 | 2021-11-22 ~ 2022-10-21 |
| Sharpe | 1.223 |
| Sortino | 1.789 |
| 信息比率 | 0.888 |
| 波动率 | 0.079 |
| Alpha | 0.104 |
| Beta | 0.141 |
| 胜率 | 71.4% |
| 盈亏比 | 3.223 |

## 2. 与对照组比较

相对统一 120 日对照，收益 +22.98pp，年化 +2.76pp，最大回撤 +1.57pp，Sharpe +0.372。相对统一 40 日对照，收益 +10.14pp，年化 +1.19pp，最大回撤 +0.57pp，Sharpe +0.144。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 399 |
| 成交额绝对值合计 | 7,730,125.60 |
| 手续费 | 773.09 |
| 持仓记录数 | 3,551 |
| 每日收益记录数 | 1,485 |
| 日胜率 | 54.0% |
| 盈利次数 | 142 |
| 亏损次数 | 57 |

## 4. 判断

本 run 是本轮主候选，收益、年化、Sharpe、Sortino 和信息比率均为五组最高。主要风险是最大回撤同步升至最高，后续应重点复盘 2021-11-22 ~ 2022-10-21 回撤区间。批次横向结论见 [param-scan-report.md](../../../test_batches/20260514-etf-ma-mixed-confirmation/report/param-scan-report.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260514-etf-ma-mixed-confirmation)/param-scan-report.md -->。
