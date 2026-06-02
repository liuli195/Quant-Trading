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

`verify fast` 是日常开发入口；`verify full` 是 push、CI 和最终交付证据。`gate` 是低层完整门禁，由 `verify full` 调用。

## PR Flow

高频 PR 流程只使用：

```powershell
make pr-submit TITLE="<PR标题>"
```

等价于：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow submit --title "<PR标题>"
```

`pr-submit` 读取 [pr-flow-interface-contract.yaml](../../../docs/rules/pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml -->，检查 GitHub repo settings 和 required checks，校验 `.local/ai-review/fragments/*.json`，创建或更新 draft PR，写 PR Evidence JSON，触发 `@codex review`，等待 required checks，执行 head-locked auto-merge，并在 merged 后只做本地 fast-forward 与本地分支删除。远端分支删除交给 GitHub。

接手入口是 `.local/pr-flow/status.json`。`pr-submit` 每次开始写当前 head 的空 `failures`，失败时覆盖为 failures，成功时可留下 `failures: []`；它不是成功证明。pending 不是失败；官方 Codex review 未返回或 required checks 未完成时继续等待，只有真实阻断、配置缺失或超时才写 failures。

排障入口：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow diagnose --pr <PR号>
make pr-diagnose PR=<PR号>
make pr-resolve-threads THREADS="<thread-id> [<thread-id>...]"
```

## Required Checks

GitHub `main` required checks 必须与契约完全一致：

- `PR Flow / review-status`
- `Research Governance / verify-full`
- `PR Flow / evidence`

`PR Flow / evidence` 只读取 PR body 托管区里的 PR Evidence JSON。`PR Flow / review-status` 通过 commit status 表示官方 Codex review 和 unresolved thread 状态；官方 Codex 未返回时保持 pending，官方 P2/P3 进入 PR Evidence `retained` 后可 resolve。`Research Governance / verify-full` 在 GitHub 上执行完整治理验证，本地 PR 前置不重复运行完整验证。

## Hooks 和主干保护

本地 hook 需要在每个 checkout 启用：

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

`.githooks/pre-commit` 运行 `verify fast --staged` 和 commit intent gate；`.githooks/pre-push` 运行主干保护门禁和 `verify full`；`.githooks/reference-transaction` 阻断本地 `main` / `master` 被 merge、reset、delete 或 force rewrite。

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
