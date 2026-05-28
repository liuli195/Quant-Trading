# AB 对比报告: hard-vs-soft-trend-gate

**状态:** archived_partial
**Baseline:** `hard_gate_main`
**额外对照:** `hard_gate_main`
**生成时间:** 2026-05-07T23:15:43

> 数据中心说明：本批次是历史 partial 档案。两个 run 的数据中心快照均缺少 `tabs_raw/audit_log.jsonl`；软门槛变体源码提交不在远端 ref 中，且 `uploaded_code_sha256` 不能从当前仓库源码复算。本报告只保留为历史线索，不能作为策略晋级、合并或后续参数扫描证据；需要重新按现行治理流程运行。

## 核心指标对比

| Variant | Role | 最大回撤 | 策略年化收益 | 超额收益 | 夏普比率 | 实际耗时(分) |
| --- | --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| hard_gate_main | control ★ | 6.97% | 10.86% | 84.45% | 0.851 | 2.0 |
| soft_gate_workspace | variant | 8.26% | 11.97% | 94.16% | 0.971 | 1.4 |

★ = baseline

## 相对 Baseline 的变化

Baseline: **hard_gate_main**

| Variant | 最大回撤 | 策略年化收益 | 超额收益 | 夏普比率 | 实际耗时(分) |
| --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| soft_gate_workspace | +1.29 pp | +1.11 pp | +9.71 pp | +14.1% | -26.8% |

## 变体详情

### hard_gate_main
- **Role:** control (baseline)
- **Issues:** historical partial data-center snapshot: missing `tabs_raw/audit_log.jsonl`; audit events unavailable; not promotion or merge evidence without governed rerun
- **Backtest ID:** 199f841dc26f34045a3391110073b7b2
- **Artifacts present:** has_backtest_report, has_strategy_analysis, has_performance_analysis

### soft_gate_workspace
- **Role:** variant
- **Issues:** historical partial data-center snapshot: missing `tabs_raw/audit_log.jsonl`; source commit is not reachable from origin refs and uploaded code hash is not reproducible from current committed source; not promotion or merge evidence without governed rerun
- **Backtest ID:** fe11e835821438464da31fd4f4d995e1
- **Artifacts present:** has_backtest_report, has_strategy_analysis, has_performance_analysis
