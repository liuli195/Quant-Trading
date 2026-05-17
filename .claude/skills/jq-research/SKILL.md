---
name: jq-research
description: 统筹本地优先的策略研究流程。用于把研究想法转成项目模板、本地 fast/full 运行、候选漏斗、云端交接建议，并在需要时委托 jq-run、jq-analyze、jq-fix、jq-param-scan 或 jq-ab-test。适用于用户提出新研究主题、想先本地缩小候选范围、判断哪些方案值得上云确认，或需要理解研究项目下一步时。
---

# JQ Research

把研究重心放在本地：先用 `scripts.research.cli` 走快筛与精筛，再把少量高价值候选交给云端确认。

## 使用

1. 先判断问题属于 `local_exact`、`local_replayable` 还是 `cloud_only`。
2. 需要选模板时，读 [references/template-selection.md](references/template-selection.md) <!-- pathref: jq_research_skill/references/template-selection.md -->。
3. 本地研究编排规则见 [references/workflow.md](references/workflow.md) <!-- pathref: jq_research_skill/references/workflow.md -->。
4. 只有本地门槛通过后，才按 [references/handoff-rules.md](references/handoff-rules.md) <!-- pathref: jq_research_skill/references/handoff-rules.md --> 委托云端确认。

## 边界

- 不复制平台已有逻辑；项目结构、缓存、候选漏斗和状态都以 `scripts.research.cli` 产物为准。
- 不直接替代 `jq-run`、`jq-analyze`、`jq-fix`、`jq-param-scan`、`jq-ab-test`。
- 自己负责理解研究意图、解释结果和决定下一步委托谁。
