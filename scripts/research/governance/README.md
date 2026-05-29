# 治理审计

`governance/` 用来防止本地研究平台继续扩展后发生入口漂移、文档漂移和目录漂移。

## 命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files docs\rules\commands.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify fast --files docs\rules\commands.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
```

`verify explain` 只解释本次改动命中的 scoped checks，不执行命令。
`verify fast` 执行 affected scoped checks，输出 checked/skipped/full-not-run，
只代表可以继续开发。PR、push 和 CI 以 `verify full` 为统一入口。
`verify full` 运行 ruff、bandit、mypy、pip-audit、governance tests、pathref 和
完整 `gate`，可作为 PR/push/CI/最终交付证据。

`gate` runs governance audit plus the pathref checker. It remains the low-level
full gate that `verify full` invokes. The tracked hooks are `.githooks/pre-commit`,
`.githooks/pre-push`, and `.githooks/reference-transaction`. They are not active
just because the files exist; enable them in each local checkout with:

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

The second command must print `.githooks`.

## 风险分级评审入口

```powershell
make pre-pr
make ai-review
make risk-check
make pr-ready TITLE="<PR标题>"
make pr-complete TITLE="<PR标题>"
```

`make ai-review` 校验 `.local/ai-review/latest.json`，并生成 `.local/ai-review/latest.md` 和 `.local/ai-review/codex-review-scope.md`。`.local/` 不入库；CI 通过 PR body 的 `AI Review 风险分级` 和 `pr-review-evidence` job 复验风险证据。

`make pr-ready TITLE="<PR标题>"` 是本地 PR 自动化入口，等价于：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow ready --title "<PR标题>"
```

它会准备本地 review 证据、渲染 `.local/ai-review/pr-body.md`、同步 GitHub PR 的 `pr-flow` 托管区、按风险补 `ai-risk-review` label、触发必要的 `@codex review`，并等待 required checks。

`make pr-complete TITLE="<PR标题>"` 会在 `pr-ready` 通过后继续把 draft PR 标记为 ready、等待新一轮 required checks、用当前 head SHA 锁定合并，并按受控 fast-forward 规则同步本地 `main`、删除已合并的本地和远端分支。已有 PR 可传 `PR=<PR号>`：

```powershell
make pr-complete TITLE="<PR标题>" PR=<PR号>
make pr-merge PR=<PR号>
make pr-cleanup PR=<PR号>
```

`pr_flow sync` 创建 PR 前会检查当前分支是否已推送到 `origin`；缺远端 head 时输出 `PUSH_REQUIRED` 和对应 `git push -u origin <branch>`。

排障时先使用 `diagnose` 汇总当前 PR 状态：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow diagnose --pr <PR号>
```

它会读取 head、PR body evidence、merge state、review decision、required checks、Codex trigger/completion 和 review threads，并给出下一步机器状态；仓库禁用 auto-merge 时不要把 `--auto` 当作建议路径。

`.local/ai-review/latest.json` 的 `reviewers` 字段必须记录至少两个独立 reviewer，作为子 agent 交叉评审证据；单 reviewer 或重复 reviewer 会被 `make ai-review` 拒绝。`cross_review.review_skills` 必须记录 Superpowers 评审模板，对应值为 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` 和 `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`。`security_review` 必须记录本地安全 review：Codex provider 要求 `tool=codex-security`，Claude provider 要求 `tool=security-guidance`，并填写 `evidence`。schema v2 默认 `review_mode=complete`，`complete_review.iterations` 必须证明每个 reviewer 持续查找更多发现，直到最后一轮 `no_new_findings=true` 且 `new_findings=[]`；`review_mode=partial` 必须填写用户授权。生成的 `.local/ai-review/latest.md` 会列出交叉评审和安全 review 证据。PR body 的 `子 agent 交叉评审` 字段必须使用 `reviewers: A, B` 写明两个独立 reviewer，还必须说明任务分发情况，未分发时写明具体原因；`本地安全 review` 字段必须写明 `provider`、`tool` 和 `evidence`。high/unknown PR 必须带 `ai-risk-review` label。

