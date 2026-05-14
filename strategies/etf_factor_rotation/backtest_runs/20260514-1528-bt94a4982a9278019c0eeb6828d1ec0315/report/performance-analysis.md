# 性能分析报告：AI20_NQ40_Gold100

**策略**: `etf_factor_rotation`  
**run_id**: `20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315`  
**参数**: `MA_long_by_etf=[20, 40, 100]`  
**数据来源**: [metadata.json](../metadata.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315)/metadata.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315)/all_data.json -->、[profile.md](../tabs_raw/profile.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260514-1528-bt94a4982a9278019c0eeb6828d1ec0315)/profile.md -->。

## 1. 执行概览

| 项目 | 数值 |
| --- | ---: |
| 聚宽实际计算耗时 | 1.44 分钟 |
| 预估耗时 | 6 分钟 |
| profile 记录数 | 3,948 |
| logs 记录数 | 1,000 |
| daily_returns 记录数 | 1,485 |
| transactioninfo 记录数 | 399 |
| positioninfo 记录数 | 3,551 |
| 风险标签页记录数 | 640 |

## 2. 数据完整性

| 产物 | 状态 |
| --- | --- |
| `metadata.json` | 已生成 |
| `summary_metrics.json` | 已生成 |
| `all_data.json` | 已生成 |
| `tabs_raw/*.md` | 已生成 |
| `report/backtest_report.md` | 已生成 |
| `strategy-analysis.md` | 已补齐 |
| `performance-analysis.md` | 已补齐 |

## 3. 性能判断

该 run 的云端计算耗时为 1.44 分钟，未接近 `backtest-timeout=600` 秒限制。研究环境抓取失败后回退到详情页只读接口，核心指标、交易、持仓、收益和风险标签页均已落盘；平台日志为免费接口部分数据。
