# ADR 0004: 使用官方 Codex Code Review 作为 PR 评审门禁

## Why
旧流程依赖本地子 Agent 产出评审结论，只能约束本地助手，不等同于 GitHub PR 上的正式 review。

## What Changes
- 合并前 AI 评审统一采用官方 Codex Code Review
- 顶层 AGENTS.md 只保留 Review guidelines 指向
- Codex Code Review 必须由 PR 评论 `@codex review` 明确触发
- PR 描述必须包含 PR Evidence JSON
- GitHub main 的 required checks 必须包含 PR Flow / review-status 和 verify-full

## Impact
合并前检查从本地子 Agent 结论改为 GitHub PR 上的官方 Codex review 结论。CI 仍保留证据校验。

---
source: docs/adr/0004-codex-code-review-governance.md
migration: 历史 ADR 迁移 — 极简归档
