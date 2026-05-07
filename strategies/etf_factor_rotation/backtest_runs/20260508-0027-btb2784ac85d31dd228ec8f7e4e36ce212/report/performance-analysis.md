# 性能分析报告：MA_long=160

**策略**: `etf_factor_rotation`  
**run_id**: `20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212`  
**参数角色**: 候选参数  
**数据来源**: [metadata.json](../metadata.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/metadata.json -->、[all_data.json](../all_data.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/all_data.json -->、[profile.md](../tabs_raw/profile.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260508-0027-btb2784ac85d31dd228ec8f7e4e36ce212)/profile.md -->。

## 1. 执行概览

| 项目 | 数值 |
| --- | ---: |
| 聚宽实际计算耗时 | 2.10 分钟 |
| 预估耗时 | 6 分钟 |
| profile 记录数 | 3784 |
| logs 记录数 | 143 |
| daily_returns 记录数 | 1289 |
| transactioninfo 记录数 | 348 |
| positioninfo 记录数 | 2444 |
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

该 run 的云端计算耗时为 2.10 分钟，未接近单次 `backtest-timeout=600` 秒限制。profile、交易、持仓、收益和风险分期表均已落盘，可支撑后续针对调仓周、回撤区间和持仓切换的进一步追踪。

批次级性能和参数结论见 [param-scan-report.md](../../../test_batches/20260508-hard-ma-scan/report/param-scan-report.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260508-hard-ma-scan)/param-scan-report.md -->。
