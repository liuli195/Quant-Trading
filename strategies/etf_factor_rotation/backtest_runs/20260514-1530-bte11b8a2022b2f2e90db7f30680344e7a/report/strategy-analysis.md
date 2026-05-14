# 策略分析报告：AI100_NQ40_Gold100

**策略**: `etf_factor_rotation`  
**run_id**: `20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a`  
**参数角色**: AI 稳健窗口确认组  
**参数**: `MA_long_by_etf=[100, 40, 100]`  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260514-1530-bte11b8a2022b2f2e90db7f30680344e7a) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 81.10% |
| 年化收益 | 12.21% |
| 超额收益 | 96.32% |
| 最大回撤 | 6.99% |
| 最大回撤区间 | 2021-11-22 ~ 2022-12-16 |
| Sharpe | 1.046 |
| Sortino | 1.494 |
| 信息比率 | 0.793 |
| 波动率 | 0.078 |
| Alpha | 0.089 |
| Beta | 0.125 |
| 胜率 | 76.2% |
| 盈亏比 | 3.332 |

## 2. 与对照组比较

相对统一 120 日对照，收益 +10.95pp，年化 +1.35pp，最大回撤 +0.02pp，Sharpe +0.195。相对统一 40 日对照，收益 -1.89pp，年化 -0.22pp，最大回撤 -0.98pp，Sharpe -0.033。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 345 |
| 成交额绝对值合计 | 6,613,984.50 |
| 手续费 | 661.41 |
| 持仓记录数 | 2,264 |
| 每日收益记录数 | 1,289 |
| 日胜率 | 54.5% |
| 盈利次数 | 128 |
| 亏损次数 | 40 |

## 4. 判断

本 run 在回撤和换手上更稳，但没有超过统一 40 日对照；它证明 AI 放弃 20 日短均线后，混合组合的主要收益优势会明显收敛。批次横向结论见 [param-scan-report.md](../../../test_batches/20260514-etf-ma-mixed-confirmation/report/param-scan-report.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260514-etf-ma-mixed-confirmation)/param-scan-report.md -->。
