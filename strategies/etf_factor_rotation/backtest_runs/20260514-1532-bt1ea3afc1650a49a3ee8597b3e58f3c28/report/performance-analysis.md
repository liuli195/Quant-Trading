# 性能分析报告：AI120_NQ40_Gold100

**策略**: `etf_factor_rotation`  
**run_id**: `20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28`  
**参数**: `MA_long_by_etf=[120, 40, 100]`  
**数据来源**: [metadata.json](../metadata.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28)/metadata.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28)/all_data.json -->、[profile.md](../tabs_raw/profile.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260514-1532-bt1ea3afc1650a49a3ee8597b3e58f3c28)/profile.md -->。

## 1. 执行概览

| 项目 | 数值 |
| --- | ---: |
| 聚宽实际计算耗时 | 1.44 分钟 |
| 预估耗时 | 6 分钟 |
| profile 记录数 | 3,940 |
| logs 记录数 | 143 |
| daily_returns 记录数 | 1,289 |
| transactioninfo 记录数 | 358 |
| positioninfo 记录数 | 2,289 |
| period_risk tabs | 10 |

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

该 run 的云端计算耗时为 1.44 分钟，未接近 `backtest-timeout=600` 秒限制。研究环境抓取成功，详情页接口仅作 profile/logs 等补充；交易、持仓、收益和风险分期表均已落盘。
