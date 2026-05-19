# 治理门禁规则

## MUST

- 主干禁止直接 push 和 force push。
- 所有主干改动必须通过 PR，并通过 required status checks。
- 关键路径必须由 CODEOWNERS 覆盖并经过 owner review。
- `scripts.research.governance gate` 是本地 hook 和 CI 的强门禁入口。
- PR 必须包含官方 Codex Code Review 的通过结论，CI 必须用 `pr-review-evidence` job 校验该结论，并用 `Codex Review Monitor` status 监听当前 head 的 Codex 评审状态。
- 本地仓库必须设置 `git config core.hooksPath .githooks`，不能只提交 hook 文件。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push` 和 `scripts.research.governance gate`，并保留 Git LFS pre-push 转交。
- 在远端 rulesets 不生效的私有仓库中，`.githooks/pre-push` 必须本地阻断推送到 `main` / `master`。
- `.githooks/reference-transaction` 必须本地阻断 `refs/heads/main` / `refs/heads/master` 更新，防止绕过 PR 的本地 `git merge`、`git reset` 或分支指针改写。
- 同步本地 `main` 到已通过 PR 的 `origin/main` 时，必须显式设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并保留审计说明。
- GitHub `main` 必须配置 branch protection 或 ruleset：Require pull request、Require status checks（`Research Governance / governance`、`Research Governance / pr-review-evidence` 与 `Codex Review Monitor`）、Require review from Code Owners、Block force pushes。
- waiver 必须登记 `id`、`rule_id`、`path`、`reason`、`owner`、`approved_by`、`expires_at`、`migration_plan`。
- 过期 waiver、无 owner、无批准人、无迁移计划的 waiver 必须阻断。
- 规则入口、Skill、README、workflow、registry、catalog、pathref 不能漂移。

## SHOULD

- PR 描述应列出已运行检查和证据链接。
- scheduled drift audit 应定期检查主干保护、CODEOWNERS、PR 模板、waiver、规则同步和长期未合并分支。

## MAY

- 对临时过渡期可保留 warning 级检查，但 MUST 规则不能降级为提醒。

## 关键路径

- `CLAUDE.md`
- `AGENTS.md`
- `docs/rules/**`
- `docs/adr/**`
- `.claude/skills/**`
- `.github/workflows/**`
- `.githooks/**`
- `scripts/research/governance/**`
- `scripts/research/registry/**`
- `path_aliases.json`
- `strategies/**`
