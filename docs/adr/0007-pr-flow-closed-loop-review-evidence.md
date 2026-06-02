# ADR 0007: PR 强闭环状态机与 Review Evidence 边界

## 状态

Accepted

## 背景

PR 风险分级评审流程见 [ADR 0006](0006-risk-tiered-pr-review.md) <!-- pathref: docs/adr/0006-risk-tiered-pr-review.md -->。实践中，PR #21/#22 和 PR #25/#26 复盘暴露出同一类问题：`pr_flow` 已能辅助准备、等待、合并和清理，但证据、review、required checks、GitHub review threads、merge policy 和 cleanup 仍经常退回人工判断。

典型问题包括：

- 本地 review evidence 与当前 `HEAD` / diff 不一致。
- scope 扩大后缺少自动补审。
- PR body 与当前 head 的官方 Codex evidence 不同步。
- GitHub checks 输出混杂旧失败和新成功。
- GitHub conversation resolution 按 unresolved thread 阻断，而仓库 severity 规则允许 P2/P3 不修复。
- GitHub API / GraphQL 瞬时错误会中断无问题路径。
- 多入口 PR 流程、远端 merge policy 和 cleanup 收尾仍有人工切换成本。

本 ADR 对应 PRD Issue：<https://github.com/liuli195/Quant-Trading/issues/27>。

## 决策

- 高频入口收敛为 `pr-submit`；它负责创建/更新 PR、刷新 PR Evidence JSON、等待 required checks、ready-for-review、head-locked auto-merge 和本地收尾。
- `.local/pr-flow/status.json` 是 `pr-submit` 到 AI 的本地接手入口。`pr-submit` 每次开始写当前 head 的空 `failures`，失败时覆盖为 failures，成功时可留下 `failures: []`；它不是成功证明，权威证据只来自当前 Git 状态、GitHub 状态和校验过的 PR Evidence JSON。
- review coverage 必须绑定当前 diff fingerprint。`base_sha`、`head_sha`、`diff_hash` 或文件集变化后，旧 evidence 失效；允许 delta review，但最终 evidence 必须证明覆盖当前完整 diff。
- `pr-submit is not a sub-agent dispatcher`: `pr-submit` 只校验 fragments 并在缺失时输出 `DISPATCH_REQUIRED`；主 agent 使用 `repo-pr-governance wrapper for $review` 调用 `$review` 默认审查，并把文本结论映射为 Standards / Spec fragments。Security review 仍单独必需，不能被 `$review` 替代。
- evidence builder 只读取结构化 fragments、security fragment、external findings、authorizations 和 diff facts；不得从聊天总结或自然语言结论中推断 review 通过。
- PR Evidence JSON v1 写入 current head、diff hash、review fingerprints、`official_review`、Issue intent 和 retained findings；过渡期可读旧 schema 缺失 `official_review` 时按 `required` 读取，新写出只写契约 v1 且必须包含 `official_review`。
- PR Evidence JSON 的 `issues.commits` 必须覆盖每个 PR commit；每个 commit 要么有关联 Issue，要么记录 `no_issue: true`。`issues.refs` 只保留 closes/reference 角色；GitHub Issue AC checkbox 仅作为人工记录，不参与 PR gate。
- `target scheme review authority`: `target spec wins`。当 PR 的目标 Issue/PRD 与旧仓库规则冲突时，Standards/Spec reviewer 以目标方案为裁判基准；旧规则冲突归类为 rule/ADR drift，不归类为实现违规；规则或 ADR 修改仍必须先获得用户显式授权。
- risk classifier 由 builder 最终裁决，review/security 只提供输入。官方 Codex Review 是否等待由 PR Evidence `official_review.decision` 决定：`required` 等待官方 review，`skip_risk_low` 跳过低风险官方 review，`skip_user_authorized` 表示用户显式授权跳过官方 review，且只记录 `authorized_by + evidence`。
- P2/P3 accepted findings 不影响 `risk_level`，也不阻断合并；所有来源的 P2/P3 统一写入 PR Evidence `retained`。
- 官方 Codex P2/P3 review thread 在 severity 可靠识别时，由 `pr_flow` 用固定模板自动接受、resolve、重新读取确认 resolved，并写入 PR Evidence `retained`。官方 Codex P0/P1 在缺少结构化 `fixed` / `false_positive` evidence 时阻断；有绑定当前 head/diff/thread ID 的证据时可由 `pr_flow` 自动回复并 resolve。无 severity thread 和人工 reviewer thread 不自动 resolve。
- 官方 Codex Review 状态由 `PR Flow / review-status` 复核；官方 Codex 未返回时 pending，不写失败。
- PR body 继续作为 CI 可见 evidence surface；CI 不读取 `.local`。CI 通过 PR body 和 GitHub API 校验 current head、PR Evidence JSON、thread 状态和 required checks。
- `pr_flow` 顶层停止状态保持三类：`DISPATCH_REQUIRED`、`REPLY_OR_FIX_REQUIRED`、`EXCEPTION_REQUIRED`。所有非 0 退出必须输出 `reason_code`、phase、retryable、dispatch target、blocking items、evidence refs 和 next actions。
- `pr_flow diagnose` 必须成为状态机观测面，能够复现停止原因，避免后续 agent 重新调查。
- cleanup 必须在确认 PR merged、本地 base 分支受控 fast-forward 后，才删除本地已合并 head branch；远端分支删除交给 GitHub。

## 后果

- PR 流程从“脚本辅助 + 人工判断”升级为强闭环状态机；确定性步骤自动推进，只在缺结构化输入、需要回复/修复或外部异常时停止。
- 本地缓存提高恢复能力，但不会成为 CI 或合并门禁的信任来源。
- `$review` 成为本地非安全 review 的统一入口；security review 继续独立存在。
- P2/P3 的仓库语义与 GitHub conversation resolution 规则统一：可以不修复，但必须结构化接受并 resolve thread。
- 官方 Codex Review 质量边界按风险/授权执行；大型 PR 通过 scope 收窄、delta review 和 evidence 复用提效，不能用未记录授权绕过 current-head 审查要求。
- `PR Flow / evidence`、`PR Flow / review-status`、PR body renderer、`pr_flow diagnose` 和 governance tests 必须同步升级，避免规则、文档和工具漂移。

## Issue Intent Extension

- `commit-scoped intent`: 每次提交前必须先 `git add`，再声明本次提交的 Issue 绑定或 no-Issue authorization；提交消息、分支名、PR 标题和 diff 内容都不是 intent 权威来源。
- `branch intent authority`: `.local/pr-flow/intents/<branch>.json` 聚合已消费的 commit intent，并作为 PR review evidence 的 `spec_ref` 权威来源；`closes` 优先于 `reference`，显式降级必须记录 correction reason。
- `no branch creation gate`: 创建分支不设门禁，门禁前移到每次提交和 PR readiness/CI 覆盖校验。
- `PR Evidence JSON issues`: PR body 托管 JSON 保留 current head、commit coverage、Issue roles 和 `no_issue: true` 最小记录；no-Issue 的 reason、authorized_by 和 evidence 保留在 branch intent 中，不扩展 PR Evidence 契约。
- `two-stage review`: Standards reviewer 与 Spec reviewer 先并行完成；没有 open P0/P1 后，Security reviewer 再运行。
- `no AC auto-marking`: PR Flow 不自动勾选 GitHub Issue AC checkbox，也不要求额外 AC 确认；Spec reviewer 按目标方案整体判断实现是否满足需求。