`.githooks/pre-push` calls all required push gates before handing off to Git LFS:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.branch_protection pre-push
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
git lfs pre-push
```

It blocks direct pushes to `main` / `master` when remote rulesets are unavailable,
reruns full governance verification before push, and preserves the Git LFS hook.
The shell hooks call `.githooks/run-python.sh` only to choose the current
worktree virtualenv on POSIX Git shell environments. Daily local commands should
call `.venv` Python directly; UTF-8 output is handled by environment variables.

`.githooks/reference-transaction` blocks local updates to `refs/heads/main` and
`refs/heads/master`, including accidental local `git merge` or `git reset` into
the protected branch. After a PR has already merged remotely, local main sync is
an audited sync action and must set both environment variables. The hook also
checks that the new local protected-branch SHA equals `refs/remotes/origin/<branch>`
and that the update is fast-forward:

```powershell
$env:ALLOW_MAIN_REF_UPDATE="1"
$env:MAIN_REF_UPDATE_REASON="sync origin/main after PR merge"
```

PR 在 GitHub 云端合并后的本地收尾示例：

```powershell
git fetch origin main
$env:ALLOW_MAIN_REF_UPDATE="1"
$env:MAIN_REF_UPDATE_REASON="sync origin/main after PR #<n> merge"
git switch main
git merge --ff-only origin/main
Remove-Item Env:\ALLOW_MAIN_REF_UPDATE -ErrorAction SilentlyContinue
Remove-Item Env:\MAIN_REF_UPDATE_REASON -ErrorAction SilentlyContinue
git branch -d <branch>
git push origin --delete <branch>
```

其中 `<branch>` 是已合并 PR 的提交分支。如果 GitHub 已自动删除远端分支，只需确认远端分支不存在；不要用 force delete 掩盖未合并分支。

用户在当前对话中显式授权直接提交和推送主干时，使用独立的直写主干链路。该链路仍要求先检查 diff、运行相关测试和 governance gate，并且只允许 fast-forward 更新；禁止 reset、删除或 force rewrite：

```powershell
git fetch origin main
git switch main
git status --short --branch

$env:ALLOW_DIRECT_MAIN_WRITE="1"
$env:DIRECT_MAIN_WRITE_REASON="user explicitly authorized direct main commit: <reason>"
git commit -m "<简体中文提交说明>"

$env:ALLOW_DIRECT_MAIN_WRITE="1"
$env:DIRECT_MAIN_WRITE_REASON="user explicitly authorized direct main push: <reason>"
git push origin main

Remove-Item Env:\ALLOW_DIRECT_MAIN_WRITE -ErrorAction SilentlyContinue
Remove-Item Env:\DIRECT_MAIN_WRITE_REASON -ErrorAction SilentlyContinue
```

GitHub `main` must also enforce the same policy with branch protection or a
ruleset:

- require pull request before merging;
- require status check `Research Governance / governance`;
- require status check `Research Governance / pr-review-evidence`;
- require status check `Codex Review Monitor`;
- require review from Code Owners;
- block force pushes.

## Codex review monitor

`Codex Review Monitor` listens to PR head updates, PR `@codex review` trigger
comments, Codex review submitted/edited/dismissed events, and Codex inline
review comments, including inline comment deletion. Trigger comments are counted
only when their effective time is after the current PR head update, and a
passing review must be submitted after that trigger. Unresolved review threads
block when GitHub conversation resolution is required, regardless of
whether the thread is advisory or outdated. It updates one PR comment
marked with `<!-- codex-review-monitor -->`, reporting whether the current PR
head is still waiting for Codex, blocked, or ready for the PR body evidence to
be updated. It also writes the commit status context `Codex
Review Monitor` to the PR head, so trigger-comment deletion can invalidate the
head status instead of only updating a PR discussion comment. Low-risk PRs that
do not require official Codex review can pass this required status without an
`@codex review` trigger after PR evidence proves that official review is not
required.

`Research Governance / pr-review-evidence` reruns on PR metadata updates,
Codex review submitted/edited/dismissed events, and inline review comment
create/edit/delete events so its evidence decision is refreshed when Codex
findings are edited, removed, or dismissed.

Manual inspection is available through workflow dispatch, or locally with:

```powershell
$env:GITHUB_REPOSITORY="owner/repo"
$env:PR_NUMBER="<number>"
$env:GITHUB_TOKEN="<token>"
.\.venv\Scripts\python.exe -m scripts.research.governance.codex_review_monitor
```

审计范围：

- 仓库级规则文档 [docs/rules/index.md](../../../docs/rules/index.md) <!-- pathref: docs/rules/index.md --> 是否存在，ADR 目录 [docs/adr](../../../docs/adr) <!-- pathref: docs/adr --> 是否连续编号。
- `.githooks/pre-push` 是否仍调用代码化主干保护门禁、完整 `verify full` 和 Git LFS 转交。
- Codex Code Review 规则 [review-guidelines.md](../../../docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> 是否存在，PR 模板是否要求 Codex 评审结论。
- Codex Review Monitor workflow 是否监听 PR head 更新、`@codex review`、Codex review 和 inline review comment。
- `CODEOWNERS` 是否覆盖关键治理路径，`.github/pull_request_template.md` 是否包含规则同步、检查、waiver 和证据项。
- `docs/exceptions/active-waivers.yaml` 中的 waiver 是否有 owner、批准人、过期时间和迁移计划。
- 工具是否登记在中央 registry。
- README、文档入口、测试文件是否存在。
- 主要 CLI 的 `--help` 是否可运行。
- `AGENTS.md`、`indexes.md`、`CLAUDE.md` 与 owner Skill / Claude adapter 是否同步到新入口。
- `research_datasets/catalog.json` 是否和目录一致。
- `docs/indexes/docs_catalog.json`、`reports_catalog.json`、`datasets_catalog.json`、`variants_catalog.json` 是否存在，并和实际报告文件一致。
- `scripts/research/workflows/templates/*.json` 是否符合模板 schema。
- Markdown `pathref` 是否通过校验。

开发单测可用：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit --skip-cli-help --skip-pathrefs
```
