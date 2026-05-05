# AB 对比报告: smoke-params-ab

**状态:** completed
**Baseline:** `main_branch`
**额外对照:** `main_branch`
**生成时间:** 2026-05-06T03:17:24

## 核心指标对比

| Variant | Role | 超额收益 | 实际耗时(分) | 策略年化收益 | 夏普比率 | 最大回撤 |
| --- | --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| main_branch | control ★ | 0.63% | 0.1 | -43.74% | -3.334 | 6.90% |
| feature_branch | variant | 0.63% | 0.1 | -43.74% | -3.334 | 6.90% |

★ = baseline

## 相对 Baseline 的变化

Baseline: **main_branch**

| Variant | 超额收益 | 实际耗时(分) | 策略年化收益 | 夏普比率 | 最大回撤 |
| --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| feature_branch | +0.00 pp | +0.9% | +0.00 pp | +0.0% | +0.00 pp |

## 变体详情

### main_branch
- **Role:** control (baseline)
- **Issues:** none
- **Backtest ID:** 30cba1413b71d2db54bf0af0ab15eb9b
- **Backtest URL:** https://www.joinquant.com/algorithm/backtest/detail?backtestId=30cba1413b71d2db54bf0af0ab15eb9b
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### feature_branch
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 640080d57fef5127e820a0613bea2d2d
- **Backtest URL:** https://www.joinquant.com/algorithm/backtest/detail?backtestId=640080d57fef5127e820a0613bea2d2d
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)
