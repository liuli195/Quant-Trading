# AB 对比报告: hard-vs-soft-trend-gate

**状态:** completed
**Baseline:** `hard_gate_main`
**额外对照:** `hard_gate_main`
**生成时间:** 2026-05-07T23:15:43

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
- **Issues:** none
- **Backtest ID:** 199f841dc26f34045a3391110073b7b2
- **Artifacts present:** has_backtest_report, has_strategy_analysis, has_performance_analysis

### soft_gate_workspace
- **Role:** variant
- **Issues:** none
- **Backtest ID:** fe11e835821438464da31fd4f4d995e1
- **Artifacts present:** has_backtest_report, has_strategy_analysis, has_performance_analysis
