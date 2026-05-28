# 治理门禁规则

## MUST

- `scripts.research.governance gate` 是本地 hook 和 CI 的强门禁入口。
- `.githooks/pre-commit` 使用 `scripts.research.governance gate --fast`，只跑快速治理审计，跳过 CLI help 和 pathref gate。
- `.githooks/pre-push` 和 CI 必须使用完整 `scripts.research.governance gate`，覆盖完整治理审计和 pathref gate。
- `scripts.research.governance.pr_flow` 是本地 PR 自动化入口；`make pr-ready TITLE="<PR标题>"` 负责准备 PR evidence、同步 GitHub draft PR、触发必要的 Codex review 并等待 required checks。
- GitHub `main` 必须启用 branch protection 或 ruleset：Require pull request、Require status checks、Require review from Code Owners、Block force pushes。
- required checks 必须包括 `Research Governance / governance`、`Research Governance / pr-review-evidence`、`Codex Review Monitor`。
- `Research Governance / governance` 汇总静态扫描、类型检查、依赖漏洞扫描、测试、pathref 和 governance gate。
- `pr-review-evidence` 校验 PR body 的 `AI Review 风险分级`、`review_mode=complete` / `partial` 授权、`security_review` / `本地安全 review`、`codex-security` / `security-guidance`、`官方 Codex Review 跳过授权`、P2 保留、Codex Review 证据和高风险 label。
- `Codex Review Monitor` 监听当前 head 的 Codex Review 状态；低风险且无需官方 review 的 PR 可快速通过/空跑。
- `Codex Review Monitor` success 可作为 `pr_flow` 自动采集官方 Codex 通过证据的信号之一，但不能替代 PR body 的 `Codex Code Review 结论`。
- 未解决且未过期的 Codex P0/P1 thread 必须阻断，任何跳过授权不得绕过。
- 本地仓库必须设置 `git config core.hooksPath .githooks`。
- `.githooks/pre-commit`、`.githooks/pre-push`、`.githooks/reference-transaction` 必须通过 `.githooks/run-python.sh` 选择项目虚拟环境，不硬编码单一平台解释器。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push` 和 `scripts.research.governance gate`，并保留 Git LFS pre-push 转交。
- `.githooks/pre-push` 必须阻断推送到 `main` / `master`；直写主干只在用户当前对话授权时允许，并要求 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`。
- `.githooks/reference-transaction` 必须阻断本地 `refs/heads/main` / `refs/heads/master` 被 merge、reset、delete 或 force rewrite；授权直写也只允许 fast-forward。
- PR 云端合并后，本地同步 `main` 必须设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并只允许 fast-forward 到 `origin/main`。
- PR 合并收尾必须删除已合并提交分支的本地和远端引用；不得 force delete 掩盖未合并分支。
- CODEOWNERS 必须覆盖关键路径。
- waiver 必须登记 `id`、`rule_id`、`path`、`reason`、`owner`、`approved_by`、`expires_at`、`migration_plan`；过期或字段不全必须阻断。
- 规则入口、Skill、README、workflow、registry、catalog、pathref 不能漂移。

## 关键路径

- `AGENTS.md`
- `CLAUDE.md`
- `indexes.md`
- `docs/rules/**`
- `docs/adr/**`
- `.codex/skills/**`
- `.claude/skills/**`
- `.github/workflows/**`
- `.githooks/**`
- `scripts/research/governance/**`
- `scripts/research/registry/**`
- `path_aliases.json`
- `strategies/**`

## SHOULD

- PR 描述列出已运行检查和证据链接。
- scheduled drift audit 定期检查主干保护、CODEOWNERS、PR 模板、waiver、规则同步和长期未合并分支。

## MAY

- 过渡期可保留 warning 级检查；MUST 规则不能降级为提醒。
