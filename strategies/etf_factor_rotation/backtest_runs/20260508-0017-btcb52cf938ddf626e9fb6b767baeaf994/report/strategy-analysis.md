# 策略分析报告：MA_long=40

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994`  
**参数角色**: 候选参数  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0017-btcb52cf938ddf626e9fb6b767baeaf994) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 82.99% |
| 年化收益 | 12.43% |
| 超额收益 | 98.37% |
| 最大回撤 | 7.97% |
| 最大回撤区间 | 2023-07-19 ~ 2023-12-05 |
| Sharpe | 1.079 |
| Sortino | 1.586 |
| Calmar | 1.560 |
| 信息比率 | 0.810 |
| 波动率 | 0.078 |
| Alpha | 0.092 |
| Beta | 0.129 |
| 胜率 | 68.4% |
| 盈亏比 | 2.800 |

## 2. 与对照组比较

相对 120 日对照组，年化收益 +1.57pp，最大回撤 +1.00pp，Sharpe +0.228。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 401 |
| 持仓记录数 | 2229 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 53.4% |
| 盈利次数 | 134 |
| 亏损次数 | 62 |

## 4. 判断

本 run 是本轮主候选：收益、Sharpe、Sortino、信息比率均为本轮最高。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
