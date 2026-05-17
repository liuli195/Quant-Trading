---
name: jq-ab-test
description: 端到端 A/B 实验设计、执行与分析。用于比较策略变体在严格控制变量条件下的表现差异。包含实验设计强制校验（防窗口过短、区间不匹配、无法归因），委托 jq-run 执行，产出 delta 归因报告（含 1000 次 bootstrap 显著性检验）。消耗云端额度，执行前必须展示实验设计并等待用户确认。
---

# JQ AB Test

端到端 A/B 实验：设计校验 → 委托 `jq-run` 执行 → 产出 delta 归因报告。

## 输入

用户口头描述 A/B 需求：策略名、baseline 参数、variant 参数变更、回测区间、初始资金。技能负责生成 AB 配置文件。

## 执行前强制校验

以下任一条不通过，拒绝执行并报告具体问题：

1. 区间 ≥ max(252 天, 10×调仓周期) —— 防窗口过短无统计意义。
2. 每个变体 `params_diff` 声明参数 ≤ 3 个 —— 防无法归因。
3. 所有变体 start_date/end_date 完全一致 —— 防区间不匹配致结论无效。
4. 预估耗时 ≤ 剩余额度 × 80% —— 额度保护。

## 流程

1. 校验实验设计（4 条规则）。
2. 展示实验计划：变体数、预计耗时、剩余额度、校验结果。等待用户确认。
3. 依次委托 `jq-run` 执行每个变体回测。
4. 委托 `jq-analyze` 生成各变体分析报告。
5. 产出 delta 归因报告（参考 [references/workflow.md](references/workflow.md) 的归因结构） <!-- pathref: jq_ab_test_skill/references/workflow.md -->。

## 输出

`strategies/<strategy>/ab_experiments/<name>/report/ab-delta-report.md`

## 边界

- 消耗云端额度。执行前必须用户确认。
- 不直接操作浏览器，回测执行全部委托 `jq-run`。
- 统计显著性使用 1000 次自助法 bootstrap。
- 报告可给出变体优劣判断及采纳建议，用户决定是否修改代码。
- 配置格式见 `scripts/tools/jq_automation/abtest.py` 的 `ABConfig`。
