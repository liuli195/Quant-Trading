# ADR 0006: PR 风险分级评审流程

## Why
当前流程要求所有 PR 合并前都完成官方 Codex Code Review。在低风险 PR 和大型 PR 上造成等待时间过长、重复 review 过多、CI 循环过多。

## What Changes
- 采用风险分级评审流程：所有 PR 必须先完成本地静态扫描、本地 AI review 和问题评级
- 本地 AI review 必须由至少两个独立 reviewer 完成子 agent 交叉评审
- P0/P1 问题必须修复或证明误报后才能继续
- 官方 Codex Review 是否等待由 PR Evidence official_review.decision 决定
- 风险分级影响是否默认触发官方 review 和 scope

## Impact
无法证明低风险的 PR 一律按高风险处理；label 只保留人工标记语义；规则、PR 模板、workflow 和 governance gate 必须使用同一套风险评级语义。

---
source: docs/adr/0006-risk-tiered-pr-review.md
migration: 历史 ADR 迁移 — 极简归档
