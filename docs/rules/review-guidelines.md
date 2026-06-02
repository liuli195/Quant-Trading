# PR Review 指南

入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；PR 流程见 [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。

本页保留 review 要求。日常不要手工复制 PR 证据；让 reviewer 直接产出契约化 fragment，再运行 `make pr-submit TITLE="<PR标题>"`，由 `scripts.research.governance.pr_flow` 更新 PR body 的 `pr-flow` 托管区。

## MUST

- 所有 PR 必须完成本地 AI review、问题评级和风险分级。
- 本地 AI review 必须记录至少两个独立 reviewer；有子 agent 能力时必须完成子 agent 交叉评审。无能力时记录原因和替代证据。
- 交叉评审必须记录 `superpowers:subagent-driven-development/spec-reviewer-prompt.md`、`superpowers:subagent-driven-development/code-quality-reviewer-prompt.md` 和 `reviewers: A, B`。
- Codex 本地安全 review 使用 `codex-security`；Claude 使用 `security-guidance`；结构化 fragment 记录安全结论，PR body 只保留 PR Evidence JSON。
- 本地 AI review 默认 `review_mode=complete`；`complete_review.iterations` 必须证明每个 reviewer 最后一轮 `no_new_findings=true` 且 `new_findings=[]`。
- `review_mode=partial` 只在用户显式授权时可用，并记录 `authorized_by`、`reason`、`evidence`。
- P0/P1 未以 `fixed` 或 `false_positive` 关闭前，不得进入下一阶段。
- `pr-submit` 对所有 PR 触发官方 Codex Code Review；高风险或 unknown PR 仍加 `ai-risk-review` label，用于标记风险和收窄 Review Scope，不作为是否触发官方 review 的开关。
- 官方 Codex Review 触发评论必须包含 `@codex review`、当前 PR、当前 head SHA、Review Scope（可为空）和审查重点；禁止模板外文案，禁止写“不要执行命令”“只做静态 diff review”等切断仓库、diff 或命令上下文的指令。
- 官方 Codex Review 按 Review Scope 聚焦 P0/P1 合并阻断风险；无法生成明确 scope 的大型 PR 应拆分，否则按全量高风险 PR 处理，但仍必须使用当前 head 的官方 review。
- 官方 Codex P2/P3 是非阻断 retained finding；`pr_flow` 只能写入 PR Evidence `retained`，不得扩展 PR body 机器字段。
- 自动写入不等于跳过 review；证据必须来自当前 PR、当前 head、当前 trigger 之后的 Codex 结果。
- `PR Flow / evidence` 和 `PR Flow / review-status` 必须读取 review thread 状态；未 resolved human thread、无 severity thread 和官方 P0/P1 阻断。官方 P2/P3 只能由 `pr_flow` 写入固定接受模板和 PR Evidence retained 后 resolve。
- `PR Flow / review-status` 是 GitHub `main` 全局 required status check；官方 Codex review 未返回时保持 pending，不写失败。`pr-submit` 开始和成功时 `status.json` 可留下 `failures: []`，它不是成功证明。
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

- PR body 托管区只写 fenced JSON，字段为 `schema/head/diff/reviews/issues/retained`，来源见 [pr-flow-interface-contract.yaml](pr-flow-interface-contract.yaml) <!-- pathref: docs/rules/pr-flow-interface-contract.yaml -->。
- `reviews` 只保存 Standards、Spec、Security 的通过指纹。
- `issues.commits` 覆盖每个 PR commit；每个 commit 要么有关联 Issue，要么明确 `no_issue`。
- `issues.refs` 记录 closes/reference 和 closes Issue 的 AC checked 状态。
- `retained` 只允许 P2/P3，来源只能是 standards/spec/security/official_codex。

## Issue Intent Review

- Standards reviewer 和 Spec reviewer 先并行运行；`Security-after-Standards/Spec` 是固定顺序，只有两者没有 open P0/P1 后才运行 Security reviewer。
- `Spec reviewer AC evidence` 不扩展 fragment 或 PR Evidence 字段；Spec reviewer 只判断每个 `closes` Issue 的 AC 是否满足，PR Evidence 仅记录 `issues.refs[].ac_checked`。
- `Standards/Security veto` 保留阻断权：Standards 可阻断规则、证据或流程问题；Security 可在第二阶段阻断安全问题。
- P2/P3 accepted findings 继续作为非阻断证据保留，不阻止 Security 或 AC auto-marking。
