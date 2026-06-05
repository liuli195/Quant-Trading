# PR Review 指南

入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；PR 流程见 [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。

本页保留 review 要求。日常不要手工复制 PR 证据；让 reviewer 直接产出契约化 fragment，再运行 `make pr-submit TITLE="<PR标题>"`，由 `scripts.research.governance.pr_flow` 更新 PR body 的 `pr-flow` 托管区。

## MUST

- `target方案优先`: 当 PR/Issue/PRD 明确目标方案时，Standards/Spec reviewer 必须以目标方案为裁判基准；旧仓库规则与目标方案冲突时，finding 归类为规则/ADR drift，不得归类为实现违反旧规则。
- 所有 PR 必须完成本地 AI review、问题评级和风险分级。
- 本地 AI review 必须记录至少两个独立 reviewer；有子 agent 能力时必须完成子 agent 交叉评审。无能力时记录原因和替代证据。
- 交叉评审必须记录 `superpowers:subagent-driven-development/spec-reviewer-prompt.md`、`superpowers:subagent-driven-development/code-quality-reviewer-prompt.md` 和 `reviewers: A, B`。
- Codex 本地安全 review 使用 `codex-security`；Claude 使用 `security-guidance`；结构化 fragment 记录安全结论，PR body 只保留 PR Evidence JSON。
- 本地 AI review 默认 `review_mode=complete`；`complete_review.iterations` 必须证明每个 reviewer 最后一轮 `no_new_findings=true` 且 `new_findings=[]`。
- `review_mode=partial` 只在用户显式授权时可用，并记录 `authorized_by`、`reason`、`evidence`。
- P0/P1 未以 `fixed` 或 `false_positive` 关闭前，不得进入下一阶段。
- `target spec wins`: 当目标 Issue/PRD/spec 与旧规则或 ADR 冲突时，review finding 应归类为 `rule/ADR drift`；规则或 ADR 修改仍必须先获得用户显式授权。
- 官方 Codex Code Review 是否等待只看 PR Evidence `official_review.decision`：`required` 等待官方 review，`skip_risk_low` 跳过低风险官方 review，`skip_user_authorized` 表示用户显式授权跳过官方 review。
- `skip_user_authorized` 只记录 `authorized_by + evidence`，不记录 `reason`；该授权不能绕过 unresolved thread、P0/P1 或 GitHub required checks 的其它阻断。
- 官方 Codex Review 触发评论必须包含 `@codex review`、当前 PR、当前 head SHA、Review Scope（可为空）和审查重点；禁止模板外文案，禁止写“不要执行命令”“只做静态 diff review”等切断仓库、diff 或命令上下文的指令。
- 触发评论必须在 3 分钟内出现 Codex bot 的 `eyes` reaction 才算远端已接收；超过 3 分钟无 `eyes` 时，`pr-submit` 必须重新触发一次 `@codex review`。Codex bot 的 `+1` reaction 不是 current-head verdict，不能替代 `eyes`、Codex no-issue comment 或当前 head PR review。
- 官方 Codex 通过判定使用 current-head verdict：latest current-head trigger 后的 Codex no-issue comment，或当前 head 的 Codex PR review，才能作为当前 head 证据；旧 head verdict 不得复用。
- `pr-submit` 等待 `eyes` 或 current-head Codex 输出；已有 current-head 输出时，不因缺少 `eyes` 重发触发评论。
- P2/P3 only + all threads resolved 可以通过 review-status；任意 unresolved review thread、P0/P1 或 context invalid 仍阻断。
- 需要官方 Codex Review 时，Review Scope 聚焦 P0/P1 合并阻断风险；无法生成明确 scope 的大型 PR 应拆分，否则按全量高风险 PR 处理。
- 官方 Codex P2/P3 是非阻断 retained finding；`pr_flow` 只能写入 PR Evidence `retained`，不得扩展 PR body 机器字段。
- 自动写入不等于跳过 review；需要官方 Codex Review 时，证据必须来自当前 PR、当前 head、当前 trigger 之后的 Codex 结果。
- `PR Flow / evidence` 和 `PR Flow / review-status` 必须读取 review thread 状态；未 resolved human thread、无 severity thread 和官方 P0/P1 阻断。官方 P2/P3 只能由 `pr_flow` 写入固定接受模板和 PR Evidence retained 后 resolve。
- `PR Flow / review-status` 是 GitHub `main` 全局 required status check；官方 Codex review 未返回时保持 pending，不写失败。`status.json` 是接手快照 v3，不保留旧 `schema/head/failures` 字段，也不是成功证明。
- 如果 Codex review 无法读取当前 PR diff、要求额外提供 unified diff、引用不存在或非当前 head，按 review 上下文失效阻断。
- 本地不再把 `verify full` 作为 PR 前置证据；完整验证由 GitHub required check `Research Governance / verify-full` 执行。`verify fast` 只用于日常开发。

## 评级

- `P0`：严重错误交易、密钥泄露、主干保护绕过、明确安全漏洞。阻塞。
- `P1`：高概率 bug、回归、治理门禁失效、关键测试缺失。阻塞。
- `P2`：中等风险，可保留，但必须写不修原因、风险接受理由和处理方式。
- `P3`：风格、可读性、小优化，不阻塞。

## 官方 Codex Review 触发评论

```markdown
@codex review

PR：https://github.com/<owner>/<repo>/pull/<number>
HEAD：<full-head-sha>
Review Scope：
- <path-or-scope-entry>

审查重点：仅 P0/P1 合并阻断风险
```

## 评审重点

- 代码：bug、未来函数、边界条件、参数不一致、回归风险。
- 聚宽：本地不可完整复现交易环境，不得把本地结果写成云端实盘结论。
- 治理：规则入口、CODEOWNERS、workflow、registry、catalog、waiver、pathref 是否漂移。
- 测试：相关单测、语法检查、governance gate、策略或研究工具回归是否缺失。
- 报告：结论必须追溯 source table、manifest、audit log、run artifact。

## 规则关注点

- [index.md](index.md) <!-- pathref: docs/rules/index.md -->
- [commands.md](commands.md) <!-- pathref: docs/rules/commands.md -->
- [environments.md](environments.md) <!-- pathref: docs/rules/environments.md -->
- [code-style.md](code-style.md) <!-- pathref: docs/rules/code-style.md -->
- [research-workflow.md](research-workflow.md) <!-- pathref: docs/rules/research-workflow.md -->
- [docs-and-pathref.md](docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->
- [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->
- [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->
- [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->

## PR Evidence JSON

- PR body 托管区只写 fenced PR Evidence JSON v2，字段为 `schema/head/diff/reviews/official_review/issues/retained`，来源见 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml -->。
- `reviews` 只保存 Standards、Spec、Security 的通过指纹。
- `official_review.decision` 只允许 `required`、`skip_risk_low`、`skip_user_authorized`；PR Evidence 只接受 `schema=2`，缺失 `official_review` 直接无效。
- `issues.commits` 覆盖每个 PR commit；每个 commit 要么有关联 Issue，要么明确 `no_issue`。
- `issues.refs` 仅记录 closes/reference 角色；GitHub Issue AC checkbox 仅作为人工记录，不参与 PR gate。
- `retained` 只允许 P2/P3，来源只能是 standards/spec/security/official_codex。

## Local Review Wrapper

- `repo-pr-governance wrapper for $review`: 主 agent 用本技能作为轻量包装器，不修改 `$review` 技能，不复制完整提示词，不让 `pr-submit` 派发子 agent。
- `pr-submit` 只校验结构化 fragments；缺失时输出 `DISPATCH_REQUIRED`。主 agent 派发 `$review`，并把 `$review` 文本结论映射为 standards/spec fragments；Security review 独立生成 security fragment。
- 有 Issue refs 时，只在 `$review` 默认逻辑基础上补充 spec hint：`closes` 是主规格，`reference` 是背景。无 Issue refs 或 no-Issue 时，完全走 `$review` 默认逻辑。

## Issue Intent Review

- Standards reviewer 和 Spec reviewer 先并行运行；`Security-after-Standards/Spec` 是固定顺序，只有两者没有 open P0/P1 后才运行 Security reviewer。
- Spec reviewer 按目标方案整体判断实现是否满足需求，不额外输出逐项 AC 确认；PR Evidence 不记录 AC 确认字段。
- `Standards/Security veto` 保留阻断权：Standards 可阻断规则、证据或流程问题；Security 可在第二阶段阻断安全问题。
- P2/P3 accepted findings 继续作为非阻断证据保留，不阻止 Security 后续流程。
