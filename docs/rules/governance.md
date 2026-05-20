# 治理门禁规则

## MUST

- 主干默认禁止直接 push 和 force push；用户在当前对话中显式授权“直写主干”时，只允许 fast-forward 直写，仍禁止 force push。
- 所有主干改动必须通过 PR，并通过 required status checks；例外是用户显式授权的直写主干链路。
- 关键路径必须由 CODEOWNERS 覆盖并经过 owner review。
- `scripts.research.governance gate` 是本地 hook 和 CI 的强门禁入口。
- `scripts.research.governance.ai_review_gate` 是本地 AI review 报告、风险等级和 Codex Review Scope 的统一校验入口；本地报告保存在 `.local/ai-review/`，不进入仓库。
- CI 必须校验 PR body 中的 `AI Review 风险分级` 和 review 证据；本地报告缺失、无法解析或无法证明低风险时，PR body 必须按 high/unknown 处理。
- 低风险 PR 可以不包含官方 Codex Code Review 链接；高风险或 unknown PR 必须包含官方 Codex Code Review 的通过结论。
- CI 必须用 `pr-review-evidence` job 校验 PR review 证据，并在需要官方 Codex Review 时用 `Codex Review Monitor` status 监听当前 head 的 Codex 评审状态；两者都必须实时读取 review thread resolved/outdated 状态，拦截未解决且未过期的 Codex P0/P1 thread。
- 本地仓库必须设置 `git config core.hooksPath .githooks`，不能只提交 hook 文件。
- `.githooks/pre-commit`、`.githooks/pre-push` 和 `.githooks/reference-transaction` 必须通过 `.githooks/run-python.sh` 调用项目虚拟环境，不能硬编码 `powershell.exe` 或单一平台解释器路径。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push` 和 `scripts.research.governance gate`，并保留 Git LFS pre-push 转交。
- 在远端 rulesets 不生效的私有仓库中，`.githooks/pre-push` 必须本地阻断推送到 `main` / `master`；用户显式授权直写主干时，必须设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`。
- `.githooks/reference-transaction` 必须本地阻断 `refs/heads/main` / `refs/heads/master` 更新，防止绕过 PR 的本地 `git merge`、`git reset` 或分支指针改写；用户显式授权直写主干时，必须设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`，且只允许 fast-forward 更新。
- PR 在 GitHub 云端合并后，同步本地 `main` 到 `origin/main` 时，必须先 `git fetch origin main`，再显式设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并只允许 fast-forward 更新。
- PR 合并收尾必须删除已合并提交分支的本地和远端引用；不得用 force delete 掩盖未合并分支。
- GitHub `main` 的 required status check 必须覆盖静态扫描、类型检查、依赖漏洞扫描、测试、governance gate 和 `pr-review-evidence`。
- `Codex Review Monitor` 只作为高风险或 unknown PR 的 required gate。
- GitHub `main` 必须配置 branch protection 或 ruleset：Require pull request、Require status checks（`Research Governance / governance`、`Research Governance / pr-review-evidence` 与按风险启用的 `Codex Review Monitor`）、Require review from Code Owners、Block force pushes。
- waiver 必须登记 `id`、`rule_id`、`path`、`reason`、`owner`、`approved_by`、`expires_at`、`migration_plan`。
- 过期 waiver、无 owner、无批准人、无迁移计划的 waiver 必须阻断。
- 规则入口、Skill、README、workflow、registry、catalog、pathref 不能漂移。
- [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 是 AI 助手通用入口；[CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 只保留 Claude Code 专属指针。

## SHOULD

- PR 描述应列出已运行检查和证据链接。
- scheduled drift audit 应定期检查主干保护、CODEOWNERS、PR 模板、waiver、规则同步和长期未合并分支。

## MAY

- 对临时过渡期可保留 warning 级检查，但 MUST 规则不能降级为提醒。

## 关键路径

- `CLAUDE.md`
- `AGENTS.md`
- `indexes.md`
- `docs/rules/**`
- `docs/adr/**`
- `.claude/skills/**`
- `.github/workflows/**`
- `.githooks/**`
- `scripts/research/governance/**`
- `scripts/research/registry/**`
- `path_aliases.json`
- `strategies/**`
