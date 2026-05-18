# 治理门禁规则

## MUST

- 主干禁止直接 push 和 force push。
- 所有主干改动必须通过 PR，并通过 required status checks。
- 关键路径必须由 CODEOWNERS 覆盖并经过 owner review。
- `scripts.research.governance gate` 是本地 hook 和 CI 的强门禁入口。
- 在远端 rulesets 不生效的私有仓库中，`.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push`，本地阻断推送到 `main` / `master`。
- waiver 必须登记 `id`、`rule_id`、`path`、`reason`、`owner`、`approved_by`、`expires_at`、`migration_plan`。
- 过期 waiver、无 owner、无批准人、无迁移计划的 waiver 必须阻断。
- 规则入口、Skill、README、workflow、registry、catalog、pathref 不能漂移。

## SHOULD

- 本地提交和推送前启用 `.githooks/pre-commit` 与 `.githooks/pre-push`。
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
