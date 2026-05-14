# 策略分析报告：AI120_NQ40_Gold100

**策略**: `etf_factor_rotation`  
**run_id**: `20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28`  
**参数角色**: AI 原默认窗口确认组  
**参数**: `MA_long_by_etf=[120, 40, 100]`  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 80.24% |
| 年化收益 | 12.10% |
| 超额收益 | 95.39% |
| 最大回撤 | 6.80% |
| 最大回撤区间 | 2021-11-22 ~ 2022-01-28 |
| Sharpe | 1.036 |
| Sortino | 1.492 |
| 信息比率 | 0.789 |
| 波动率 | 0.078 |
| Alpha | 0.088 |
| Beta | 0.127 |
| 胜率 | 76.0% |
| 盈亏比 | 3.212 |

## 2. 与对照组比较

相对统一 120 日对照，收益 +10.09pp，年化 +1.24pp，最大回撤 -0.17pp，Sharpe +0.185。相对统一 40 日对照，收益 -2.75pp，年化 -0.33pp，最大回撤 -1.17pp，Sharpe -0.043。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 358 |
| 成交额绝对值合计 | 6,682,586.60 |
| 手续费 | 668.30 |
| 持仓记录数 | 2,289 |
| 每日收益记录数 | 1,289 |
| 日胜率 | 54.5% |
| 盈利次数 | 133 |
| 亏损次数 | 42 |

## 4. 判断

本 run 是三组混合参数中最防守的一组：最大回撤最低，收益和 Sharpe 低于统一 40 日，但显著强于统一 120 日。它适合作为低回撤备选，而不是收益主候选。批次横向结论见 [param-scan-report.md](../../../test_batches/20260514-etf-ma-mixed-confirmation/report/param-scan-report.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260514-etf-ma-mixed-confirmation)/param-scan-report.md -->。
