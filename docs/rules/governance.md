# 治理门禁规则

## MUST

- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。
- `scripts.research.governance gate` 保留强门禁语义；`scripts.research.governance verify` 负责编排 affected fast、explain 和 full。
- 日常小改默认使用 `scripts.research.governance verify fast`，只表示可继续开发，不作为 PR 或合并证据。
- PR 提交不把本地 `verify full` 作为前置证据；`.githooks/pre-push` 不运行本地 `verify full`，只做主干保护、local review fragments freshness 非阻断提醒和 Git LFS 转交；CI 和最终合并证据以 GitHub required check `Research Governance / verify-full` 为准。
- `.githooks/pre-commit` 使用 `scripts.research.governance verify fast --staged`。
- CI 必须覆盖完整治理审计和 pathref gate，不得使用 fast；pre-push 不提供本地 full verification。
- `scripts.research.governance.pr_flow` 是本地 PR 自动化入口；高频 PR 流程只推荐 `make pr-submit TITLE="<PR标题>"`，它按 [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md --> 和 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml --> 推进到 GitHub auto-merge 和本地收尾。
- GitHub `main` 必须启用 branch protection 或 ruleset：Require pull request、Require status checks、Require conversation resolution、Block force pushes；approval / Code Owner review 是否阻断以远端实际 ruleset / branch protection 为准，`pr_flow` 不得本地硬编码。
- required checks 必须与 `PR Flow Interface Contract` 完全一致：`PR Flow / review-status`、`Research Governance / verify-full`、`PR Flow / evidence`。
- `Research Governance / verify-full` 通过 `verify full` 汇总静态扫描、类型检查、依赖漏洞扫描、测试、pathref 和 governance gate。
- `verify-full` 是 head/diff 级别检查，只由 `main` push、PR head 变化、schedule 和 manual dispatch 触发；不监听 review、thread、label 或 `ready_for_review` 事件。
- `PR Flow / evidence` 只校验 PR body 托管区中的 PR Evidence JSON v2；CI 不读取本地 `.local` 产物。
- `PR Flow / evidence` 保留 PR body `edited` 触发，并只监听 `opened`、`synchronize`、`reopened`、`edited`。
- 需要官方 Codex review 时，`pr-submit` 必须先通过 local stable gate；该 gate 只等待 current head 的 `Research Governance / verify-full` 和 `PR Flow / evidence`，明确排除 `PR Flow / review-status`。pending 超时使用 `WAITING_LOCAL_STABILIZATION` reason_code 和 `submit_local_stabilization` phase，不新增顶层 stop state，并在 `.local/pr-flow/local-stabilization.json` 留下 current head、last triggered head、superseded 和 next trigger condition。
- `PR Flow / review-status` 监听当前 head 的官方 Codex review、PR Evidence `official_review.decision` 和 unresolved threads。`official_review.decision=required` 且官方 Codex review 未返回时保持 pending；官方 P0/P1、无 severity thread 和 unresolved human thread 阻断；官方 P2/P3 由 `pr_flow` 接受、resolve、重新读取确认 resolved，并写入 PR Evidence `retained`。`skip_risk_low` 或 `skip_user_authorized` 时，该 check 可写 skipped success；用户授权只记录 `authorized_by + evidence`。
- `ai-risk-review` label 不参与 `skip_risk_low` 校验、required-check 触发或 current-head verdict，只作为人工可见风险标记。
- `PR Flow / review-status` 保留 review/thread/workflow_dispatch 触发；PR branch worker 的 `pull_request` 触发只覆盖 `opened`、`synchronize`、`reopened`。
- required-check workflows 使用 PR-scoped concurrency，同一 workflow、同一 PR/head 只保留最新 run，不跨 workflow 互相取消。
- 不新增 live PR state guard；如果 closed/merged 后仍污染 required check，优先继续收敛事件触发面。
- `issue_comment` 只能由默认分支 `codex-review-router.yml` 处理：router 识别 review 相关 PR 评论、写 `PR Flow / review-status` pending、用 PR head branch dispatch `codex-review-monitor.yml` worker；router dispatch 成功后不得写 success。
- `codex-review-monitor.yml` 是 PR branch worker，不得监听 `issue_comment`，必须保留 `pull_request`、`pull_request_review`、`pull_request_review_comment` 和 `workflow_dispatch` 入口；`workflow_dispatch` 必须接收 `pr_number`、`expected_head_sha`、`trigger_event`、`trigger_run_id`。
- `PR Flow / review-status` worker 发布 pending 后必须有 failure finalizer；`workflow_dispatch` 同样必须覆盖 pending 和 finalizer。checkout、setup 或依赖安装失败时必须把 required status 写成 failure/error，不得永久停在 pending。
- `expected_head_sha` 与 PR 当前 head 不一致时，worker 必须写 `error`，description 为 `PR head changed before monitor completed`，并停止 checkout、install 和 monitor，不得让旧 run 覆盖新 head verdict。
- 只要 GitHub conversation resolution ruleset 要求 resolved conversation，未 resolved 的 review thread 必须阻断；风险/授权跳过只影响是否等待官方 Codex review，不绕过其它 required checks。
- 修复后的 review thread 只能由 `pr_flow resolve-threads` 或内部恢复命令显式 resolve，且必须显式传入 thread ID；不得猜测或批量 resolve 全部未处理 thread。官方 P2/P3 例外路径只能由 `pr_flow` 写入固定接受模板和 PR Evidence retained 后 resolve 并重新读取确认；官方 P0/P1 只有结构化 `fixed` / `false_positive` 证据且绑定当前 head/diff/thread ID 时才可自动关闭，reply/resolve 后也必须重新读取确认 resolved。
- 本地 review fragments 和 official Codex P0/P1 closure evidence 的 agent-only builder 都只接受结构化 JSON payload；失败不得写半成品 evidence。pre-push freshness 仍只提醒，不写 handoff、不生成、不刷新、不修改 fragments。
- 本地仓库必须设置 `git config core.hooksPath .githooks`，普通 worktree 和 linked worktree 都必须检查。
- `.githooks/pre-commit`、`.githooks/pre-push`、`.githooks/reference-transaction` 必须通过 `.githooks/run-python.sh` 选择项目虚拟环境，不硬编码单一平台解释器。
- `.githooks/pre-push` 必须调用 `scripts.research.governance.branch_protection pre-push` 和 `scripts.research.governance.pr_flow pre-push-review-fragments`，并保留 Git LFS pre-push 转交；该 freshness 提醒不生成、不刷新、不修改 review fragments，也不阻断 push。
- `.githooks/pre-push` 必须阻断推送到 `main` / `master`；直写主干只在用户当前对话授权时允许，并通过 `branch_protection authorize-main --action direct-write --reason <reason> -- git <main-command>` 对单个 Git 子进程注入 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`。
- `.githooks/reference-transaction` 必须阻断本地 `refs/heads/main` / `refs/heads/master` 被 merge、reset、delete 或 force rewrite；授权直写也只允许 fast-forward。
- `.githooks/reference-transaction` 必须阻断本地 `refs/heads/*` 的 non-fast-forward 更新；新建和删除本地分支允许。agent 不得默认使用 `commit --amend`、`rebase`、`squash`、`reset` 后重做提交等 history rewrite；review finding 修复必须使用追加 commit。单次例外只能通过 repo-native wrapper 注入 `ALLOW_BRANCH_HISTORY_REWRITE=1` 和 `BRANCH_HISTORY_REWRITE_REASON=<reason>`，wrapper 不负责 review、intent 或 cleanup 后续恢复。决策见 [ADR 0010](../adr/0010-local-branch-history-rewrite-gate.md) <!-- pathref: docs/adr/0010-local-branch-history-rewrite-gate.md -->。
- PR 云端合并后，手工同步本地 `main` 必须通过 `branch_protection authorize-main --action ref-sync --reason <reason> -- git merge --ff-only origin/main` 对单个 Git 子进程注入 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并只允许 fast-forward 到 `origin/main`；`pr-submit` cleanup 内部可继续使用一次性临时 env，语义仍必须是受控 fast-forward。
- PR 合并收尾必须删除已合并提交分支的本地引用；远端分支删除交给 GitHub 的 delete branch on merge。
- `pr-submit` 必须使用当前 head SHA 的 `--match-head-commit` auto-merge 授权；merged 后先 fetch，再走受控 fast-forward，同步后只删除本地已合并分支。
- `pr-submit` 在新功能分支首次缺少远端 branch 时，可自动执行 `git push -u origin HEAD:<branch>` 并验证远端 head；该自动 push 禁止用于 `main` / `master`。
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
- `.claude/skills`
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
- PR readiness 必须检查 branch intent coverage，发现 amend、squash、rebase、reset 或 hook bypass 导致的 missing SHA 时停止；这些状态说明 history rewrite 围墙已被绕过或出现外部状态污染，不得把 stale branch intent 自动当成正常路径兼容。
- `PR Evidence JSON issues` 是 CI 可见审计面，必须覆盖 current head、PR commits、Issue roles 和 no-Issue minimum records；CI 不读取本地 `.local`。
- `no-Issue PR Evidence minimum` 在 PR body 只记录 `no_issue: true`；reason、authorized_by 和 evidence 按 commit 保留在 branch intent 中，不扩展 PR Evidence 契约。
