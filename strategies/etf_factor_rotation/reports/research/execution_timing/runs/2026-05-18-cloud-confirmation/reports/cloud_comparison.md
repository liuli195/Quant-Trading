# 执行时序云端正式比较

## 结论

正式云端结果确认：执行时序差异**不是可以忽略的小扰动**。

- `logic-2-delay-only` 相对 `baseline` 年化只高 `0.28pp`，但最大回撤恶化 `1.13pp`
- `logic-3-live-like` 相对 `baseline` 年化低 `0.22pp`，最大回撤恶化 `3.44pp`
- 因此，在真实人工执行口径尚未确认前，`baseline` 仍可作为代码定义上的正式基线，但**不能再默认代表真实人工执行效果**

当前结论属于“正式差异已确认”，但还**不能直接写回默认口径**。下一步必须先确认真实人工流程到底更接近 `logic-2` 还是 `logic-3`。

## 数据来源

- 有效云端批次：[manifest.json](../../../../../../test_batches/20260518-execution-timing-cloud-compare-v2/manifest.json) <!-- pathref: test_batch(strategy=etf_factor_rotation, batch_id=20260518-execution-timing-cloud-compare-v2)/manifest.json -->
- 场景定义：[scenario.json](../../../../../../test_batches/20260518-execution-timing-cloud-compare-v2/scenarios/s01-execution-timing-worktree/scenario.json) <!-- pathref: test_scenario(strategy=etf_factor_rotation, batch_id=20260518-execution-timing-cloud-compare-v2, scenario_id=s01-execution-timing-worktree)/scenario.json -->
- baseline：[summary_metrics.json](../../../../../../backtest_runs/20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718)/summary_metrics.json -->、[audit_log.jsonl](../../../../../../backtest_runs/20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718/tabs_raw/audit_log.jsonl) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260518-2125-bt17c8ba539ebb20f374b4c36fc322b718)/audit_log.jsonl -->
- logic-2：[summary_metrics.json](../../../../../../backtest_runs/20260518-2128-bt720a21be72ca92343877e3eed66a5644/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260518-2128-bt720a21be72ca92343877e3eed66a5644)/summary_metrics.json -->、[audit_log.jsonl](../../../../../../backtest_runs/20260518-2128-bt720a21be72ca92343877e3eed66a5644/tabs_raw/audit_log.jsonl) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260518-2128-bt720a21be72ca92343877e3eed66a5644)/audit_log.jsonl -->
- logic-3：[summary_metrics.json](../../../../../../backtest_runs/20260518-2130-btd3a302dab6ce74013cb2c7dfd6785a62/summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260518-2130-btd3a302dab6ce74013cb2c7dfd6785a62)/summary_metrics.json -->、[audit_log.jsonl](../../../../../../backtest_runs/20260518-2130-btd3a302dab6ce74013cb2c7dfd6785a62/tabs_raw/audit_log.jsonl) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260518-2130-btd3a302dab6ce74013cb2c7dfd6785a62)/audit_log.jsonl -->
- 本地先验结果：[timing_path_summary.json](../../2026-05-18-phase1-open-refresh/tables/timing_path_summary.json) <!-- pathref: strategy_research_run(strategy=etf_factor_rotation, project=execution_timing, run_id=2026-05-18-phase1-open-refresh)/tables/timing_path_summary.json -->

## 正式云端指标

| 口径 | 总收益 | 年化收益 | 最大回撤 | Sharpe | 波动率 |
|---|---:|---:|---:|---:|---:|
| `baseline` | 118.32% | 16.35% | 7.99% | 1.498 | 8.2% |
| `logic-2-delay-only` | 121.07% | 16.63% | 9.12% | 1.535 | 8.2% |
| `logic-3-live-like` | 116.17% | 16.13% | 11.43% | 1.514 | 8.0% |

## 相对 baseline 的变化

| 口径 | 总收益变化 | 年化变化 | 最大回撤恶化 | 解释 |
|---|---:|---:|---:|---|
| `logic-2-delay-only` | `+2.75pp` | `+0.28pp` | `+1.13pp` | 只晚一天成交，收益略好，但回撤更差 |
| `logic-3-live-like` | `-2.15pp` | `-0.22pp` | `+3.44pp` | 多看一天数据后再成交，风险画像明显偏离 |

## 时序口径审计

第二版正式批次的审计结果是完整的：

| 口径 | 周信号 | 排队/标记 | 实际执行 | 说明 |
|---|---:|---:|---:|---|
| `baseline` | 272 | - | 272 | 当周首个交易日开盘直接执行 |
| `logic-2-delay-only` | 272 | 272 | 272 | 全部信号都在下一交易日开盘执行 |
| `logic-3-live-like` | 272 | 272 | 272 | 全部首个交易日信号都在下一交易日开盘执行 |

第一版批次 `20260518-execution-timing-cloud-compare` 只保留为诊断记录，不作为结论来源。它暴露出单槽缓存会在长假周覆盖待执行信号，导致 `logic-2` 仅执行 `269/272` 次、`logic-3` 仅覆盖 `269/272` 次。修复后改为队列执行，并通过第二版批次重新确认。

## 与本地近似结果的关系

本地先验判断方向正确：

- `logic-2`：本地预测年化 `+0.19pp`、最大回撤恶化约 `0.98pp`；云端正式结果为年化 `+0.28pp`、最大回撤恶化 `1.13pp`
- `logic-3`：本地预测年化 `-0.27pp`、最大回撤恶化约 `4.00pp`；云端正式结果为年化 `-0.22pp`、最大回撤恶化 `3.44pp`

这说明本地平台适合作为前置筛选器，但正式解释仍应以云端结果为准。

## 当前决策

1. `baseline` 继续保留为代码层面的正式回测基线
2. 若真实人工流程最终确认更接近 `logic-2`，后续解释时必须补充“回撤风险比 baseline 更差”
3. 若真实人工流程最终确认更接近 `logic-3`，则后续不应再把 `baseline` 当作人工执行结果的主解释口径
4. 在真实流程未确认前，不修改策略默认参数，不把任何一种替代口径写回正式默认
