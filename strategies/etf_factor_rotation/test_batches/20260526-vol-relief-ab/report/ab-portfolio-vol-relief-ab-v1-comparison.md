# AB 对比报告: portfolio-vol-relief-ab-v1

**状态:** completed
**Baseline:** `baseline_current`
**额外对照:** `baseline_current`
**生成时间:** 2026-05-26T23:35:59

## 核心指标对比

| Variant | Role | 超额收益 | 最大回撤 | 实际耗时(分) | 策略年化收益 | 夏普比率 |
| --- | --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| baseline_current | control ★ | 136.67% | 7.99% | 1.8 | 16.35% | 1.498 |
| fixed_gold_f50_r2 | variant | 142.11% | 7.80% | 1.8 | 16.86% | 1.515 |
| dyn_marginal_f100_r1.5_mom | variant | 146.21% | 7.60% | 2.1 | 17.25% | 1.582 |

★ = baseline

## 相对 Baseline 的变化

Baseline: **baseline_current**

| Variant | 超额收益 | 最大回撤 | 实际耗时(分) | 策略年化收益 | 夏普比率 |
| --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| fixed_gold_f50_r2 | +5.44 pp | -0.19 pp | -2.4% | +0.51 pp | +1.1% |
| dyn_marginal_f100_r1.5_mom | +9.54 pp | -0.39 pp | +18.3% | +0.90 pp | +5.6% |

## 变体详情

### baseline_current
- **Role:** control (baseline)
- **Issues:** none
- **Backtest ID:** a35e64a2599b009eba3c6b8219d61e22
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### fixed_gold_f50_r2
- **Role:** variant
- **Issues:** none
- **Backtest ID:** fefcb2db54c231df54d773457629bda1
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### dyn_marginal_f100_r1.5_mom
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 36f34fb52505979aa53d97ef4949fc60
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)
