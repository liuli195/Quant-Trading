# ETF 时间窗异质性验证执行计划

制定日期：2026-05-15  
适用策略：[etf_factor_rotation.py](../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->  
关联报告：[2026-05-14-deep-attribution.md](../2026-05-14-deep-attribution.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/2026-05-14-deep-attribution.md -->  
研究规格：[research_spec.md](../research/window_heterogeneity/docs/research_spec.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/research_spec.md -->

## 1. 研究目标

验证三只 ETF 是否对资产级方向因子的时间窗口存在稳定差异，并判断这种差异是否值得继续写入策略参数。

当前已知前提：

- `MA_long` 已有三层证据支持 ETF 异质性：
  - 统一窗口扫描
  - ETF 维度归因
  - 混合窗口确认
- 现有最强组合已指向：
  - AI：短窗
  - 纳指：中窗
  - 黄金：长窗
- 本轮不再重复证明 `MA_long`，而是继续验证：
  - 动量窗口
  - 拥挤度相关窗口
- 第一轮只研究“资产方向节奏”，暂不纳入风险估计类窗口：
  - 暂不研究 `VolWindow`
  - 暂不研究 `PortfolioVolWindow`
  - 暂不研究 `RSRS_N / RSRS_M`
  - 暂不研究 `CrowdWindow`

## 2. 总体推进路径

| 阶段 | 目标 | 主要产物 |
|---|---|---|
| Step 1 | 固化研究口径与数据契约 | 研究规格说明、字段清单、窗口清单 |
| Step 2 | 在研究环境准备基础数据 | 原始行情导出文件、数据完整性检查结果 |
| Step 3 | 复现当前策略默认信号 | 默认窗口复现表、与审计日志对账结果 |
| Step 4 | 做窗口响应研究 | 各 ETF × 因子 × 窗口结果表、窗口曲线 |
| Step 5 | 做稳健性验证 | 发现集/留出集/分段稳定性结果 |
| Step 6 | 形成研究结论 | 专题报告、候选窗口清单 |
| Step 7 | 设计云端确认实验 | 参数扫描 / A-B 方案、实验批次配置 |
| Step 8 | 执行云端确认并决策 | A/B 报告、是否写回策略的结论 |

## 3. 分步执行清单

| Step | 动作 | 输入 | 产物 | 完成标准 |
|---|---|---|---|---|
| 1 | 冻结口径、窗口、通过门槛 | 已有归因报告、当前策略参数 | `research_spec.md` | 因子、窗口、样本、前向收益口径固定 |
| 2 | 导出原始行情 | 聚宽研究环境 | 原始行情 JSON、`data_integrity.md` | 三只 ETF 可对齐，缺失和预热样本显式可查 |
| 3 | 复现默认信号 | 原始行情、`audit_log.jsonl` | 默认信号对账 CSV / MD | 默认窗口下核心信号与审计结果一致 |
| 4 | 做窗口响应扫描 | 原始行情、研究规格 | `factor_window_grid.csv`、曲线 CSV、`best_window_summary.csv` | 能比较共享窗口与 ETF 专属窗口 |
| 5 | 做稳健性验证 | Step 4 输出 | `holdout_validation.csv`、`segment_stability.csv`、`bootstrap_summary.csv`、`robustness_check.md` | 可区分稳定偏好与样本偶然 |
| 6 | 汇总结论 | Step 4-5 输出 | `window-heterogeneity-validation-report.md` | 能回答哪些因子值得继续推进 |
| 7 | 设计云端确认 | Step 6 候选窗口 | A/B 设计文档、`scenario.json`、`manifest.json` | 每组实验都能单独归因 |
| 8 | 执行确认并决策 | 云端回测结果 | `ab-delta-report.md`、最终决策文档 | 明确写回 / 观察 / 放弃 |

## 4. 建议推进顺序

### 第一轮：先证明现象

1. Step 1
2. Step 2
3. Step 3
4. Step 4

第一轮结束后，先回答“你的猜想是否在研究层面站得住”。

### 第二轮：再判断稳定性

1. Step 5
2. Step 6

第二轮结束后，判断“现象是否足够稳，值得进入策略实验”。

### 第三轮：最后讨论写回策略

1. Step 7
2. Step 8

第三轮只在研究结论稳定后启动。

## 5. 当前仓库中已落地的支撑物

| 类型 | 文件 | 用途 |
|---|---|---|
| 研究规格 | [research_spec.md](../research/window_heterogeneity/docs/research_spec.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/research_spec.md --> | 固定字段、窗口、门槛和产物 |
| 云端实验说明 | [cloud_confirmation_plan.md](../research/window_heterogeneity/docs/cloud_confirmation_plan.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/cloud_confirmation_plan.md --> | 约束 Step 7-8 的实验口径 |
| 聚宽导出脚本 | [jq_research_export.py](../research/window_heterogeneity/exports/joinquant/jq_research_export.py) <!-- pathref: strategy_research_project_exports(strategy=etf_factor_rotation, project=window_heterogeneity)/joinquant/jq_research_export.py --> | 在研究环境导出原始行情 JSON |
| 分析脚本 | [analysis.py](../../../../scripts/research/etf_window_research/analysis.py) <!-- pathref: scripts/research/etf_window_research/analysis.py --> | 生成 Step 2-6 的本地研究产物 |
| 研究环境导出脚本生成器 | [research_export.py](../../../../scripts/research/etf_window_research/research_export.py) <!-- pathref: scripts/research/etf_window_research/research_export.py --> | 生成聚宽研究环境可执行的原始行情导出脚本 |

## 6. 关键产物清单

| 阶段 | 产物 |
|---|---|
| 规格 | `research_spec.md` |
| 数据 | 原始行情导出、`data_integrity.md` |
| 复现 | 默认信号对账 CSV / MD |
| 研究 | `factor_window_grid.csv`、窗口曲线、`best_window_summary.csv` |
| 稳健性 | `holdout_validation.csv`、`segment_stability.csv`、`bootstrap_summary.csv` |
| 结论 | `window-heterogeneity-validation-report.md` |
| 实验 | A/B 设计文档、`scenario.json`、`manifest.json` |
| 决策 | `ab-delta-report.md`、最终采用结论 |

## 7. 当前已知事实

- `MA_long` 的 ETF 异质性已有强证据。
- 已知最优方向：
  - AI 偏短窗
  - 纳指偏中窗
  - 黄金偏长窗
- 当前仍未验证：
  - 动量是否也有类似分化
  - 拥挤度相关窗口是否也有类似分化
  - 这些分化是否足够稳定，值得继续增加策略参数复杂度

## 8. 默认假设

- 主样本固定沿用现有回测区间。
- 先研究方向信号，再研究风险估计。
- 先证明现象，再讨论写回策略。
- 不因为某个窗口在全样本最优，就直接认定它适合正式策略。
