# 治理门禁规则

## MUST

- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。
- `scripts.research.governance gate` 保留强门禁语义；`scripts.research.governance verify` 负责编排 affected fast、explain 和 full。
- 日常小改默认使用 `scripts.research.governance verify fast`，只表示可继续开发，不作为 PR 或合并证据。
- PR 准备、push 前、CI 和最终交付证据必须使用 `scripts.research.governance verify full`。
- `.githooks/pre-commit` 使用 `scripts.research.governance verify fast --staged`。
- `.githooks/pre-push` 和 CI 必须覆盖完整治理审计和 pathref gate，不得使用 fast。
- `scripts.research.governance.pr_flow` 是本地 PR 自动化入口；`make pr-ready TITLE="<PR标题>"` 负责准备 PR evidence、同步 GitHub draft PR、触发必要的 Codex review 并等待 required checks；`make pr-complete TITLE="<PR标题>"` 负责在无阻断路径上继续 ready-for-review、head-locked merge 和合并后 cleanup。
- GitHub `main` 必须启用 branch protection 或 ruleset：Require pull request、Require status checks、Require conversation resolution、Block force pushes；approval / Code Owner review 是否阻断以远端实际 ruleset / branch protection 为准，`pr_flow` 不得本地硬编码。
- required checks 必须包括 `Research Governance / governance`、`Research Governance / pr-review-evidence`、`Codex Review Monitor`。
- `Research Governance / governance` 通过 `verify full` 汇总静态扫描、类型检查、依赖漏洞扫描、测试、pathref 和 governance gate。
- `pr-review-evidence` 校验 PR body 的 `AI Review 风险分级`、`review_mode=complete` / `partial` 授权、`security_review` / `本地安全 review`、`codex-security` / `security-guidance`、`官方 Codex Review 跳过授权`、P2 保留、Codex Review 证据和高风险 label。
- `Codex Review Monitor` 监听当前 head 的 Codex Review 状态；低风险且无需官方 review 的 PR 可快速通过/空跑。
- `Codex Review Monitor` success 可作为 `pr_flow` 自动采集官方 Codex 通过证据的信号之一，但不能替代 PR body 的 `Codex Code Review 结论`。
- 只要 GitHub conversation resolution ruleset 要求 resolved conversation，任何未 resolved 的 review thread 必须阻断，任何跳过授权不得绕过。
- 修复后的 review thread 只能由 `pr_flow resolve-threads` 或 `pr-ready` / `pr-complete --resolve-thread <thread-id>` resolve，且必须显式传入 thread ID；不得猜测或批量 resolve 全部未处理 thread。
- 本地仓库必须设置 `git config core.hooksPath .githooks`。
- `.githooks/pre-commit`、`.githooks/pre-push`、`.githooks/reference-transaction` 必须通过 `.githooks/run-python.sh` 选择项目虚拟环境，不硬编码单一平台解释器。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push` 和 `scripts.research.governance verify full`，并保留 Git LFS pre-push 转交。
- `.githooks/pre-push` 必须阻断推送到 `main` / `master`；直写主干只在用户当前对话授权时允许，并要求 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`。
- `.githooks/reference-transaction` 必须阻断本地 `refs/heads/main` / `refs/heads/master` 被 merge、reset、delete 或 force rewrite；授权直写也只允许 fast-forward。
- PR 云端合并后，本地同步 `main` 必须设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并只允许 fast-forward 到 `origin/main`。
- PR 合并收尾必须删除已合并提交分支的本地和远端引用；不得 force delete 掩盖未合并分支。
- `pr_flow merge` 必须使用当前 head SHA 的 `--match-head-commit` 合并；`pr_flow cleanup` 必须先 fetch，再走受控 fast-forward，同步后再删除本地和远端已合并分支并验证远端引用消失。
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
