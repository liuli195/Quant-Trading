# 动量分桶检查

- **数据口径**: baseline `audit_log.jsonl` 的活跃资产周频信号，结合窗口异质性研究原始行情导出的前向收益
- **审计日志**: [audit_log.jsonl](../../../backtest_runs/20260517-1611-bt9b67f2f9a034bb7d3d7a044cf3e0d4e9/tabs_raw/audit_log.jsonl) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260517-1611-bt9b67f2f9a034bb7d3d7a044cf3e0d4e9)/audit_log.jsonl -->
- **原始行情**: [etf_window_research_prices.json](../../../reports/research/window_heterogeneity/inputs/raw/etf_window_research_prices.json) <!-- pathref: strategy_research_project_raw_inputs(strategy=etf_factor_rotation, project=window_heterogeneity)/etf_window_research_prices.json -->

## 极端高分命中

| ETF | `score >= 0.90` 命中数 | 被实际压帽数 | baseline 平均 tilt | `0.90` 方案平均 tilt | 平均压降 |
|---|---:|---:|---:|---:|---:|
| AI | 35 | 31 | 1.1319 | 1.0000 | 0.1319 |
| 纳指 | 64 | 47 | 1.0947 | 1.0000 | 0.0947 |
| 黄金 | 77 | 31 | 1.0419 | 1.0000 | 0.0419 |
| **合计** | **176** | **109** | - | - | - |

`0.50 <= score < 0.90` 的中段样本在 baseline 与 `extreme-neutral-090` 之间倾斜差异最大值为 `0.0000`，说明新规则只处理极端高分，没有把中段增强一并抹平。

## 前向收益分桶

单位为 bp。每只 ETF 按自身活跃样本内的 `MomentumScore` 三分位分组。

| ETF | 分组 | 样本数 | 5d | 10d | 20d | 40d |
|---|---|---:|---:|---:|---:|---:|
| AI | 低 | 45 | 45.6 | 74.7 | 22.8 | 2.0 |
| AI | 中 | 44 | **131.7** | **260.4** | **494.2** | **742.4** |
| AI | 高 | 45 | 29.0 | 116.9 | 17.6 | -68.2 |
| 纳指 | 低 | 58 | **71.8** | **159.4** | **292.8** | **681.2** |
| 纳指 | 中 | 57 | 41.5 | 106.1 | 42.9 | -377.5 |
| 纳指 | 高 | 58 | -6.4 | -161.5 | -141.5 | -125.3 |
| 黄金 | 低 | 70 | **96.2** | **151.2** | 206.3 | 446.1 |
| 黄金 | 中 | 70 | 49.6 | 84.9 | **251.5** | **548.0** |
| 黄金 | 高 | 70 | 14.5 | 42.8 | 89.3 | 117.4 |

## 结论

1. 原始归因结论被再次复核：AI 的中动量最好，纳指与黄金的高动量组最弱。
2. `0.90` 方案确实命中了需要处理的区域，而且没有伤到中段。
3. 但“分桶现象成立”并不自动等于“非线性方案应写回默认值”；最终仍需服从 A/B 与稳健性结果。
