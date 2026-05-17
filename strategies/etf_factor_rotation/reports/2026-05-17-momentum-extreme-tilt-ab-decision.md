# 动量极端高位弱化 A/B 决策

- **实验日期**: 2026-05-17
- **验证计划**: [2026-05-17-momentum-extreme-tilt-validation-plan.md](testing/2026-05-17-momentum-extreme-tilt-validation-plan.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/testing/2026-05-17-momentum-extreme-tilt-validation-plan.md -->
- **A/B 对比**: [ab-momentum-extreme-ab-comparison.md](../test_batches/20260517-momentum-extreme-ab/report/ab-momentum-extreme-ab-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260517-momentum-extreme-ab)/ab-momentum-extreme-ab-comparison.md -->
- **分桶检查**: [momentum-bucket-check.md](../test_batches/20260517-momentum-extreme-ab/report/momentum-bucket-check.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260517-momentum-extreme-ab)/momentum-bucket-check.md -->
- **稳健性验证**: [robustness-verification.md](../backtest_runs/20260517-1624-btac3499f8d6b8bf0f5ee81147b6bd0da1/report/robustness-verification.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260517-1624-btac3499f8d6b8bf0f5ee81147b6bd0da1)/robustness-verification.md -->

## 决策

**暂不把 `MomentumExtremeScoreStart=0.90`、`MomentumExtremeTiltCap=1.00` 写回正式默认参数。**

本轮结论定级为：**方向性支持，继续观察**。

## 证据链

1. `extreme-neutral-090` 相对 baseline 有改善：Sharpe `1.447 -> 1.464`，年化 `15.76% -> 15.85%`，最大回撤 `8.09% -> 8.00%`。
2. 分桶复核支持原假设：AI 中动量组最好，纳指与黄金的高动量组最弱；`0.90` 方案共命中 `176` 次极端高分，其中 `109` 次实际把高位 tilt 压回 `1.0`。
3. 中动量增强被完整保留：`0.50 <= score < 0.90` 区间 baseline 与 `0.90` 方案的倾斜差异最大值为 `0.0000`。
4. 但主方案没有通过最关键的机制门槛：`linear-weak` 的 Sharpe `1.469`、年化 `15.91%` 均高于 `extreme-neutral-090`。
5. 稳健性证据不足以支撑正式写回：`0.90` 对 baseline 的配对 bootstrap CI95 为 `[-0.142, +0.233] bp`，`p=0.379`；滚动 `252` 日 Sharpe 胜率仅 `50.1%`。
6. 改善来源过于集中：`0.90` 的净提升几乎全部来自黄金 `+1,543.7`，AI 与纳指分别为 `-194.1`、`-411.2`。

## 解释

这次实验说明两件事可以同时成立：

- “极端高动量不值得继续线性加仓”这个结构性判断，大体是对的。
- 但在当前样本里，问题更可能不只出在极端段，而是整体动量暴露略偏强；否则 `linear-weak` 不应在全样本点估计上优于 `0.90`。

因此，非线性方案现在还不是可直接落地的默认参数，更像是下一轮研究里值得保留的候选分支。

## 后续建议

1. 保留 `0.90` 作为观察阈值，不下移到 `0.85`；本轮 `0.90` 的 Sharpe 与回撤都略优于 `0.85`。
2. 下一轮把研究问题改写为“整体动量强度是否偏高”，优先比较：
   - `MomentumTiltStrength = 0.35 / 0.40 / 0.45`
   - `linear-weak` 与“中段保留、顶端缓降”的更平滑分段函数
3. 若后续仍想保留非线性结构，应增加“黄金贡献占比”门槛，避免再次被单一 ETF 驱动的改善误导。
