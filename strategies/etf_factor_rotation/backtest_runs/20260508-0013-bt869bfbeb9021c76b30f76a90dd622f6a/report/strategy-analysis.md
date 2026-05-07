# 策略分析报告：MA_long=120

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a`  
**参数角色**: 120 日对照组  
**回测区间**: 2021-01-01 ~ 2026-04-30  
**初始资金**: 100,000  
**数据来源**: [summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a)/summary_metrics.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a)/all_data.json -->、[tabs_raw](../tabs_raw) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0013-bt869bfbeb9021c76b30f76a90dd622f6a) -->。

## 1. 核心指标

| 指标 | 数值 |
| --- | ---: |
| 策略收益 | 70.15% |
| 年化收益 | 10.86% |
| 超额收益 | 84.45% |
| 最大回撤 | 6.97% |
| 最大回撤区间 | 2022-03-09 ~ 2022-12-16 |
| Sharpe | 0.851 |
| Sortino | 1.168 |
| Calmar | 1.558 |
| 信息比率 | 0.716 |
| 波动率 | 0.081 |
| Alpha | 0.076 |
| Beta | 0.132 |
| 胜率 | 76.9% |
| 盈亏比 | 2.932 |

## 2. 与对照组比较

本 run 是对照组，用于衡量其它均线窗口的边际变化。

## 3. 交易行为

| 项目 | 数值 |
| --- | ---: |
| 订单记录数 | 360 |
| 持仓记录数 | 2449 |
| 每日收益记录数 | 1289 |
| 账户余额记录数 | 1289 |
| 日胜率 | 54.2% |
| 盈利次数 | 133 |
| 亏损次数 | 40 |

## 4. 判断

对照组表现稳健，Calmar 与 40 日和 160 日候选非常接近。 批次横向结论见 [batch-comparison.md](../../../test_batches/20260508-hard-ma-scan/report/batch-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/batch-comparison.md -->。
