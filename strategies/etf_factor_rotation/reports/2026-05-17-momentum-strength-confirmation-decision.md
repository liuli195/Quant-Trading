# 动量倾斜强度确认决策

- **本地研究运行**: [momentum-next-stage-decision.md](research/momentum_tilt/runs/2026-05-17-baseline/reports/momentum-next-stage-decision.md) <!-- pathref: strategy_research_run_reports(strategy=etf_factor_rotation, project=momentum_tilt, run_id=2026-05-17-baseline)/momentum-next-stage-decision.md -->
- **Replay 校准**: [replay_calibration.md](research/momentum_tilt/runs/2026-05-17-baseline/reports/replay_calibration.md) <!-- pathref: strategy_research_run_reports(strategy=etf_factor_rotation, project=momentum_tilt, run_id=2026-05-17-baseline)/replay_calibration.md -->
- **云端 A/B**: [ab-momentum-strength-confirmation-comparison.md](../test_batches/20260517-momentum-strength-confirmation/report/ab-momentum-strength-confirmation-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260517-momentum-strength-confirmation)/ab-momentum-strength-confirmation-comparison.md -->
- **稳健性验证**: [robustness-verification.md](../backtest_runs/20260517-1734-bt19cd602c6a77e0878d1aec4a60c9f3d8/report/robustness-verification.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260517-1734-bt19cd602c6a77e0878d1aec4a60c9f3d8)/robustness-verification.md -->

## 决策

**暂不把 `MomentumTiltStrength` 从 `0.50` 写回调整到 `0.25`。**

本轮结论定级为：**方向性支持，继续观察**。

## 证据链

1. 离线响应曲线支持“中段优于高段”：discovery 中段相对高段 `+159.9 bp`，holdout 为 `+309.2 bp`。
2. replay 校准通过，且成功复现已知云端结果的方向与排序；本地扫描认为 `linear-025` 是当前最优线性候选。
3. 云端批次 A 复核了这一点：`linear-025` 相对 baseline 的 Sharpe `1.447 -> 1.469`，年化 `15.76% -> 15.91%`，最大回撤维持 `8.09%`。
4. 但正式写回所需的稳定性门槛没有通过：
   - 配对 bootstrap CI95 为 `[-0.089, +0.220] bp`，仍覆盖 `0`
   - 滚动 `252` 日 Sharpe 胜率仅 `45.5%`
   - 年度 Sharpe 只在 `3/6` 个年份改善
5. 改善没有完全被单一 ETF 垄断，但仍明显偏向黄金：近似贡献中黄金 `+94.9 bp`，AI `-16.9 bp`，纳指 `-13.5 bp`。

## 解释

这一轮已经把主问题从“是不是极端高位需要特殊处理”进一步澄清为：

- 当前整体动量 slope 偏强的迹象更可靠；
- 在全样本点估计上，简单把 `MomentumTiltStrength` 降到 `0.25` 优于继续做顶端形状修饰；
- 但这还不足以证明 `0.25` 是值得写回正式默认值的稳定改动。

因此，本轮最稳妥的处理不是继续加复杂度，而是：

1. 暂时保留正式默认值 `0.50`
2. 把 `0.25` 作为下一阶段重点观察候选
3. 不启动非线性形状批次 B，直到出现“中间 strength 同时优于 `0.50` 与 `0.25`”的新证据

## 后续建议

1. 若需要继续推进，优先补 **真正的留出验证** 或后续模拟交易窗口，而不是在同一历史样本上继续细扫 `0.20 / 0.30`。
2. 后续若再做参数确认，建议把 `0.25` 作为主候选，`0.35` 作为邻近对照，保留 `0.50` 为正式 baseline。
3. 非线性高端弱化暂时降级为备选分支，不进入下一轮默认主线。
