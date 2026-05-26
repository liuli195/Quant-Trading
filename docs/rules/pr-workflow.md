# PR 工作流规则

本文件是本仓库的核心 PR 工作流规则，覆盖分支协作、评审门禁、主干同步和分支清理。

## MUST

- 多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支。
- 不允许多个 agent 在同一写入分支上并行修改 repo-tracked 文件。
- 所有任务默认按优先分发原则执行：主会话只负责流程编排、范围确认、结果汇总和最终验证，任务优先分发给子agent执行；简单只读查询、强串行依赖或工具权限只在主会话可用时，必须说明不分发理由。
- PR 合并前必须完成本地静态扫描、本地 AI review 和问题评级；P0/P1 问题未关闭时禁止进入下一阶段。
- PR code review 必须委派至少两个独立子 agent 做子 agent 交叉评审；评审子 agent 必须使用 Superpowers 模板 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` 和 `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`，并在 PR body 中用 `reviewers: A, B` 记录两个独立 reviewer；实现者或主会话不得作为唯一 reviewer。
- 本地 AI review 必须包含安全 review 证据：Codex provider 必须使用 `codex-security`，Claude provider 必须使用 `security-guidance`；本地报告写入 `security_review`，PR body 写入 `本地安全 review`。
- 本地 AI review 默认使用 `complete` 完全 review 模式；两个 reviewer 必须持续查找更多发现，直到各自最后一轮明确记录无新发现。只有用户显式授权并记录 `authorized_by`、`reason`、`evidence` 时，才能使用 `partial` 不完全模式。
- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权使用“直写主干”链路。
- “合并到主干”默认含义是创建、更新或准备 PR，不是本地合并 `main`。
- 禁止本地合并主干；AI 助手不得用 `git switch main` 后接 `git merge` / `git reset` 把功能分支提交写入本地 `main`。
- 低风险 PR 可以不触发官方 Codex Code Review，但必须提供本地 AI review 报告、CI 通过证据和 P2 保留说明。
- 高风险或 unknown PR 默认必须加 `ai-risk-review`，并触发官方 Codex Code Review；用户显式授权跳过时，必须在 PR body 记录 `官方 Codex Review 跳过授权` 的 `authorized_by`、`reason` 和 `evidence`。
- 官方 Codex Review 触发评论必须保留当前 PR、当前 head SHA、Review Scope 和本地门禁证据；禁止用“不要执行命令”“只做静态 diff review”这类指令切断仓库、diff 或命令上下文。
- 大型 PR 的官方 Codex Code Review 必须使用 `Codex Review Scope`，只审高风险目录和高风险规则命中改动的 P0/P1 逻辑风险。
- 无法生成明确 `Codex Review Scope` 的大型 PR，应拆分 PR；未拆分时按全量高风险 PR 处理。
- 高风险或 unknown PR 合并前必须有 Codex Code Review 的通过结论，或用户显式授权跳过官方 review；并通过 CI 的 `pr-review-evidence` job 与 `Codex Review Monitor` status。二者必须拦截未解决且未过期的 Codex P0/P1 review thread，跳过授权不得绕过该阻断。
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
