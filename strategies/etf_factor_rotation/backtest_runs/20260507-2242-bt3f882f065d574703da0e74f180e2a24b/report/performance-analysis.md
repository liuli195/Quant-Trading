# 性能分析

## 回测概况

- 回测区间：2026-04-01 至 2026-04-30。
- 回测 ID：`3f882f065d574703da0e74f180e2a24b`。
- 数据来源：[profile.md](../tabs_raw/profile.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260507-2242-bt3f882f065d574703da0e74f180e2a24b)/profile.md -->、[metadata.json](../metadata.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2242-bt3f882f065d574703da0e74f180e2a24b)/metadata.json -->、[backtest_report.md](backtest_report.md) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2242-bt3f882f065d574703da0e74f180e2a24b)/report/backtest_report.md -->。

## 云端链路

| 阶段 | 结果 |
|---|---|
| 本地 compile-check | 通过，并生成 `etf_factor_rotation__upload.py` |
| 云端上传与编译 | 通过 |
| 云端回测 | 完成 |
| 详情抓取 | 成功，使用聚宽详情页只读 JSON 接口 |
| Research 抓取 | 失败后自动降级，不影响已落盘结果 |
| 实际计算时间 | 0.07 分钟 |

`metadata.json` 记录 `research_fetch_failed=true`，原因是研究端 Jupyter API 未返回可用入口；工具随后使用详情页只读接口完成抓取，`summary_metrics.json`、`tabs_raw/` 和 `backtest_report.md` 均已生成。

## 函数耗时

| 函数 | 总耗时 |
|---|---:|
| `weekly_check` | 0.843168s |
| `compute_rsrs_multipliers` | 0.169091s |
| `compute_crowd_penalties` | 0.151358s |
| `compute_momentum_scores` | 0.032467s |
| `execute_rebalance` | 0.017366s |
| `compute_trend_gates` | 0.011450s |
| `compute_portfolio_vol_scale` | 0.006363s |

软门槛改动对性能影响很小。`compute_trend_gates` 全月累计仅 0.01145s，主要耗时仍在 RSRS 与拥挤度计算。

## 稳定性观察

- 策略日志：`INFO=59`、`WARNING=9`、`ERROR=0`。
- WARNING 主要来自聚宽对空 Position 的兼容提示和 100 股整数倍撮合提示，不是策略异常。
- 全月保存 16 组原始数据文件，交易、持仓、收益、风险指标和日志均完整。

## 结论

本次软门槛版本的云端性能验证通过。新增线性门槛没有引入可见性能瓶颈，实际运行耗时仍由历史数据拉取、RSRS 和拥挤度计算主导。
