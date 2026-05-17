# `linear-035` 稳健性补充与本地研究平台验证

- **补充日期**: 2026-05-17
- **关联决策**: [2026-05-17-momentum-strength-confirmation-decision.md](2026-05-17-momentum-strength-confirmation-decision.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/2026-05-17-momentum-strength-confirmation-decision.md -->
- **平台研究项目**: [project.json](research/momentum_strength_035_robustness/project.json) <!-- pathref: strategy_research_project_manifest(strategy=etf_factor_rotation, project=momentum_strength_035_robustness) -->
- **平台 full 复核**: [full_candidate_review.csv](research/momentum_strength_035_robustness/runs/2026-05-17-full/tables/full_candidate_review.csv) <!-- pathref: strategy_research_run_tables(strategy=etf_factor_rotation, project=momentum_strength_035_robustness, run_id=2026-05-17-full)/full_candidate_review.csv -->
- **平台交接结果**: [cloud_handoff.json](research/momentum_strength_035_robustness/runs/2026-05-17-full/tables/cloud_handoff.json) <!-- pathref: strategy_research_run_tables(strategy=etf_factor_rotation, project=momentum_strength_035_robustness, run_id=2026-05-17-full)/cloud_handoff.json -->
- **策略级稳健性报告**: [robustness-verification.md](../backtest_runs/20260517-1731-btbe2e525c63caec09d9355836a69f8676/report/robustness-verification.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260517-1731-btbe2e525c63caec09d9355836a69f8676)/robustness-verification.md -->

## 结论

`linear-035` 可以作为“方向正确但不够稳定”的补充证据，**不能写回正式默认参数**。

它相对 baseline 的点估计有改善，但与 `linear-025` 一样，仍没有通过正式写回所需的稳定性门槛。新增结果没有改变上一轮主结论：

1. 当前 `MomentumTiltStrength=0.50` 偏强的迹象仍然成立。
2. 线性弱化优于继续扩展非线性高端形状。
3. 但 `0.35` 与 `0.25` 目前都还只能保留为观察候选，不能替代正式 baseline。

## `linear-035` 结果

| 指标 | baseline | `linear-035` | 结论 |
|---|---:|---:|---|
| 年化收益 | 15.76% | 15.85% | 小幅改善 |
| Sharpe | 1.447 | 1.459 | 小幅改善 |
| 最大回撤 | 8.09% | 8.09% | 基本不变 |
| 配对 bootstrap CI95 | - | `[-0.083, +0.169] bp` | 仍覆盖 `0` |
| 滚动 `252` 日 Sharpe 胜率 | - | 45.8% | 未通过 |
| 年度 Sharpe 改善 | - | `4/6` | 通过 |
| 单一 ETF 最大解释占比 | - | 65.5% | 通过 |
| leave-one-out | - | 未通过 | 去掉黄金后优势不再稳固 |

分 ETF 近似贡献：

| ETF | 贡献 |
|---|---:|
| AI | `-14.6 bp` |
| 纳指 | `-7.1 bp` |
| 黄金 | `+57.5 bp` |

这说明 `0.35` 的改善仍主要来自黄金，AI 与纳指没有同步确认。它比 `0.25` 更接近保守候选，但并没有换来更好的滚动稳定性。

## 与 `linear-025` 的对照

| 方案 | 年化 | Sharpe | 滚动 Sharpe 胜率 | 年度 Sharpe 改善 | 是否通过全部门槛 |
|---|---:|---:|---:|---:|---|
| `linear-035` | 15.85% | 1.459 | 45.8% | `4/6` | 否 |
| `linear-025` | 15.91% | 1.469 | 45.5% | `3/6` | 否 |

当前更合理的解释是：

- `0.25` 的点估计更好；
- `0.35` 的年度分布略平衡；
- 但两者都没有提供足以写回的决定性证据。

因此，下一步若继续推进，不应再扩大历史内搜索，而应进入真正的新样本观察。

## 本地研究平台验证

本次使用 `robustness_check` 模板完整跑通了：

1. `init`
2. `run --mode fast`
3. `promote`
4. `handoff-cloud`
5. `status`

### 运行结果

| 阶段 | 结果 |
|---|---|
| fast | 成功完成，耗时 `0.013s` |
| full | 成功完成，耗时 `0.066s` |
| 缓存 | full 阶段命中缓存，`cache_hit=true` |
| SLO | fast / full 均通过 |
| handoff-cloud | `blocked`，原因是 `no_candidate_passed` |

平台 full 复核给出的主要结论：

| 项目 | 结果 |
|---|---|
| `annual_return_delta` | `+0.093 pp` |
| `sharpe_delta` | `+0.010` |
| `bootstrap_ci_low` | `< 0` |
| `rolling_sharpe_win_rate` | `45.76%` |
| `promotion_reasons` | `bootstrap_crosses_zero;rolling_win_rate_low` |

### 实用性判断

本地研究平台这次是**能跑通、也有实际价值**的：

- 适合快速验证“候选是否值得继续推进”
- 能自动复用缓存，适合重复小实验
- 能把“不该上云”的候选直接挡在本地，减少无效回测额度
- 生命周期清楚，产物结构稳定，适合后续复用

但它当前更适合作为**通用筛选器**，还不能完全替代策略专用研究：

- `robustness_check` 只基于日收益路径，不包含 ETF 贡献拆解
- 不覆盖本策略当前使用的 `dominant_share`、`leave-one-out` 等专用门槛
- 默认只产出表格，不直接产出可归档的策略级结论文档

因此，当前最合适的分工是：

1. 本地研究平台负责通用 fast/full 漏斗与流程管理
2. 策略专用工具负责最终解释性分析和正式结论

## 本次额外发现

在使用专用动量工具生成报告时，发现默认原始行情路径少了 `research/` 目录层级，导致默认命令无法直接运行。该问题已修复，并补充了单测，避免后续再次退化。

## 最终判断

本次补充研究后，建议保持：

1. 正式默认值继续使用 `0.50`
2. `0.25` 仍作为当前主观察候选
3. `0.35` 作为保守邻近对照保留，但不升级为写回候选
4. 后续停止在旧样本内继续细扫，转向 `2026-05-01` 之后的新样本验证

