---
name: jq-research
description: 统筹本地优先的策略研究流程。用于把研究想法转成项目模板、本地 fast/full 运行、候选漏斗、云端交接建议，并在需要时委托 jq-run、jq-analyze、jq-fix、jq-param-scan 或 jq-ab-test。适用于用户提出新研究主题、想先本地缩小候选范围、判断哪些方案值得上云确认，或需要理解研究项目下一步时。
---

# JQ Research

把研究重心放在本地：先用 `scripts.research.cli` 走快筛与精筛，再把少量高价值候选交给云端确认。参数 variant 默认登记在策略变体库，不直接开 Git 分支；结构 variant 只在用户授权后创建分支或合并。

## 使用

1. 先判断问题属于 `local_exact`、`local_replayable` 还是 `cloud_only`。
2. 需要选模板时，读 [references/template-selection.md](references/template-selection.md) <!-- pathref: jq_research_skill/references/template-selection.md -->，并以 `scripts/research/workflows/templates/` 的模板声明为准。
3. 本地研究编排规则见 [references/workflow.md](references/workflow.md) <!-- pathref: jq_research_skill/references/workflow.md -->。
4. 只有本地门槛通过后，才按 [references/handoff-rules.md](references/handoff-rules.md) <!-- pathref: jq_research_skill/references/handoff-rules.md --> 委托云端确认。
5. 新工具、新数据快照或新报告入口完成后，运行 `scripts.research.governance audit` 检查注册、模板 schema、文档、catalog 和 pathref。

## 边界

- 不复制平台已有逻辑；项目结构、缓存、候选漏斗和状态都以 `scripts.research.cli` 产物为准。
- 通用指标、稳健性、replay 接口和报告片段优先复用 `scripts.research.research_core`。
- 不直接替代 `jq-run`、`jq-analyze`、`jq-fix`、`jq-param-scan`、`jq-ab-test`。
- 不在未授权情况下创建/切换 Git 分支、merge/cherry-pick、修改默认参数或标记结构 variant 为 `merged_confirmed`。
- 自己负责理解研究意图、解释结果和决定下一步委托谁。
