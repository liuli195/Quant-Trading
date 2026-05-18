# 现金利用率优化研究计划

- **制定日期**: 2026-05-17
- **更新日期**: 2026-05-18
- **适用策略**: [etf_factor_rotation.py](../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->
- **前置归因**: [2026-05-14-deep-attribution.md](../2026-05-14-deep-attribution.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/2026-05-14-deep-attribution.md -->
- **Phase 0 现金拆解**: [cash_decomposition_summary.md](../research/cash_utilization/runs/2026-05-17-phase0-baseline/reports/cash_decomposition_summary.md) <!-- pathref: strategy_research_run_reports(strategy=etf_factor_rotation, project=cash_utilization, run_id=2026-05-17-phase0-baseline)/cash_decomposition_summary.md -->
- **组合波动率局部网格扫描（历史）**: [portfolio-volatility-full-scan.md](../research/cash_utilization/runs/2026-05-18-volscale-full-scan/reports/portfolio-volatility-full-scan.md) <!-- pathref: strategy_research_run_reports(strategy=etf_factor_rotation, project=cash_utilization, run_id=2026-05-18-volscale-full-scan)/portfolio-volatility-full-scan.md -->
- **组合波动率性能冒烟**: [portfolio-volatility-performance-smoke.md](../research/portfolio_volatility/runs/2026-05-18-smoke-warm-v2/reports/portfolio-volatility-performance-smoke.md) <!-- pathref: strategy_research_run_reports(strategy=etf_factor_rotation, project=portfolio_volatility, run_id=2026-05-18-smoke-warm-v2)/portfolio-volatility-performance-smoke.md -->
- **组合波动率行为完整扫描**: [portfolio-volatility-full-scan.md](../research/portfolio_volatility/runs/2026-05-18-full-v1/reports/portfolio-volatility-full-scan.md) <!-- pathref: strategy_research_run_reports(strategy=etf_factor_rotation, project=portfolio_volatility, run_id=2026-05-18-full-v1)/portfolio-volatility-full-scan.md -->
- **研究主题**: 在保留现有信号框架的前提下，优先处理最大现金来源，提高有效风险预算利用率

## 1. 本次更新的核心变化

旧计划把优先级排成：

```text
软趋势门槛
-> 拥挤度现金回收
-> 最后重新评估 TargetVol
```

最新 Phase 0 结果已经不支持这个顺序。

| 现金来源 | 平均贡献 | 占总现金比例 |
|---|---:|---:|
| 组合波动率缩放 | `25.15%` | `58.7%` |
| 拥挤度惩罚 | `7.93%` | `18.5%` |
| 趋势门槛 | `6.99%` | `16.3%` |
| 交易约束 | `2.77%` | `6.5%` |

因此，新计划把主线改为：

```text
先研究组合波动率调整
-> 再判断是否需要 ETF 差异化波动率控制
-> 之后才研究拥挤度现金回收
-> 最后再决定是否需要软趋势门槛
```

## 2. 当前事实

### 2.1 现金状态

| 指标 | 当前结果 |
|---|---:|
| 调仓信号总数 | `272` |
| 平均目标仓位 | `57.16%` |
| 中位目标仓位 | `60.00%` |
| 平均现金 | `42.84%` |
| 全空仓信号 | `19` 次 |

### 2.2 最新现金归因结论

1. 主要矛盾不是趋势门槛，而是 `PortfolioVolScale`。
2. `PortfolioVolScale` 与拥挤度惩罚合计解释 `77.2%` 总现金。
3. 组合波动率缩放在所有年份都重要，尤其是：
   - `2021`: `32.21%`
   - `2022`: `30.12%`
   - `2026`: `54.43%`
4. 趋势门槛仍有研究价值，但它不是第一优先级。

## 3. 行为完整扫描结论

本轮已完成：

| 扫描层 | 覆盖 |
|---|---|
| 组合层 | `5` 个窗口各自覆盖 `[0, 历史最大组合波动率]`，共 `8835` 个行为点 |
| 覆盖证明 | 每窗 `884` 个有效断点 + `883` 个区间代表点，缺口 `0` |

局部 replay 以最新正式基线 `20260517-1724-bt580e16e5a3f1bf99d197cea88889da1a` 为锚，只用于筛选，不替代最终云端 A/B。

### 3.1 问题 1：收益怎么变化

| 方案 | 年化变化 | 平均仓位 | 解释 |
|---|---:|---:|---|
| `40 日 + 约 7.85%` | `+0.61pp` | `57.36%` | 满足“仓位不低于当前基线”后的最佳折中 |
| `40 日 + 约 8.00%` | `+0.76pp` | `58.09%` | 收益更高，但风险代价开始上升 |
| `120 日 + 约 21.17%` | `+2.58pp` | `73.27%` | 只是最高收益点，不适合作为主线 |

结论：

- 只改组合层，已经可以在不降低平均仓位的前提下提高收益。
- 继续抬高 `TargetVol` 会继续增收，但很快开始拿 Sharpe 和回撤换收益。

### 3.2 问题 2：风险怎么变化

| 方案 | 波动率变化 | 最大回撤变化 | 解释 |
|---|---:|---:|---|
| `40 日 + 约 7.20%` | `-0.42pp` | 改善 `+0.66pp` | 纯 Sharpe 最优，但年化 `-0.26pp`、仓位更低 |
| `40 日 + 约 7.85%` | `+0.03pp` | 改善 `+0.12pp` | 主目标下最干净的风险收益折中 |
| `40 日 + 约 8.00%` | `+0.13pp` | 基本不变 | 更偏增收，仍可作为高收益对照 |
| `90/120 日高 TargetVol` | 大幅上升 | 明显变差 | 不能只看收益绝对值 |

结论：

- `40` 日窗口仍明显优于当前 `60` 日窗口。
- 纯 Sharpe 最优和本轮业务目标最优不是同一个点；必须把“少拿现金”放进决策条件里。

### 3.3 问题 3：收益和风险的最佳平衡

若只允许一个简单、可解释、适合先上云验证的方案：

```text
PortfolioVolWindow = 40
TargetVol = 0.0785
```

理由：

| 指标 | 结果 |
|---|---:|
| 平均目标仓位 | `57.36%` |
| 年化变化 | `+0.61pp` |
| 波动率变化 | `+0.03pp` |
| Sharpe 变化 | `+0.058` |
| 最大回撤变化 | 改善 `+0.12pp` |

结论：

- `40 日 + 约 7.20%` 的 Sharpe 更高，但它降低仓位，也降低收益，不适合作为本轮主线。
- `40 日 + 约 8.00%` 的收益更高，但 `40 日 + 约 7.85%` 在“仓位至少不低于当前基线”的约束下更平衡。

### 3.4 问题 4：是否需要 ETF 差异化波动率控制

结论分两层：

1. **值得继续研究。**
2. **但现在还不是必须先做的步骤。**

原因：

- 行为完整扫描已经把组合层主线从旧的 `40 日 + 8%` 重定位到 `40 日 + 约 7.85%`
- 旧 ETF 差异化结果仍有参考价值，但它们建立在旧主线上，不能直接平移成正式结论
- 当前应先确认新的组合层主线，再决定差异化控制是否能继续改善前沿

若后续继续做，顺序应为：

1. 先确认组合层 `40 日 + 约 7.85%`
2. 再测 `AI-only tightening`
3. 只有当 `AI-only tightening` 也稳定，才考虑加入黄金放宽分支

## 4. 新的研究假设

| 编号 | 假设 | 当前判断 |
|---|---|---|
| `H1` | 当前现金的首要来源是组合波动率控制 | 已被 Phase 0 确认 |
| `H2` | `PortfolioVolWindow=60` 对当前策略偏慢 | 本地扫描支持 |
| `H3` | `40 日 + 约 7.85%` 比当前 `60 日 + 8%` 更适合作为主基线 | 行为完整扫描支持，待云端确认 |
| `H4` | ETF 差异化控制仍有价值，但应基于新主线从 AI 最小改动验证 | 旧局部结果仅作方向性参考 |
| `H5` | 拥挤度现金回收与软趋势门槛仍有价值，但不是第一优先级 | 当前成立 |

## 5. Phase 1：先做组合波动率调整

### 5.1 研究目标

先回答一个问题：

> 在不改其它信号模块的前提下，能否只靠组合波动率参数，把收益提高，同时不明显恶化风险？

### 5.2 云端 A/B 首轮矩阵

| 变体 | 目的 |
|---|---|
| `baseline-pv60-tv008` | 当前正式基线 |
| `pv40-tv074` | 低风险正收益对照 |
| `pv40-tv0785` | 主候选 |
| `pv40-tv080` | 高收益对照 |

### 5.3 进入下一阶段的门槛

主候选 `pv40-tv0785` 至少同时满足：

- 年化收益高于 baseline
- 最大回撤不高于 baseline `+0.5pp`
- 策略波动率不高于 baseline `+0.3pp`
- 滚动 `252` 日 Sharpe 胜率 `> 55%`
- 年度 Sharpe 改善至少 `4 / 6`
- 配对 bootstrap 不出现明显反向证据

### 5.4 Phase 1 产物

| 产物 | 内容 |
|---|---|
| A/B manifest | `pv40-tv074 / pv40-tv0785 / pv40-tv080` |
| 对比报告 | `cash-utilization-volscale-ab-comparison.md` |
| 稳健性验证 | `cash-utilization-volscale-robustness.md` |
| 阶段决策 | `cash-utilization-volscale-decision.md` |

## 6. Phase 2：ETF 差异化波动率控制

### 6.1 进入条件

只有在 `pv40-tv0785` 通过云端确认后，才进入这一阶段。

### 6.2 先测最小改动

建议先只做 AI 单边收紧：

```text
effective_target
= base_target * (1 - ai_penalty * ai_share)
```

首轮候选：

| 变体 | 说明 |
|---|---|
| `ai-tight-020` | `ai_penalty = 0.20` |
| `ai-tight-030` | `ai_penalty = 0.30` |
| `ai-tight-040` | `ai_penalty = 0.40` |

### 6.3 只有 AI 单边有效后，再测黄金放宽

第二步再研究：

```text
effective_target
= base_target * (1 + gold_bonus * gold_share - ai_penalty * ai_share)
```

候选：

| 变体 | 说明 |
|---|---|
| `gold020-ai030` | 黄金加成 `20%`，AI 惩罚 `30%` |
| `gold030-ai030` | 黄金加成 `30%`，AI 惩罚 `30%` |

### 6.4 为什么不直接做三 ETF 全量异质化

- 当前本地证据只指向 `AI` 与 `黄金`
- 纳指暂未显示必须单独加一套控制
- 一次引入太多自由度，会把收益来源和风险来源重新搅混

### 6.5 Phase 2 产物

| 产物 | 内容 |
|---|---|
| `portfolio-vol-ai-tight-scan.csv` | AI 单边收紧扫描 |
| `portfolio-vol-mix-aware-scan.csv` | 黄金放宽 + AI 收紧扫描 |
| `cash-utilization-etf-vol-control-decision.md` | 是否保留差异化控制 |

## 7. Phase 3：剩余现金再优化

若 Phase 1 与 Phase 2 后，平均目标仓位仍明显低于预期，再继续处理剩余现金来源。

### 7.1 先做拥挤度现金回收

原因：

- 当前拥挤度现金占比 `18.5%`
- 高于趋势门槛现金 `16.3%`
- 比软趋势更接近“被动残留现金”

首轮候选：

| 变体 | 回收比例 |
|---|---:|
| `recycle-025` | `25%` |
| `recycle-050` | `50%` |
| `recycle-075` | `75%` |

约束：

- 只回收给仍然活跃的资产
- 优先给低惩罚资产
- 不直接把被重罚资产原样加回

### 7.2 再看软趋势门槛

只有在下列情况出现时，才进入软趋势：

- 组合层调整已确认
- 拥挤度现金回收已评估
- 低仓和全空仓仍主要由趋势门槛解释

## 8. 统一评价指标

### 8.1 主要指标

| 指标 | 用途 |
|---|---|
| 年化收益 | 看是否真正提高资金利用效率 |
| 策略波动率 | 看风险是否同步抬升 |
| 最大回撤 | 看最坏路径是否恶化 |
| Sharpe | 看风险调整后是否改善 |
| 平均目标仓位 | 看现金是否真正减少 |
| 全空仓信号次数 | 看是否仍有过度空仓 |

### 8.2 稳健性指标

| 指标 | 用途 |
|---|---|
| 配对 bootstrap | 看改善是否只是噪音 |
| 滚动 `252` 日 Sharpe 胜率 | 看改善是否稳定 |
| 年度 Sharpe 分解 | 看是否只靠单一年份 |
| 分 ETF 贡献 | 看是否被单一 ETF 驱动 |
| leave-one-out | 看去掉单一 ETF 后结论是否翻转 |

## 9. 推荐执行顺序

1. 先完成 Phase 1 云端确认：`pv40-tv074 / pv40-tv0785 / pv40-tv080`
2. 若 `pv40-tv0785` 通过，再做 `AI-only tightening`
3. 若 AI 单边收紧继续有效，再测黄金放宽分支
4. 只有在组合层和 ETF 差异化都定下来后，再回头做拥挤度现金回收
5. 软趋势门槛降到最后，只在残余问题仍指向趋势门槛时再启动

## 10. 当前推荐

当前最合理的下一步不是继续先动趋势门槛，而是：

1. 把 `PortfolioVolWindow=40`、`TargetVol=0.08` 作为新的第一候选
2. 先用云端 A/B 验证它是否能稳定替代当前 `60 日 + 8%`
3. 保留 ETF 差异化为第二阶段，优先验证 `AI-only tightening`
4. 暂时不把黄金放宽、拥挤度现金回收、软趋势门槛混在同一轮里
