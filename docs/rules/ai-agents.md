# 多 AI Agent 协作规则

## MUST

- 多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支。
- 不允许多个 agent 在同一写入分支上并行修改 repo-tracked 文件。
- `pr-governance-review` 是独立评审 Agent，只做 PR review、治理 review 和测试回归结论，不负责实现改动。
- 所有进入主干的改动必须通过 PR。
- PR 合并前必须有 `pr-governance-review` 的通过结论，并通过 CI 的 `pr-review-evidence` job。
- 本地推送主干由 `.githooks/pre-push` 的代码化门禁阻断；如需紧急绕过，必须使用显式环境变量并留下审计说明。
- 不采用任务登记作为主要协作机制。Git 分支、commit、diff、PR 和 review 承担协作追踪。
- AI 工具入口统一指向 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->；[AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只记录跨工具补充约束，不另立规则源。

## SHOULD

- 分支命名使用 `agent/<tool>/<topic>`、`research/<strategy>/<topic>` 或 `fix/<scope>/<issue>`。
- 长期研究分支应定期 rebase 或关闭，避免主干差异长期堆积。
- 本地共享工作区只用于只读探索、临时验证或单 agent 串行工作。

## MAY

- 简单文档修补可以直接使用短生命周期分支。
- 只读分析不要求创建分支，但不得修改 repo-tracked 文件。
