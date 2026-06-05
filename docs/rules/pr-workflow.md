# PR 工作流规则

Review 细则见 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->；门禁见 [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->；机器接口见 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml -->。

## 默认入口

- 高频 PR 流程只使用 `make pr-submit TITLE="<PR标题>"`，等价于 `.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow submit --title "<PR标题>"`。
- `pr-submit` 是前台有界自动流程：读取 `PR Flow Interface Contract`、检查 GitHub auto-merge / merge 后删远端分支 / required checks 配置、校验本地 review fragments、创建或更新 draft PR、刷新 PR Evidence JSON、按风险/授权判断是否触发官方 Codex review、等待 required checks、ready-for-review、head-locked auto-merge、等待 merged，并做本地收尾。
- 官方 Codex completion comment 触发的 `PR Flow / review-status` 由默认分支 router 自动 dispatch 到 PR head branch worker；`pr-submit` 不维护 PR Flow changed-files 白名单、不直接触发 `workflow_dispatch`、不新增公开 `diagnose`、`handoff` 或 `refresh` 入口。
- pending 是等待状态，不是失败状态。需要官方 Codex review 但未返回、或 required checks 未完成时，`pr-submit` 继续等待；只有 P0/P1、unresolved thread、CI failure、配置缺失、官方 Codex 不可用或 30 分钟超时才写接手快照 v3 并退出。
- `.local/pr-flow/status.json` 是接手入口，不是成功证明。运行时只写接手快照 v3：`schema_version`、`snapshot_subject`、`pr_submit_stop`、`checkpoint_statuses`、`blocking_signals`、`diagnostic_signals`、`suggested_next_actions` 和 `evidence_artifacts`；合并权威仍是 GitHub required checks、conversation resolution、ruleset 和 merged state。
- `pr-cleanup`、`ready-for-review`、`merge`、`cleanup` 等旧底层能力只用于内部恢复或调试，不作为默认用户步骤；不得要求用户在多个 PR 入口间切换。

## 主干规则

- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权直写主干。
- “合并到主干”默认指创建、更新或准备 PR，不是本地合并 `main`。
- 禁止把功能分支本地合入 `main`；GitHub 合并后的本地同步只能走受控 fast-forward。
- 直写主干或 GitHub 合并后的本地 `main` 同步都必须走受控 fast-forward；前者设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`，后者先 `git fetch origin main`，再设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并用 `git merge --ff-only origin/main` 或等价 fast-forward 同步；禁止 reset、删除或 force rewrite。
- PR 合并后远端分支删除交给 GitHub；本地收尾只删除已合并的本地功能分支，不本地删除远端分支。
- `main` 被其他 worktree 占用时，`pr-submit` 在 `main` 所在 worktree 执行受控 fast-forward；当前 worktree 只切到 detached `origin/main` 以便删除已合并的本地功能分支。

- 本地删除已合并功能分支使用 `git branch -d <branch>`；远端分支删除交给 GitHub。
## Review 和 Evidence

- 本地 review fragment 是 `pr-submit` 的输入，路径和字段以 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml --> 为准。
- review fragment 只绑定当前 `head` 和 `diff`；PR body、required status 或 update-branch 状态变化不会单独让 fragment 失效。只有 fragment 缺失、`head` 不匹配或 `diff` 不匹配时才要求重新 review。
- Standards 和 Spec 同阶段完成后统一汇总 P0/P1；两者无 P0/P1 后才进入 Security。Security P0/P1 阻断，P2/P3 进入 retained findings。
- PR body 的 `pr-flow` 托管区只写 fenced PR Evidence JSON。CI 的 `PR Flow / evidence` 只信任 PR body，不读取本地 `.local`。
- Issue intent 并入 PR Evidence JSON 的 `issues`，不再单独维护 Issue intent machine block。每个 PR commit 要么有关联 Issue，要么明确 `no_issue: true`。
- GitHub update-branch 生成的同步主干 merge commit 由 `pr-submit` 自动按 commit 级 `no_issue: true` 覆盖；PR 级 `issues.refs` 仍只表达 closes/reference，不受该 synthetic merge commit 影响。
- 手工排障先读 `.local/pr-flow/status.json`；旧 required-check failure 只能进入 `diagnostic_signals`，当前阻断只进入 `blocking_signals`；GitHub 当前状态归因由 `pr-submit` 内部处理，`diagnose` 不作为用户流程入口。

## Commit Intent

- 提交顺序固定为 `git add` -> `pr_flow intent stage` -> `git commit`。先 stage 文件，再为当前 staged diff 记录 Issue 绑定或 no-Issue authorization，最后提交。
- 每个 commit 都需要新的 commit intent；pre-commit 会校验 pending intent 的 branch intent、staged diff fingerprint 和 consumed 状态。
- post-commit 会写入真实 commit SHA，并把 commit intent 合并到 branch intent；PR Evidence 使用 branch intent 校验 commit coverage。
- branch intent 是 PR Issue 绑定来源；PR body 只渲染和校验它，不从分支名、commit message、PR title 或 diff 推断 Issue。
