# ETF 时间窗异质性云端确认计划

制定日期：2026-05-15  
前置研究规格：[research_spec.md](research_spec.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/research_spec.md -->

## 1. 启动条件

仅在研究报告给出 A 级候选时启动云端确认。

## 2. 实验原则

- 单模块单独确认。
- 单次变体最多修改 3 个参数。
- 所有变体必须使用完全一致的回测区间。
- 先做模块级，再做组合级。
- 研究结论不足时，不为了“凑一次回测”强行上云。

## 3. 实验顺序

| 顺序 | 模块 | 说明 |
|---|---|---|
| 1 | 趋势门槛 | 复用已有 `MA_long` 结果，只补必要对照 |
| 2 | 动量 | 共享窗口 vs ETF 专属窗口 vs 保守窗口 |
| 3 | 拥挤度收益窗 | 共享窗口 vs ETF 专属窗口 vs 中性化 / 保守窗口 |
| 4 | 拥挤度形态窗 | 共享窗口 vs ETF 专属窗口 vs 保守窗口 |
| 5 | 组合版 | 当前策略 vs 共享窗口 control vs 专属中心版 vs 专属保守版 |

## 4. 单模块实验模板

| 角色 | 说明 |
|---|---|
| baseline | 当前正式策略参数 |
| shared_control | 研究层最优的共享窗口 |
| etf_specific_center | 研究层最佳 ETF 专属窗口 |
| etf_specific_conservative | 研究层 1-SE 稳健带内的保守窗口 |

## 5. 采用门槛

同时满足：

1. 研究层通过。
2. 单模块 A/B 通过。
3. 组合版在全样本与留出期都改善。
4. Sharpe、Calmar、IR 整体不恶化。
5. 若回撤上升，必须能解释来源，且不是脆弱收益换来的。
6. 结果不能只依赖单一年份、单一 ETF 或单一极端月份。

## 6. 预期产物

| 阶段 | 产物 |
|---|---|
| 设计 | 实验设计文档、`scenario.json`、`manifest.json`、额度估算 |
| 执行 | 每个 run 的 `summary_metrics.json`、标准分析报告 |
| 决策 | `ab-delta-report.md`、最终是否写回策略的结论 |

## 7. 尚未生成的配置

`scenario.json` 与 `manifest.json` 依赖研究报告给出的候选窗口，在研究结论形成前不提前硬编码，避免把未经验证的参数写入批次配置。
