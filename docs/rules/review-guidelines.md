# PR Review 指南

入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；PR 流程见 [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。

本页保留 evidence schema 和 review 要求。日常不要手工复制整段 PR 证据；先让 Skills / agents 产出 `.local/ai-review/latest.json`，再运行 `make pr-ready TITLE="<PR标题>"`，由 `scripts.research.governance.pr_flow` 渲染 `.local/ai-review/pr-body.md` 并更新 PR body 的 `pr-flow` 托管区。

## MUST

- 所有 PR 必须完成本地 AI review、问题评级和风险分级。
- 本地 AI review 必须记录至少两个独立 reviewer；有子 agent 能力时必须完成子 agent 交叉评审。无能力时记录原因和替代证据。
- 交叉评审必须记录 `superpowers:subagent-driven-development/spec-reviewer-prompt.md`、`superpowers:subagent-driven-development/code-quality-reviewer-prompt.md` 和 `reviewers: A, B`。
- Codex 本地安全 review 使用 `codex-security`；Claude 使用 `security-guidance`；报告字段为 `security_review`，PR body 字段为 `本地安全 review`。
- 本地 AI review 默认 `review_mode=complete`；`complete_review.iterations` 必须证明每个 reviewer 最后一轮 `no_new_findings=true` 且 `new_findings=[]`。
- `review_mode=partial` 只在用户显式授权时可用，并记录 `authorized_by`、`reason`、`evidence`。
- P0/P1 未以 `fixed` 或 `false_positive` 关闭前，不得进入下一阶段。
- 高风险或 unknown PR 必须加 `ai-risk-review` label，并触发官方 Codex Code Review；用户显式授权跳过时，PR body 必须记录 `官方 Codex Review 跳过授权`。
- 官方 Codex Review 触发评论必须包含 `@codex review`、当前 PR、当前 head SHA、Review Scope（可为空）和审查重点；禁止模板外文案，禁止写“不要执行命令”“只做静态 diff review”等切断仓库、diff 或命令上下文的指令。
- 官方 Codex Review 按 Review Scope 聚焦 P0/P1 合并阻断风险；无法生成明确 scope 的大型 PR 应拆分，否则按全量高风险 PR 处理。
- 官方 Codex Review 无 P0/P1 且匹配当前 head 时，`pr_flow` 可以自动把真实 review/comment 链接写入 PR body evidence。
- 自动写入不等于跳过 review；证据必须来自当前 PR、当前 head、当前 trigger 之后的 Codex 结果。
- `pr-review-evidence` 和 `Codex Review Monitor` 必须读取 review thread 状态；只要 GitHub conversation resolution ruleset 要求 resolved conversation，任何未 resolved 的 review thread 都阻断，跳过授权不得绕过。
- `Codex Review Monitor` 是 GitHub `main` 全局 required status check；低风险且无需官方 Codex Review 的 PR 允许快速通过/空跑，但不替代 PR body 证据。
- 如果 Codex review 无法读取当前 PR diff、要求额外提供 unified diff、引用不存在或非当前 head，按 review 上下文失效阻断。
- 必须保留本地检查证据，至少包括 `.\.venv\Scripts\python.exe -m scripts.research.governance verify full`；`verify fast` 不能作为 PR 证据。

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

## PR 证据格式

```markdown
## AI Review 风险分级

- 风险等级: low / high / unknown
- 是否需要官方 Codex Review: 是 / 否（低风险无需 / 用户授权跳过）
- high/unknown PR label: `ai-risk-review` / 不适用
- 官方 Codex Review 跳过授权: 无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex / claude；tool=codex-security / security-guidance；evidence=<安全 review 证据>
- 本地 AI review 模式: complete / partial
- 不完全 Review 模式授权: 无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>
- 子 agent 交叉评审: `superpowers:subagent-driven-development/spec-reviewer-prompt.md` + `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`；reviewers: <规格评审子agent>, <代码质量评审子agent>；见 `.local/ai-review/latest.md`
- 任务分发说明: 已分发任务 / 未分发原因
- Codex Review Scope: `.local/ai-review/codex-review-scope.md`
- P0/P1 未关闭项: 无

## P2 保留项

- 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review`
- 结论: 通过 / 未要求 / 未执行
- 阻断问题: 无
- 关键证据:
  - Codex review 链接：https://github.com/<owner>/<repo>/pull/<number>#pullrequestreview-<id>
  - `.\.venv\Scripts\python.exe -m scripts.research.governance verify full`
```
