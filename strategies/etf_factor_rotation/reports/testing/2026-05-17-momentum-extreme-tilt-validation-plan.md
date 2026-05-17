# 动量极端高位弱化验证计划

- **制定日期**: 2026-05-17
- **关联归因**: [2026-05-14-deep-attribution.md](../2026-05-14-deep-attribution.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/2026-05-14-deep-attribution.md -->
- **策略代码**: [etf_factor_rotation.py](../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->
- **A/B 配置**: [momentum-extreme-ab.json](../../test_batches/20260517-momentum-extreme-ab/abtests/momentum-extreme-ab.json) <!-- pathref: test_batch_abtests(strategy=etf_factor_rotation, batch_id=20260517-momentum-extreme-ab)/momentum-extreme-ab.json -->
- **当前工作区批次**: [scenario.json](../../test_batches/20260517-momentum-extreme-ab/scenarios/s01-momentum-extreme-worktree/scenario.json) <!-- pathref: test_scenario(strategy=etf_factor_rotation, batch_id=20260517-momentum-extreme-ab, scenario_id=s01-momentum-extreme-worktree)/scenario.json -->

## 1. 验证目标

本轮只验证“动量倾斜函数形状”是否需要从线性高位加仓改成“中段保留增强、极端高位回落到中性”，不同时调整动量窗口、RSRS 或拥挤度参数。

依据：

- 深度归因显示纳指和黄金的高动量组反而最弱，更稳的候选方向是弱化极端高动量，而不是否定动量因子本身。
- 时间窗异质性研究已把动量窗口降级为观察项，因此本轮不把窗口变更混入实验。

## 2. 代码口径

新增参数：

| 参数 | 默认值 | 说明 |
|---|---:|---|
| `MomentumExtremeScoreStart` | `None` | `None` 表示关闭新规则；启用时按固定高分阈值识别极端高动量 |
| `MomentumExtremeTiltCap` | `1.00` | 命中阈值后，高于该值的动量倾斜被压回该上限 |

规则：

1. 先按现有线性公式计算 `MomentumTilt`
2. 若 `MomentumExtremeScoreStart is not None` 且 `MomentumScore >= threshold`
3. 再执行 `MomentumTilt = min(MomentumTilt, MomentumExtremeTiltCap)`

默认配置继续关闭新规则，以保证历史 baseline 仍可逐点复现。

## 3. A/B 设计

| 变体 | 目的 |
|---|---|
| `baseline-linear` | 当前线性动量倾斜 |
| `extreme-neutral-090` | 主方案：`start=0.90, cap=1.00` |
| `extreme-neutral-085` | 邻近方案：检验是否需要更早弱化 |
| `linear-weak` | 机制对照：整体降低 `MomentumTiltStrength` 到 `0.25` |

解释规则：

- `extreme-neutral-090` 优于 baseline 且不弱于 `linear-weak`，才说明“只处理极端高位”优于“整体少押动量”。
- 若 `linear-weak` 更优，则应回到“整体动量暴露偏强”的假设。
- 若 `extreme-neutral-085` 明显优于 `0.90`，再考虑是否把正式阈值下移。

## 4. 决策门槛

正式写回默认参数需同时满足：

- `Sharpe` 高于 baseline
- 年化收益不低于 baseline 超过 `0.30pp`
- 最大回撤不高于 baseline 超过 `0.20pp`
- `extreme-neutral-090` 不弱于 `linear-weak`
- 中动量区间仍保留增强效果，不能退化成高于均值即被普遍压平

支持性验证：

- 极端高分命中次数与命中后的平均倾斜变化
- 低 / 中 / 高动量组在 `5/10/20/40` 日窗口下的前向表现
- 配对 block bootstrap、滚动 252 日 Sharpe、年度分解
- 分 ETF 贡献拆解，确认不是单一年份或单一资产驱动

## 5. 当前已完成

- 已实现新参数和弱化逻辑，默认关闭。
- 已补齐单元测试。
- 已回放 `2026-05-14` 基线审计日志：关闭新规则时，`272` 个调仓点的 `MomentumTilt` 最大绝对误差为 `0`。

## 6. 执行前置

- 标准 `ab run` 使用 Git ref 读取源码；正式执行前，需要先把本轮策略改动提交到 A/B 配置引用的 ref。
- 在策略改动尚未提交时，可先使用同批次下的 `s01-momentum-extreme-worktree` 场景直接跑当前工作区代码，完成 4 个候选项的云端确认。
