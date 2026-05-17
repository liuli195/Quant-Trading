# ETF 时间窗异质性研究流水线性能优化方案

制定日期：2026-05-15  
关联规格：[research_spec.md](research_spec.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/research_spec.md -->  
分析脚本：[analysis.py](../../../../../../scripts/research/etf_window_research/analysis.py) <!-- pathref: scripts/research/etf_window_research/analysis.py -->

## 1. 当前症状

截至 `2026-05-15`，研究数据已经成功导出，但完整 Step 3-6 分析在本地执行超过 10 分钟仍未完成，且首版实现要到最后才统一落盘，导致长任务期间缺少进度反馈。

## 2. 已确认瓶颈

| 模块 | 微基准 | 结论 |
|---|---:|---|
| `trend_gate:20` | `0.0004s` | 可忽略 |
| `momentum_return:20` | `0.0002s` | 可忽略 |
| `crowd_ret_short:20` | `0.1345s` | 逐窗 rolling percentile 成本明显 |
| `crowd_amount:20` | `0.1193s` | 同上 |
| `crowd_deviation:20` | `0.1238s` | 同上 |
| `crowd_volatility:20` | `0.1256s` | 同上 |
| 完整 5 日网格，不做 bootstrap | `13.9730s` | 因子重复计算和 DataFrame 拼装已经偏重 |
| 完整 5 日网格，20 次 bootstrap | `30.3972s` | bootstrap 是第二大成本中心 |

## 3. 根因分层

### A. 算法层

1. 拥挤度因子对每个窗口都做一次 `500` 日 rolling percentile，且使用 `rolling(...).apply(..., raw=False)`，每个窗口都触发 Python 回调。
2. `build_holdout_validation()` 和 `build_segment_stability()` 会重新生成整套因子序列，导致 discovery、holdout、segment 之间重复计算。
3. bootstrap 内层仍在重复做 DataFrame 切片、`qcut`、`groupby`，没有针对 numpy 数组做轻量化实现。

### B. 任务编排层

1. 主 horizon、辅助 horizon、留出集、分段集默认共用同一套重计算规格。
2. 长任务只在最后统一写文件，缺少中间 checkpoint。
3. 当前报告产物没有分阶段落盘，无法在中断后复用已完成结果。

### C. 研究设计层

1. 研究结论真正依赖的是主 horizon 的置信区间、共享窗口对照、留出集与分段稳定性。
2. `10/20/40` 日 horizon 更适合做方向一致性检查，不必与主 horizon 同等深度 bootstrap。
3. 分段稳定性更关心最佳档位是否翻转，不需要为每个分段窗口重新估计完整置信区间。

## 4. 优化目标

| 级别 | 目标 |
|---|---|
| P0 | 将单次完整分析压到可接受范围，并保证中断后能复用中间产物 |
| P1 | 消除 discovery / holdout / segment 的重复因子计算 |
| P2 | 将 bootstrap 从 DataFrame 内循环改为 numpy 内循环 |
| P3 | 如仍需更快，再考虑并行化 |

## 5. 分阶段方案

### Phase 1：立即执行，低风险高收益

1. 只对主 horizon `5d` 做 bootstrap。
2. 次级 horizon `10/20/40d` 只保留点估计与方向检查。
3. discovery / holdout / 分段稳定性关闭 bootstrap，只保留最佳窗口、收益方向和档位。
4. 拆分输出：
   - `full_grid`
   - `holdout`
   - `segments`
   - `bootstrap`
5. 先产出数据完整性与默认信号复现，再进入重计算阶段。

### Phase 2：核心重构

1. 新增 `ResearchCache`：
   - 统一缓存 anchors
   - 统一缓存 forward returns
   - 统一缓存 `factor × ETF × window` 全量日序列
2. 所有 period 只在缓存结果上切片，不再重新计算 factor series。
3. 将 `build_holdout_validation()` 和 `build_segment_stability()` 改成消费已有 grid。

### Phase 3：bootstrap 提速

1. 为三类 metric 提供 numpy 版本。
2. 预先把 `factor_value`、`forward_return`、block index 转成 ndarray。
3. bootstrap 内层不再构造 DataFrame。
4. 目标：相同 reps 下把 bootstrap 成本至少压低 `50%`。

### Phase 4：可选增强

1. 对独立的 `factor × ETF` 任务做进程级并行。
2. 将 factor cache 写为 Parquet/Feather，支持中断恢复。
3. 为 CLI 增加 `--stage`、`--resume`、`--bootstrap-reps` 参数。

## 6. 推荐执行顺序

1. 先完成 Phase 1，让研究能稳定跑完。
2. 再做 Phase 2，解决重复计算这一类结构性浪费。
3. 若仍希望把全流程压到分钟级，再做 Phase 3。
4. Phase 4 只在后续准备把这条流水线长期保留时再做。

## 7. 当前建议

- **马上做**：Phase 1 + Phase 2。
- **暂缓**：并行化。当前最大浪费还在单进程内的重复计算，并行只会把浪费并发放大。
- **研究结论前置要求**：优化后先重跑 Step 3，确认默认信号复现通过，再继续解释窗口异质性结果。

## 8. 首轮优化落地后的复测

| 阶段 | 优化前 | 优化后 |
|---|---:|---:|
| 因子缓存构建 | 无缓存 | `13.4328s` |
| 全样本 `5d` 网格，无 bootstrap | `13.9730s` | `0.2287s` |
| 分段稳定性 | 重算整套因子 | `0.6706s` |
| holdout | 发现集 + 留出集全量 bootstrap | `0.4576s` |

解释：

- 缓存层已经把重复因子计算基本消掉。
- holdout 改为点估计验证后，当前主瓶颈已经进一步收敛到主网格自身的 `5d` bootstrap。
- 如果后续还要继续压缩总耗时，下一步最值钱的是把 bootstrap 内层改成 numpy 化，而不是继续折腾因子缓存。

## 9. 后续可选优化优先级

| 优先级 | 项目 | 预期收益 | 风险 |
|---|---|---|---|
| P1 | bootstrap numpy 化 | 高 | 中 |
| P1 | 分阶段落盘与 `--resume` | 中 | 低 |
| P2 | factor cache 持久化 | 中 | 低 |
| P3 | 进程级并行 | 中 | 中 |

### P1：bootstrap numpy 化

- 将三类 metric 改写成 ndarray 版本。
- block bootstrap 直接采样索引数组，不再构造 DataFrame。
- 这是当前唯一还可能显著压缩主流程时间的热点。

### P1：分阶段落盘

- 在生成 `data_integrity`、`default_signal_reproduction`、`factor_window_grid` 后立即写盘。
- 发生中断时可从最后 checkpoint 继续，不必整轮重跑。
- 对研究体验的改善很大，代码风险却较低。

### P2：factor cache 持久化

- 将全量日频 factor cache 持久化为 Parquet/Feather。
- 同一份 raw data 重复研究时可以跳过约 `13s` 的缓存构建。
- 对“当天只跑一次”的场景收益有限，但对后续反复调研究口径有价值。

### P3：进程级并行

- 可按 `factor × ETF` 拆分任务并行。
- 当前不建议先做，因为串行代码已经大幅提速，且并行会放大内存、调试和平台差异成本。
