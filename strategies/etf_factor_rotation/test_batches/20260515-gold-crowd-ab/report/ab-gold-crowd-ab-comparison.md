# AB 对比报告: gold-crowd-ab

**状态:** completed
**Baseline:** `gold-baseline`
**额外对照:** `gold-baseline`
**生成时间:** 2026-05-15T20:59:38

## 核心指标对比

| Variant | Role | 夏普比率 | 策略年化收益 | 最大回撤 | 超额收益 | 实际耗时(分) |
| --- | --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| gold-baseline | control ★ | 1.437 | 15.44% | 8.09% | 127.29% | 1.5 |
| gold-start-080 | variant | 1.447 | 15.76% | 8.09% | 130.50% | 1.6 |
| gold-neutralized | variant | 1.389 | 15.70% | 8.09% | 129.91% | 2.0 |
| gold-calc-longwin | variant | 1.414 | 15.29% | 8.09% | 125.72% | 1.6 |

★ = baseline

## 相对 Baseline 的变化

Baseline: **gold-baseline**

| Variant | 夏普比率 | 策略年化收益 | 最大回撤 | 超额收益 | 实际耗时(分) |
| --- |  ---  |  ---  |  ---  |  ---  |  ---  |
| gold-start-080 | +0.7% | +0.32 pp | +0.00 pp | +3.21 pp | +2.0% |
| gold-neutralized | -3.3% | +0.26 pp | +0.00 pp | +2.62 pp | +28.2% |
| gold-calc-longwin | -1.6% | -0.15 pp | +0.00 pp | -1.57 pp | +2.1% |

## 变体详情

### gold-baseline
- **Role:** control (baseline)
- **Issues:** none
- **Backtest ID:** 7636c4788d821690fd90b281dee7e913
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### gold-start-080
- **Role:** variant
- **Issues:** none
- **Backtest ID:** e8e07662646ef6b56f453ea15c7d959d
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### gold-neutralized
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 72abfe3d501669b91a4b3d3a0fd5b49b
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)

### gold-calc-longwin
- **Role:** variant
- **Issues:** none
- **Backtest ID:** 3e11aaf64867aa42e8644d88dfe0a4e3
- **Artifacts present:** has_backtest_report
- **Artifacts missing:** has_strategy_analysis, has_performance_analysis (建议运行分析流程补充)
