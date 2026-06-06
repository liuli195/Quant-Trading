# 治理审计

`governance/` 用来防止本地研究平台继续扩展后发生入口漂移、文档漂移和目录漂移。规则入口见 [docs/rules/index.md](../../../docs/rules/index.md) <!-- pathref: docs/rules/index.md -->，ADR 入口见 [docs/adr/index.md](../../../docs/adr/index.md) <!-- pathref: docs/adr/index.md -->。

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files docs\rules\commands.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs\rules\commands.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
```

`verify fast` 是日常开发入口；本地 PR 提交和 pre-push 不重复运行完整验证；`verify full` 是 CI 和最终合并证据。`gate` 是低层完整门禁，由 `verify full` 调用。

## PR Flow

高频 PR 流程只使用：

```powershell
make pr-submit TITLE="<PR标题>"
```

等价于：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow submit --title "<PR标题>"
```

`pr-submit` 读取 [pr-flow-interface-contract.yaml](../../../docs/rules/pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml -->，检查 GitHub repo settings 和 required checks，校验 `.local/ai-review/fragments/*.json`，创建或更新 draft PR，sync PR Evidence，ready-for-review，触发或复用当前 head 的 `@codex review`，等待 required checks，执行 head-locked auto-merge，并在 merged 后只做本地 fast-forward 与本地分支删除。远端分支删除交给 GitHub。

同一 head/diff 的 fragments 可复用；PR body 或 status 更新不会单独要求重新 review。GitHub update-branch 生成的同步主干 merge commit 会自动按 commit 级 `no_issue: true` 进入 PR Evidence，PR 级 closes/reference 不受影响。`main` 在其他 worktree 时，本地收尾会在该 worktree 同步 `main`。

接手入口是 `.local/pr-flow/status.json`。运行时只写接手快照 v3，不保留旧 `schema/head/failures` 字段；它不是成功证明。pending 不是失败；官方 Codex review 未返回或 required checks 未完成时继续等待，只有真实阻断、配置缺失或超时才写 `blocking_signals`、`diagnostic_signals`、`suggested_next_actions` 和必要的 `evidence_artifacts`。cleanup 后 dirty worktree 停 `EXCEPTION_REQUIRED` / `WORKTREE_DIRTY_AFTER_CLEANUP`，raw status 落盘，cleanup 不自动修复。

失败接手入口先读 `.local/pr-flow/status.json`；`diagnose` 只保留为 `pr-submit` 内部归因和开发测试面，不作为用户命令入口。unresolved review thread 明细写入 `.local/pr-flow/resolve-threads-plan.json`，显式处理 review thread 时使用：

```powershell
make pr-resolve-threads THREADS="<thread-id> [<thread-id>...]"
```

## Required Checks

GitHub `main` required checks 必须与契约完全一致：

- `PR Flow / review-status`
- `Research Governance / verify-full`
- `PR Flow / evidence`

`PR Flow / evidence` 只读取 PR body 托管区里的 PR Evidence JSON。`PR Flow / review-status` 通过 commit status 表示官方 Codex review 和 unresolved thread 状态；官方 Codex 未返回时保持 pending，官方 P2/P3 进入 PR Evidence `retained` 后可 resolve。`Research Governance / verify-full` 在 GitHub 上执行完整治理验证，本地 PR 前置不重复运行完整验证。

`issue_comment` 事件只进入默认分支 `codex-review-router.yml`。router 识别 `@codex review`、`Codex Review:`、edited 和 deleted PR 评论后，先把 `PR Flow / review-status` 写成 pending，再用 PR head branch dispatch `codex-review-monitor.yml` worker。router 成功调度后不写 success；最终 success、failure、error 或 skipped 只由 worker 写。

`codex-review-monitor.yml` 是 PR branch worker，保留 `pull_request`、`pull_request_review`、`pull_request_review_comment` 和 `workflow_dispatch` 入口，不监听 `issue_comment`。`workflow_dispatch` 接收 `pr_number`、`expected_head_sha`、`trigger_event`、`trigger_run_id`；worker 对 `workflow_dispatch` 也必须写 pending，并用 finalizer 兜底 checkout、setup、依赖安装等基础设施失败。`expected_head_sha` 和当前 PR head 不一致时，worker 写 `PR head changed before monitor completed` error 并停止。

## Hooks 和主干保护

本地 hook 需要在每个 checkout 启用：

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

`.githooks/pre-commit` 运行 `verify fast --staged` 和 commit intent gate；`.githooks/pre-push` 运行主干保护门禁、local review fragments freshness 非阻断提醒和 Git LFS 转交，不运行本地 `verify full`；`.githooks/reference-transaction` 阻断本地 `main` / `master` 被 merge、reset、delete 或 force rewrite。

pre-push freshness 提醒只读取现有 `.local/ai-review/fragments/*.json`，不生成、不刷新、不修改 fragments。看到 stale diff 提醒后，先重新 review / 重新映射 fragments，再运行 `pr-submit`；same diff 仅 head stale 时，`pr-submit` 可刷新 fragment head。

PR 在 GitHub 云端合并后的本地收尾只允许 fast-forward：

```powershell
git fetch origin main
$env:ALLOW_MAIN_REF_UPDATE="1"
$env:MAIN_REF_UPDATE_REASON="sync origin/main after PR #<n> merge"
git switch main
git merge --ff-only origin/main
git branch -d <branch>
```

## 审计范围

- 规则文档、ADR 索引、CODEOWNERS、workflow、PR template、waiver、tool registry 和 pathref。
- `AGENTS.md`、`CLAUDE.md` 与 `.agents/skills/` 是否同步到当前入口。
- required checks、PR Evidence JSON、Codex review status 和 commit intent 是否仍使用同一契约。
- 主要 CLI 的 `--help` 是否可运行。

开发单测可用：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit --skip-cli-help --skip-pathrefs
```
