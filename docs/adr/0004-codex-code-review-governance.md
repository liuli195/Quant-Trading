# ADR 0004: 使用官方 Codex Code Review 作为 PR 评审门禁

## 背景

旧流程依赖 `.claude/agents/pr-governance-review.md` 子 Agent 产出评审结论。这个流程只能约束本地助手，不等同于 GitHub PR 上的正式 review，也会让不同 AI 工具各自维护评审入口。

## 状态

Superseded in part by [ADR 0005](0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md -->

## 决策

- 合并前 AI 评审统一采用官方 Codex Code Review。
- 顶层 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只保留 `Review guidelines` 指向，完整规则维护在 [review-guidelines.md](../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->。此条已由 [ADR 0005](0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md --> 更新为 `AGENTS.md` 作为通用入口，规则索引归 [docs/rules/index.md](../rules/index.md) <!-- pathref: docs/rules/index.md -->，ADR 入口归 [docs/adr/index.md](index.md) <!-- pathref: docs/adr/index.md -->。
- [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 仍是 AI 助手主入口和权威规则源。此条已由 [ADR 0005](0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md --> 更新为 `CLAUDE.md` 只保留到 `AGENTS.md` 的入口指针。
- Codex Code Review 必须由 PR 评论 `@codex review` 明确触发；具体审查范围由 PR body 或触发评论中的 Review Scope 提供。
- Automatic reviews 可以作为补充，但不能替代上面的明确触发评论。
- PR 描述必须包含 `pr-flow` 托管区的 PR Evidence JSON，CI job `PR Flow / evidence` 校验该 JSON。
- GitHub `main` 的 required checks 必须包含 `PR Flow / review-status`、`Research Governance / verify-full` 和 `PR Flow / evidence`。

## 后果

合并前检查从本地子 Agent 结论改为 GitHub PR 上的官方 Codex review 结论。CI 仍保留证据校验；approval / Code Owner review 只在远端实际 branch protection / ruleset 要求时作为合并门禁。
