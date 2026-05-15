# AB 对比报告: ai-crowd-ab

**状态:** completed
**Baseline:** `ai-baseline`
**额外对照:** `ai-baseline`
**生成时间:** 2026-05-15T21:11:24

## 核心指标对比

| Variant | Role | 实际耗时(分) | 夏普比率 | 策略年化收益 | 超额收益 | 最大回撤 |
| --- | --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| ai-baseline | control ★ | 1.5 | 1.437 | 15.44% | 127.29% | 8.09% |
| ai-start-075 | variant | 1.5 | 1.421 | 15.41% | 127.00% | 8.09% |
| ai-neutralized | variant | 1.6 | 1.340 | 15.06% | 123.42% | 8.09% |
| ai-calc-longwin | variant | 1.5 | 1.418 | 15.29% | 125.76% | 8.09% |

★ = baseline

## 相对 Baseline 的变化

Baseline: **ai-baseline**

| Variant | 实际耗时(分) | 夏普比率 | 策略年化收益 | 超额收益 | 最大回撤 |
| --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| ai-start-075 | +2.8% | -1.1% | -0.03 pp | -0.29 pp | +0.00 pp |
| ai-neutralized | +7.0% | -6.8% | -0.38 pp | -3.87 pp | +0.00 pp |
| ai-calc-longwin | +2.3% | -1.3% | -0.15 pp | -1.53 pp | +0.00 pp |

## 变体详情

### ai-baseline
- **Role:** control (baseline)
- **Issues:** none
- **Backtest ID:** 852ee6d4016248c77c11386f2f6a7245
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### ai-start-075
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 5d8807c600e004cf70f4c4b31a1b28ac
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### ai-neutralized
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 6fb6670169c26ae89dd2902eba243fff
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### ai-calc-longwin
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 157c5e16bdd7a47cb327a70b75b69da4
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)
