# PR 工作流规则

本文件是本仓库的核心 PR 工作流规则，覆盖分支协作、评审门禁、主干同步和分支清理。

## MUST

- 多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支。
- 不允许多个 agent 在同一写入分支上并行修改 repo-tracked 文件。
- PR review 使用官方 Codex Code Review，不使用本地子 Agent 作为合并前评审门禁；无论实现者是 Claude、Codex、Cursor、Copilot 或人工，都必须走同一套 review。
- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权使用“直写主干”链路。
- “合并到主干”默认含义是创建、更新或准备 PR，不是本地合并 `main`。
- 禁止本地合并主干；AI 助手不得用 `git switch main` 后接 `git merge` / `git reset` 把功能分支提交写入本地 `main`。
- PR 合并前必须有 Codex Code Review 的通过结论，并通过 CI 的 `pr-review-evidence` job 与 `Codex Review Monitor` status。
- 本地推送主干由 `.githooks/pre-push` 的代码化门禁阻断；如用户显式授权直写主干，必须在对应命令上设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`。
- 本地主干 ref 更新由 `.githooks/reference-transaction` 阻断；如用户显式授权直写主干，可设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`，但只允许 fast-forward 更新，禁止 reset、删除或 force rewrite。
- PR 在 GitHub 云端合并后，本地 `main` 必须先 `git fetch origin main`，再显式设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON`，并只用 `git merge --ff-only origin/main` 或等价 fast-forward 命令同步到 `origin/main`。
- 直写主干链路只适用于用户在当前对话中明确说“可以直接提交和推送主干”的场景；执行前仍必须检查 diff、运行相关测试和 `scripts.research.governance gate`，提交说明必须使用简体中文。
- PR 合并后必须删除提交分支的本地和远端引用：先确认已不在该分支，再执行 `git branch -d <branch>` 和 `git push origin --delete <branch>`；远端分支已由 GitHub 自动删除时，必须确认其不存在。
- 不采用任务登记作为主要协作机制。Git 分支、commit、diff、PR 和 review 承担协作追踪。
- AI 工具通用入口统一指向 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；[CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 只保留 Claude Code 专属指针。

## SHOULD

- 分支命名使用 `agent/<tool>/<topic>`、`research/<strategy>/<topic>` 或 `fix/<scope>/<issue>`。
- 长期研究分支应定期 rebase 或关闭，避免主干差异长期堆积。
- 本地共享工作区只用于只读探索、临时验证或单 agent 串行工作。

## MAY

- 简单文档修补可以直接使用短生命周期分支。
- 只读分析不要求创建分支，但不得修改 repo-tracked 文件。
