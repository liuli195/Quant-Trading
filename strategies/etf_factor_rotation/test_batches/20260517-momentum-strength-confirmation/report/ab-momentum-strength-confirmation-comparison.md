# AB 对比报告: momentum-strength-confirmation

**状态:** completed
**Baseline:** `baseline-linear-050`
**额外对照:** `baseline-linear-050`
**生成时间:** 2026-05-17T17:37:01

## 核心指标对比

| Variant | Role | 夏普比率 | 实际耗时(分) | 超额收益 | 最大回撤 | 策略年化收益 |
| --- | --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| baseline-linear-050 | control ★ | 1.447 | 1.6 | 130.50% | 8.09% | 15.76% |
| linear-045 | variant | 1.449 | 1.5 | 130.75% | 8.09% | 15.78% |
| linear-040 | variant | 1.448 | 1.5 | 130.57% | 8.09% | 15.76% |
| linear-035 | variant | 1.459 | 1.6 | 131.45% | 8.09% | 15.85% |
| linear-025 | variant | 1.469 | 1.6 | 132.12% | 8.09% | 15.91% |

★ = baseline

## 相对 Baseline 的变化

Baseline: **baseline-linear-050**

| Variant | 夏普比率 | 实际耗时(分) | 超额收益 | 最大回撤 | 策略年化收益 |
| --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| linear-045 | +0.1% | -8.5% | +0.25 pp | +0.00 pp | +0.02 pp |
| linear-040 | +0.1% | -7.3% | +0.07 pp | +0.00 pp | +0.00 pp |
| linear-035 | +0.8% | -5.3% | +0.95 pp | +0.00 pp | +0.09 pp |
| linear-025 | +1.5% | -4.6% | +1.62 pp | +0.00 pp | +0.15 pp |

## 变体详情

### baseline-linear-050
- **Role:** control (baseline)
- **Issues:** none
- **Backtest ID:** 580e16e5a3f1bf99d197cea88889da1a
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### linear-045
- **Role:** variant
- **Issues:** none
- **Backtest ID:** a2d755cf006abe1aac853e65803acf70
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### linear-040
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 2405ba5c36f5774b229998b57b1d400e
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### linear-035
- **Role:** variant
- **Issues:** none
- **Backtest ID:** be2e525c63caec09d9355836a69f8676
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### linear-025
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 19cd602c6a77e0878d1aec4a60c9f3d8
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)
