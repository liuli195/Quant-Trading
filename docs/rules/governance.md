# 治理门禁规则

## MUST

- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。
- `scripts.research.governance gate` 保留强门禁语义；`scripts.research.governance verify` 负责编排 affected fast、explain 和 full。
- 日常小改默认使用 `scripts.research.governance verify fast`，只表示可继续开发，不作为 PR 或合并证据。
- PR 准备、push 前、CI 和最终交付证据必须使用 `scripts.research.governance verify full`。
- `.githooks/pre-commit` 使用 `scripts.research.governance verify fast --staged`。
- `.githooks/pre-push` 和 CI 必须覆盖完整治理审计和 pathref gate，不得使用 fast。
- `scripts.research.governance.pr_flow` 是本地 PR 自动化入口；高频 PR 流程只推荐 `make pr-submit TITLE="<PR标题>"`，它按 [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md --> 和 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml --> 推进到 GitHub auto-merge 和本地收尾。
- GitHub `main` 必须启用 branch protection 或 ruleset：Require pull request、Require status checks、Require conversation resolution、Block force pushes；approval / Code Owner review 是否阻断以远端实际 ruleset / branch protection 为准，`pr_flow` 不得本地硬编码。
- required checks 必须与 `PR Flow Interface Contract` 完全一致：`PR Flow / review-status`、`Research Governance / verify-full`、`PR Flow / evidence`。
- `Research Governance / verify-full` 通过 `verify full` 汇总静态扫描、类型检查、依赖漏洞扫描、测试、pathref 和 governance gate。
- `PR Flow / evidence` 只校验 PR body 托管区中的 PR Evidence JSON v1；CI 不读取本地 `.local` 产物。
- `PR Flow / review-status` 监听当前 head 的官方 Codex review 和 unresolved threads。官方 Codex 未返回时保持 pending；官方 P0/P1、无 severity thread 和 unresolved human thread 阻断；官方 P2/P3 由 `pr_flow` 接受、resolve，并写入 PR Evidence `retained`。
- 只要 GitHub conversation resolution ruleset 要求 resolved conversation，未 resolved 的 review thread 必须阻断；新 PR Flow 不提供绕过官方 Codex required check 的合并路径。
- 修复后的 review thread 只能由 `pr_flow resolve-threads` 或内部恢复命令显式 resolve，且必须显式传入 thread ID；不得猜测或批量 resolve 全部未处理 thread。官方 P2/P3 例外路径只能由 `pr_flow` 写入固定接受模板和 PR Evidence retained 后 resolve；官方 P0/P1 只有结构化 `fixed` / `false_positive` 证据且绑定当前 head/diff/thread ID 时才可自动关闭。
- 本地仓库必须设置 `git config core.hooksPath .githooks`。
- `.githooks/pre-commit`、`.githooks/pre-push`、`.githooks/reference-transaction` 必须通过 `.githooks/run-python.sh` 选择项目虚拟环境，不硬编码单一平台解释器。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push` 和 `scripts.research.governance verify full`，并保留 Git LFS pre-push 转交。
- `.githooks/pre-push` 必须阻断推送到 `main` / `master`；直写主干只在用户当前对话授权时允许，并要求 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`。
- `.githooks/reference-transaction` 必须阻断本地 `refs/heads/main` / `refs/heads/master` 被 merge、reset、delete 或 force rewrite；授权直写也只允许 fast-forward。
- PR 云端合并后，本地同步 `main` 必须设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并只允许 fast-forward 到 `origin/main`。
- PR 合并收尾必须删除已合并提交分支的本地引用；远端分支删除交给 GitHub 的 delete branch on merge。
- `pr-submit` 必须使用当前 head SHA 的 `--match-head-commit` auto-merge 授权；merged 后先 fetch，再走受控 fast-forward，同步后只删除本地已合并分支。
- `.gitignore` 禁止裸 `data/`、`data`、`**/data/`、`**/data` 等宽泛数据忽略模式；如需忽略仓库根数据目录，只允许使用 `/data/`。
- CODEOWNERS 必须覆盖关键路径。
- waiver 必须登记 `id`、`rule_id`、`path`、`reason`、`owner`、`approved_by`、`expires_at`、`migration_plan`；过期或字段不全必须阻断。
- 规则入口、Skill、README、workflow、registry、catalog、pathref 不能漂移。

## 关键路径

- `AGENTS.md`
- `CLAUDE.md`
- `docs/agents/**`
- `docs/rules/**`
- `docs/adr/**`
- `.agents/skills/**`
- `.codex/environments/**`
- `.claude/settings.json`
- `.claude/settings.local.json`
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

## Commit Intent Gate

- `commit intent hook`: `.githooks/pre-commit` 必须运行 `pr_flow intent pre-commit`，`.githooks/post-commit` 必须运行 `pr_flow intent post-commit`，并继续通过 `.githooks/run-python.sh` 使用项目 `.venv`。
- PR readiness 必须检查 branch intent coverage，发现 amend、squash、rebase 或 hook bypass 导致的 missing SHA 时停止。
- `PR Evidence JSON issues` 是 CI 可见审计面，必须覆盖 current head、PR commits、Issue roles 和 no-Issue minimum records；CI 不读取本地 `.local`。
- `no-Issue PR Evidence minimum` 在 PR body 只记录 `no_issue: true`；reason、authorized_by 和 evidence 按 commit 保留在 branch intent 中，不扩展 PR Evidence 契约。
