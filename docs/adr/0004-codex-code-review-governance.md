# ADR 0004: 使用官方 Codex Code Review 作为 PR 评审门禁

## 背景

旧流程依赖 `.claude/agents/pr-governance-review.md` 子 Agent 产出评审结论。这个流程只能约束本地助手，不等同于 GitHub PR 上的正式 review，也会让不同 AI 工具各自维护评审入口。

## 决策

- 合并前 AI 评审统一采用官方 Codex Code Review。
- 顶层 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只保留 `Review guidelines` 指向，完整规则维护在 [review-guidelines.md](../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->。
- [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 仍是 AI 助手主入口和权威规则源。
- Codex Code Review 必须由 PR 评论 `@codex review 按 AGENTS.md 和 docs/rules/review-guidelines.md 审；逐条检查 docs/rules/*.md` 明确触发。
- Automatic reviews 可以作为补充，但不能替代上面的明确触发评论。
- PR 描述必须包含 `Codex Code Review 结论`，CI job `pr-review-evidence` 校验该结论。
- GitHub `main` 的 required checks 必须包含 `Research Governance / governance`、`Research Governance / pr-review-evidence` 和 `Codex Review Monitor`。

## 后果

合并前检查从本地子 Agent 结论改为 GitHub PR 上的官方 Codex review 结论。CI 仍保留证据校验，CODEOWNER review 仍是人工 owner 门禁。
