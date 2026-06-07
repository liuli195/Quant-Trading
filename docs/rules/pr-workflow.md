# PR 工作流规则

Review 细则见 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->；门禁见 [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->；机器接口见 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml -->。

## 默认入口

- 高频 PR 流程只使用 `make pr-submit TITLE="<PR标题>"`，等价于 `.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow submit --title "<PR标题>"`。
- `pr-submit` 是前台有界自动流程：读取 `PR Flow Interface Contract`、检查 GitHub auto-merge / merge 后删远端分支 / required checks 配置、校验本地 review fragments、创建或更新 draft PR、刷新 PR Evidence JSON、ready-for-review、通过 local stable gate 后按风险/授权触发官方 Codex review、等待 required checks、head-locked auto-merge、等待 merged，并做本地收尾。
- 官方 Codex completion comment 触发的 `PR Flow / review-status` 由默认分支 router 自动 dispatch 到 PR head branch worker；`pr-submit` 不维护 PR Flow changed-files 白名单、不直接触发 `workflow_dispatch`、不新增公开 `diagnose`、`handoff` 或 `refresh` 入口。
- `pr-submit` 触发 `@codex review` 后，必须用 Codex bot 对该 trigger comment 的 `eyes` reaction 确认远端已接收；当前 head trigger 后若已出现 current-head Codex 输出，也视为触发成功。当前 head trigger 超过 3 分钟仍无 `eyes` 或 current-head 输出时，必须重新发送一次 `@codex review`。`eyes` 只代表接收确认，不代表 review 完成；`+1` reaction 不是 current-head verdict。
- pending 是等待状态，不是失败状态。需要官方 Codex review 但未返回、或 required checks 未完成时，`pr-submit` 继续等待；只有 P0/P1、unresolved thread、CI failure、配置缺失、官方 Codex 不可用或 10 分钟超时才写接手快照 v3 并退出。
- `.local/pr-flow/status.json` 是接手入口，不是成功证明。运行时只写接手快照 v3：`schema_version`、`snapshot_subject`、`pr_submit_stop`、`checkpoint_statuses`、`blocking_signals`、`diagnostic_signals`、`suggested_next_actions` 和 `evidence_artifacts`；合并权威仍是 GitHub required checks、conversation resolution、ruleset 和 merged state。
- `pr-cleanup`、`ready-for-review`、`merge`、`cleanup` 等旧底层能力只用于内部恢复或调试，不作为默认用户步骤；不得要求用户在多个 PR 入口间切换。
- cleanup 完成 base fetch、受控 fast-forward 和本地功能分支删除后，必须执行 `git status --porcelain=v2 --branch`。发现 dirty worktree 时停在 `EXCEPTION_REQUIRED`，`reason_code=WORKTREE_DIRTY_AFTER_CLEANUP`，`phase=cleanup_worktree_health`，raw status 写入 evidence artifact；cleanup 不自动恢复、不自动删除、不自动修复。

## 主干规则

- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权直写主干。
- “合并到主干”默认指创建、更新或准备 PR，不是本地合并 `main`。
- 禁止把功能分支本地合入 `main`；GitHub 合并后的本地同步只能走受控 fast-forward。
- 手工直写主干或手工同步 GitHub 合并后的本地 `main` 都必须走单次 wrapper：`branch_protection authorize-main --action direct-write --reason <reason> -- git <main-command>` 或先 `git fetch origin main`，再运行 `branch_protection authorize-main --action ref-sync --reason <reason> -- git merge --ff-only origin/main`。wrapper 只对子 Git 进程注入 `ALLOW_DIRECT_MAIN_WRITE` / `DIRECT_MAIN_WRITE_REASON` 或 `ALLOW_MAIN_REF_UPDATE` / `MAIN_REF_UPDATE_REASON`；禁止 reset、删除或 force rewrite。
- 本地工作分支默认只允许 fast-forward 更新。agent 不得默认使用 `commit --amend`、`rebase`、`squash` 或 `reset` 后重做提交；review finding 修复必须使用追加 commit。单次 history rewrite 例外只通过 repo-native wrapper 授权，不附带 review、intent 或 cleanup 后续恢复。
- PR 合并后远端分支删除交给 GitHub；本地收尾只删除已合并的本地功能分支，不本地删除远端分支。
- `main` 被其他 worktree 占用时，`pr-submit` 在 `main` 所在 worktree 执行受控 fast-forward；当前 worktree 只切到 detached `origin/main` 以便删除已合并的本地功能分支。
- `pr-submit` cleanup 内部可继续用一次性临时 env 执行受控 fast-forward，但不得要求用户设置会话级 `ALLOW_*`。

- 本地删除已合并功能分支使用 `git branch -d <branch>`；远端分支删除交给 GitHub。
## Review 和 Evidence

- 本地 review fragment 是 `pr-submit` 的输入，路径和字段以 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml --> 为准。
- review fragment 只绑定当前 `head` 和 `diff`；PR body、required status 或 update-branch 状态变化不会单独让 fragment 失效。只有 fragment 缺失、`head` 不匹配或 `diff` 不匹配时才要求重新 review。
- `pr-submit` 遇到 missing / stale local review fragments 时写 `.local/pr-flow/review-fragments-handoff.json`，列出 current head、diff、role、目标 fragment 路径和 agent-only builder 输入模板。标准动作是重新 review，然后用结构化 verdict payload 通过隐藏 builder 落 current fragment；不得从聊天总结推断 pass。
- push 时 `.githooks/pre-push` 会非阻断提醒 existing local review fragments 是否 stale；看到 stale diff 提醒后，主 agent 必须先重新 review / 重新映射 fragments，再运行 `pr-submit`。same diff 仅 head stale 时，`pr-submit` 可按现有规则刷新 fragment head。
- P0/P1 finding 必须在 fragment 中记录 `status=open|fixed|false_positive`；只有 `open` 阻断，`fixed` 必须带 current head/diff 下的 `evidence`，`false_positive` 必须带 `rationale`。stale fragment 中的 closed P0/P1 不能作为当前关闭证据。
- Standards / Spec fragment 必须记录 `delegation_attempt`：`required=true`、`authorization_basis="AGENTS.md + ADR 0009"`、`tool="spawn_agent"`、`result=spawned|tool_unavailable|spawn_failed`；`tool_unavailable` / `spawn_failed` 必须写具体 `reason`，且不得使用 `user_not_authorized`、`permission_not_allowed`、`explicit_authorization_missing`、`policy_disallowed` 这类授权缺失理由。
- security fragment 顶层必须记录 `security_review.tool`；未使用 `codex-security` 时必须记录 `security_review.fallback_reason`。
- Standards 和 Spec 同阶段完成后统一汇总 P0/P1；两者无 P0/P1 后才进入 Security。Security P0/P1 阻断，P2/P3 进入 retained findings。
- PR body 的 `pr-flow` 托管区只写 fenced PR Evidence JSON。CI 的 `PR Flow / evidence` 只信任 PR body，不读取本地 `.local`。
- Issue intent 并入 PR Evidence JSON 的 `issues`，不再单独维护 Issue intent machine block。每个 PR commit 要么有关联 Issue，要么明确 `no_issue: true`。
- GitHub update-branch 生成的同步主干 merge commit 由 `pr-submit` 自动按 commit 级 `no_issue: true` 覆盖；PR 级 `issues.refs` 仍只表达 closes/reference，不受该 synthetic merge commit 影响。
- 新功能分支首次运行 `pr-submit` 且当前非主干分支缺少远端 branch 时，`pr-submit` 可自动执行 `git push -u origin HEAD:<branch>`，并验证远端 head 等于当前 head 后继续创建或更新 PR；`main` / `master` 不自动 push。
- 手工排障先读 `.local/pr-flow/status.json`；旧 required-check failure 只能进入 `diagnostic_signals`，当前阻断只进入 `blocking_signals`；GitHub 当前状态归因由 `pr-submit` 内部处理，`diagnose` 不作为用户流程入口。
- official Codex P0/P1 thread 接手只读 `.local/pr-flow/resolve-threads-plan.json`，提供结构化 closure verdict payload，并用隐藏 builder upsert `.local/pr-flow/thread-closure-evidence.json`。builder 只处理 current head / current diff / plan 中的 unresolved official Codex P0/P1 thread，不自动 reply、不自动 resolve；推进仍由 `pr-submit` 完成。
- local stable gate 位于 PR Evidence sync / ready-for-review 之后、官方 Codex review trigger 之前，只等待 current head 的 `PR Flow / evidence` 和 `Research Governance / verify-full`。`PR Flow / review-status` 不参与 local stable gate，避免 official review 与 review-status 循环等待；pending 超时写 `reason_code=WAITING_LOCAL_STABILIZATION`、`phase=submit_local_stabilization`，不新增顶层 stop state，并落 `.local/pr-flow/local-stabilization.json` 记录 current head、last triggered head、superseded 和 next trigger condition。

## Commit Intent

- 提交顺序固定为 `git add` -> `pr_flow intent stage` -> `git commit`。先 stage 文件，再为当前 staged diff 记录 Issue 绑定或 no-Issue authorization，最后提交。
- 每个 commit 都需要新的 commit intent；pre-commit 会校验 pending intent 的 branch intent、staged diff fingerprint 和 consumed 状态。
- post-commit 会写入真实 commit SHA，并把 commit intent 合并到 branch intent；PR Evidence 使用 branch intent 校验 commit coverage。
- branch intent 是 PR Issue 绑定来源；PR body 只渲染和校验它，不从分支名、commit message、PR title 或 diff 推断 Issue。
