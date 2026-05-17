# 动量极端高位弱化 A/B 对比

- **实验日期**: 2026-05-17
- **回测窗口**: 2021-01-01 -> 2026-04-30
- **基线 run**: `20260517-1611-bt9b67f2f9a034bb7d3d7a044cf3e0d4e9`
- **批次清单**: [manifest.json](../manifest.json) <!-- pathref: test_batch(strategy=etf_factor_rotation, batch_id=20260517-momentum-extreme-ab)/manifest.json -->
- **方案说明**: [2026-05-17-momentum-extreme-tilt-validation-plan.md](../../../reports/testing/2026-05-17-momentum-extreme-tilt-validation-plan.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/testing/2026-05-17-momentum-extreme-tilt-validation-plan.md -->

## 标准指标

| 变体 | 年化收益 | Sharpe | 最大回撤 | 相对 baseline |
|---|---:|---:|---:|---|
| `baseline-linear` | 15.76% | 1.447 | 8.09% | - |
| `extreme-neutral-090` | 15.85% | 1.464 | 8.00% | 年化 `+0.09pp`，Sharpe `+0.017`，回撤 `-0.09pp` |
| `extreme-neutral-085` | 15.85% | 1.462 | 8.06% | 年化 `+0.09pp`，Sharpe `+0.015`，回撤 `-0.03pp` |
| `linear-weak` | 15.91% | 1.469 | 8.09% | 年化 `+0.15pp`，Sharpe `+0.022`，回撤 `+0.00pp` |

## 门槛判定

| 门槛 | `extreme-neutral-090` | 结论 |
|---|---:|---|
| Sharpe 高于 baseline | `1.464 > 1.447` | 通过 |
| 年化收益不低于 baseline 超过 `0.30pp` | `+0.09pp` | 通过 |
| 最大回撤不高于 baseline 超过 `0.20pp` | `-0.09pp` | 通过 |
| 不弱于 `linear-weak` | `1.464 < 1.469` | **未通过** |
| 中动量增强仍保留 | `0.50 <= score < 0.90` 区间倾斜差异最大值 `0.0000` | 通过 |

## 解释

1. 非线性弱化极端高分是有效方向：`0.90` 与 `0.85` 都优于 baseline。
2. 但本轮最优点估计来自 `linear-weak`，说明当前证据更偏向“整体动量暴露略强”，而不只是“极端高位过强”。
3. `0.90` 略优于 `0.85`：Sharpe 更高、回撤更低，若后续继续观察非线性方案，仍应保留更保守的 `0.90` 阈值。

## 关联产物

| 变体 | Run ID |
|---|---|
| `baseline-linear` | `20260517-1611-bt9b67f2f9a034bb7d3d7a044cf3e0d4e9` |
| `extreme-neutral-090` | `20260517-1624-btac3499f8d6b8bf0f5ee81147b6bd0da1` |
| `extreme-neutral-085` | `20260517-1627-bteaf8bd75c426dcbb66b49eca35aeab1c` |
| `linear-weak` | `20260517-1629-bt13a13155cdf761ba85550d3987fd22c4` |
