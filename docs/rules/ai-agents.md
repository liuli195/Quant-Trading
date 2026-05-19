# 多 AI Agent 协作规则

## MUST

- 多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支。
- 不允许多个 agent 在同一写入分支上并行修改 repo-tracked 文件。
- PR review 使用官方 Codex Code Review，不使用本地子 Agent 作为合并前评审门禁；无论实现者是 Claude、Codex、Cursor、Copilot 或人工，都必须走同一套 review。
- 所有进入主干的改动必须通过 PR。
- “合并到主干”默认含义是创建、更新或准备 PR，不是本地合并 `main`。
- 禁止本地合并主干；AI 助手不得用 `git switch main` 后接 `git merge` / `git reset` 把功能分支提交写入本地 `main`。
- PR 合并前必须有 Codex Code Review 的通过结论，并通过 CI 的 `pr-review-evidence` job 与 `Codex Review Monitor` status。
- 本地推送主干由 `.githooks/pre-push` 的代码化门禁阻断；如需紧急绕过，必须使用显式环境变量并留下审计说明。
- 本地主干 ref 更新由 `.githooks/reference-transaction` 阻断；PR 在 GitHub 云端合并后，本地 `main` 必须先 `git fetch origin main`，再显式设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON`，并只用 `git merge --ff-only origin/main` 或等价 fast-forward 命令同步到 `origin/main`。
- PR 合并后必须删除提交分支的本地和远端引用：先确认已不在该分支，再执行 `git branch -d <branch>` 和 `git push origin --delete <branch>`；远端分支已由 GitHub 自动删除时，必须确认其不存在。
- 不采用任务登记作为主要协作机制。Git 分支、commit、diff、PR 和 review 承担协作追踪。
- AI 工具入口统一指向 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->；[AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只记录跨工具补充约束，不另立规则源。

## SHOULD

- 分支命名使用 `agent/<tool>/<topic>`、`research/<strategy>/<topic>` 或 `fix/<scope>/<issue>`。
- 长期研究分支应定期 rebase 或关闭，避免主干差异长期堆积。
- 本地共享工作区只用于只读探索、临时验证或单 agent 串行工作。

## MAY

- 简单文档修补可以直接使用短生命周期分支。
- 只读分析不要求创建分支，但不得修改 repo-tracked 文件。
