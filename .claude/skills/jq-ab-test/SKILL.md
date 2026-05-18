---
name: jq-ab-test
description: 端到端 A/B 实验设计、执行与分析。用于比较策略变体在严格控制变量条件下的表现差异。包含实验设计强制校验（防窗口过短、区间不匹配、无法归因），委托 jq-run 执行，产出 delta 归因报告（含 1000 次 bootstrap 显著性检验）。消耗云端额度，执行前必须展示实验设计并等待用户确认。
---

# JQ AB Test

端到端 A/B 实验：设计校验 → 委托 `jq-run` 执行 → 产出 delta 归因报告。

## 输入

用户口头描述 A/B 需求：策略名、baseline 参数、`variant_id`、variant 参数变更、回测区间、初始资金。技能负责生成 AB 配置文件。

参数变体默认来自策略变体库：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.variants materialize `
  --strategy-dir strategies\<strategy> --variant-id <variant_id>
```

结构变体必须已经有代码来源和云端确认材料；未获用户授权时，不创建分支、不切换分支、不 merge、不 cherry-pick。

## 执行前强制校验

以下任一条不通过，拒绝执行并报告具体问题：

1. 区间 ≥ max(252 天, 10×调仓周期) —— 防窗口过短无统计意义。
2. 每个参数变体 `params_diff` 声明参数 ≤ 3 个 —— 防无法归因。
3. 所有变体 start_date/end_date 完全一致 —— 防区间不匹配致结论无效。
4. 预估耗时 ≤ 剩余额度 × 80% —— 额度保护。
5. 结构变体必须有 `variant_id` 和 `code_source`，且不能在 A/B 执行中临时修改主策略代码。

## 流程

1. 校验实验设计（5 条规则）。
2. 读取或登记 `variant_id`，参数变体用 `scripts.research.variants materialize` 生成上传快照。
   现在 `scripts.tools.jq_automation ab` 原生支持 `variants[].variant_id`：A/B 配置中只写 label/role/variant_id，参数和结构代码来源从策略变体登记表读取。
3. 展示实验计划：变体数、预计耗时、剩余额度、校验结果。等待用户确认。
4. 依次委托 `jq-run` 执行每个变体回测。
5. 委托 `jq-analyze` 生成各变体分析报告。
6. 产出 delta 归因报告（参考 [references/workflow.md](references/workflow.md) 的归因结构） <!-- pathref: jq_ab_test_skill/references/workflow.md -->。

## 输出

`strategies/<strategy>/ab_experiments/<name>/report/ab-delta-report.md`

## 边界

- 消耗云端额度。执行前必须用户确认。
- 不直接操作浏览器，回测执行全部委托 `jq-run`。
- 统计显著性使用 1000 次自助法 bootstrap。
- 报告可给出变体优劣判断及采纳建议，用户决定是否修改代码。
- 参数变体 A/B 不依赖 Git 分支；结构变体 A/B 只比较已登记代码来源。
- 配置格式见 `scripts/tools/jq_automation/abtest.py` 的 `ABConfig`。
