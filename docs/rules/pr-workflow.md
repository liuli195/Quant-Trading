# PR 工作流规则

Review 细则见 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->；门禁见 [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->。

## 默认入口

- 一键准备、ready、合并和清理用 `make pr-complete TITLE="<PR标题>"`，等价于 `.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow complete --title "<PR标题>"`。
- 日常用 `make pr-ready TITLE="<PR标题>"`，等价于 `.\.venv\Scripts\python.exe -m scripts.research.governance.pr_flow ready --title "<PR标题>"`。
- `pr-ready` / `pr_flow ready` 是强闭环状态机，只推进到 `merge-ready`，永不合并。阶段顺序是 preflight、freeze diff、local review、security review、build evidence、official Codex、threads、sync PR body、wait latest checks；本地诊断缓存写入 `.local/pr-flow/state.json`。
- `pr-complete` / `pr_flow complete` 在 `pr-ready` 到达 `merge-ready` 后继续执行 `ready-for-review`、head-locked `merge` 和 `cleanup`；任何 pending/failing checks、未 resolved thread、Codex P0/P1、head 变化、GitHub/API/权限异常都会停止。
- 停止状态只有三类：`DISPATCH_REQUIRED` 表示缺结构化输入或需分发 review/security 任务；`REPLY_OR_FIX_REQUIRED` 表示需要作者修复或回复 review；`EXCEPTION_REQUIRED` 表示 GitHub、权限、检查、策略或本地环境异常。停止时必须写 `.local/pr-flow/last-status.json`，包含 reason_code、phase、retryable、dispatch target、blocking items、evidence refs 和 next actions。
- 修复 Codex review thread 后，agent 可把对应 thread ID 传给 `pr-ready` / `pr-complete` 的 `--resolve-thread <thread-id>`；`pr_flow` 只 resolve 显式传入的 thread。官方 Codex P2/P3 thread 在 severity 可靠识别时由 `pr_flow` 用固定模板接受、resolve 并写入 `external_findings` / PR body P2 保留项；官方 P0/P1、无 severity thread 和人工 reviewer thread 阻断。官方 P0/P1 只有已有结构化 `fixed` / `false_positive` 证据且绑定当前 head/diff/thread ID 时才自动关闭。
- `pr_flow sync` 创建 PR 前必须确认当前分支已推送到 `origin`；缺远端 head 时输出 `PUSH_REQUIRED`，由操作者先执行对应 push。
- Skills / agents 负责 review 判断和结论；`pr_flow` 只同步结构化证据，不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review；缺本地 review evidence 时必须停止并进入任务分发。
- Git hooks 只守本地不变量：pre-commit 走快速治理门禁，pre-push 和 CI 走完整治理门禁。

## 主干规则

- 所有进入主干的改动必须通过 PR，除非用户在当前对话中显式授权直写主干。
- “合并到主干”默认指创建、更新或准备 PR，不是本地合并 `main`。
- 禁止把功能分支本地合入 `main`；GitHub 合并后的本地同步只能走受控 fast-forward。
- 直写主干或 GitHub 合并后的本地 `main` 同步都必须走受控 fast-forward；前者设置 `ALLOW_DIRECT_MAIN_WRITE=1` 和 `DIRECT_MAIN_WRITE_REASON=<reason>`，后者先 `git fetch origin main`，再设置 `ALLOW_MAIN_REF_UPDATE=1` 和 `MAIN_REF_UPDATE_REASON=<reason>`，并用 `git merge --ff-only origin/main` 或等价 fast-forward 同步；禁止 reset、删除或 force rewrite。
- PR 合并授权包含删除已合并提交分支；清理前确认不在该分支，再执行 `git branch -d <branch>` 和 `git push origin --delete <branch>`。远端已自动删除时确认不存在；不得 force delete 掩盖未合并分支。

## Review 和等待

- Review 按 [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> 执行。
- `pr-ready` / `pr_flow ready` 负责按 Review 规则推进无问题路径；`pr-complete` / `pr_flow complete` 负责在 merge-ready 后继续合并和收尾。只有异常处理、任务分发、问题回复三类情况需要人工或 agents 介入。手工排障先用 `scripts.research.governance.pr_flow diagnose --pr <PR号>` 汇总 head、PR body evidence、merge state、latest required checks、Codex trigger/completion 和 review threads；需要盯 CI 时再单独使用 `gh pr checks <PR号或URL> --required --watch --interval 10` 或 `scripts.research.governance.codex_review_monitor`。
- 本地 review evidence 使用 schema v4：`diff_fingerprint` 绑定当前 diff，`review_fragments.standards/spec` 来自 review wrapper，`review_fragments.security` 来自独立 security review，`current_commit_evidence` 绑定当前 head，`external_findings` 记录官方 Codex thread 等外部发现，`spec_ref`/`issue_refs` 记录关联 Issue。`sync_pr_body` 会写入 `Closes #N` 并检查关联 Issue AC checkbox 已全部勾选。risk classifier 只根据结构化 evidence、阻断项和授权裁决 risk level；P2/P3 accepted 不触发官方 Codex Review。

## Commit Intent

- 提交顺序固定为 `git add` -> `pr_flow intent stage` -> `git commit`。先 stage 文件，再为当前 staged diff 记录 Issue 绑定或 no-Issue authorization，最后提交。
- 每个 commit 都需要新的 commit intent；pre-commit 会校验 pending intent 的 branch intent、staged diff fingerprint 和 consumed 状态。
- post-commit 会写入真实 commit SHA，并把 commit intent 合并到 branch intent；PR readiness 使用 branch intent 校验 rewrite 后的 commit coverage。
- branch intent 是 PR Issue 绑定来源；PR body 只渲染和校验它，不从分支名、commit message、PR title 或 diff 推断 Issue。
