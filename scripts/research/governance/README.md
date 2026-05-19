# 治理审计

`governance/` 用来防止本地研究平台继续扩展后发生入口漂移、文档漂移和目录漂移。

## 命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

`gate` is the enforced entry for hooks and CI. It runs governance audit plus
the pathref checker. The tracked hooks are `.githooks/pre-commit`,
`.githooks/pre-push`, and `.githooks/reference-transaction`. They are not active
just because the files exist; enable them in each local checkout with:

```powershell
git config core.hooksPath .githooks
git config --get core.hooksPath
```

The second command must print `.githooks`.

`.githooks/pre-push` calls all required push gates before handing off to Git LFS:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.branch_protection pre-push
.\.venv\Scripts\python.exe -m scripts.research.governance gate
git lfs pre-push
```

It blocks direct pushes to `main` / `master` when remote rulesets are unavailable,
reruns the full governance gate before push, and preserves the Git LFS hook.
The shell hooks call `.githooks/run-python.ps1` so Git for Windows can reliably
use the repository venv from hook context.

`.githooks/reference-transaction` blocks local updates to `refs/heads/main` and
`refs/heads/master`, including accidental local `git merge` or `git reset` into
the protected branch. After a PR has already merged remotely, local main sync is
an audited break-glass action and must set both environment variables:

```powershell
$env:ALLOW_MAIN_REF_UPDATE="1"
$env:MAIN_REF_UPDATE_REASON="sync origin/main after PR merge"
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
comments, Codex review submissions, and Codex inline review comments, including
inline comment deletion. Trigger comments are counted only when their effective
time is after the current PR head commit, and a passing review must be submitted
after that trigger. It updates one PR comment
marked with `<!-- codex-review-monitor -->`, reporting whether the current PR
head is still waiting for Codex, blocked by P0/P1 findings, or ready for the PR
body evidence to be updated. It also writes the commit status context `Codex
Review Monitor` to the PR head, so trigger-comment deletion can invalidate the
head status instead of only updating a PR discussion comment.

Manual inspection is available through workflow dispatch, or locally with:

```powershell
$env:GITHUB_REPOSITORY="owner/repo"
$env:PR_NUMBER="<number>"
$env:GITHUB_TOKEN="<token>"
.\.venv\Scripts\python.exe -m scripts.research.governance.codex_review_monitor
```

审计范围：

- 仓库级规则文档 [docs/rules/index.md](../../../docs/rules/index.md) <!-- pathref: docs/rules/index.md --> 是否存在，ADR 目录 [docs/adr](../../../docs/adr) <!-- pathref: docs/adr --> 是否连续编号。
- `.githooks/pre-push` 是否仍调用代码化主干保护门禁、完整 gate 和 Git LFS 转交。
- Codex Code Review 规则 [review-guidelines.md](../../../docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> 是否存在，PR 模板是否要求 Codex 评审结论。
- Codex Review Monitor workflow 是否监听 PR head 更新、`@codex review`、Codex review 和 inline review comment。
- `CODEOWNERS` 是否覆盖关键治理路径，`.github/pull_request_template.md` 是否包含规则同步、检查、waiver 和证据项。
- `docs/exceptions/active-waivers.yaml` 中的 waiver 是否有 owner、批准人、过期时间和迁移计划。
- 工具是否登记在中央 registry。
- README、文档入口、测试文件是否存在。
- 主要 CLI 的 `--help` 是否可运行。
- `CLAUDE.md` 与 `jq-research` Skill 是否同步到新入口。
- `research_datasets/catalog.json` 是否和目录一致。
- `docs/indexes/docs_catalog.json`、`reports_catalog.json`、`datasets_catalog.json`、`variants_catalog.json` 是否存在，并和实际报告文件一致。
- `scripts/research/workflows/templates/*.json` 是否符合模板 schema。
- Markdown `pathref` 是否通过校验。

开发单测可用：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit --skip-cli-help --skip-pathrefs
```
