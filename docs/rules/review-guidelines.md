# PR Review 指南

本文件是仓库级 PR review 规则。AI 助手通用入口是 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；[CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 只保留 Claude Code 专属指针。

## MUST

- 所有 PR 必须完成本地 AI review、问题评级和风险分级。
- 本地 AI review 必须由至少两个独立 reviewer 完成子 agent 交叉评审，并在统一报告 schema 的 `reviewers` 字段中记录；评审子 agent 必须使用 Superpowers 模板 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` 和 `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`。
- 本地 AI review 默认使用 `complete` 完全 review 模式；两个 reviewer 必须持续查找更多发现，直到各自最后一轮明确记录无新发现。
- 只有用户显式授权时，本地 AI review 才能使用 `partial` 不完全模式；必须记录 `authorized_by`、`reason` 和 `evidence`。
- P0/P1 问题未以 `fixed` 或 `false_positive` 关闭前，不得进入下一阶段。
- 高风险或 unknown PR 默认必须执行官方 Codex Code Review，并由 PR 评论明确触发。评论内容必须包含 `@codex review`。
- 官方 Codex Review 触发评论必须保留仓库上下文：写明当前 PR、当前 head SHA、Review Scope 和本地门禁证据。禁止写“不要执行命令”“只做静态 diff review”“do not execute/run local commands”等会切断仓库、diff 或命令上下文的指令。
- 用户显式授权时，可以跳过官方 Codex Code Review；必须记录 `官方 Codex Review 跳过授权` 的 `authorized_by`、`reason` 和 `evidence`。该授权不允许绕过未解决且未过期的 Codex P0/P1 thread。
- Automatic reviews 可以作为补充，但不能替代上面的明确触发评论。
- PR 中如存在 Codex 标出的 P0/P1 问题，不得填写通过结论。
- 高风险或 unknown PR 描述必须填写 `Codex Code Review 结论`，且 `结论` 为 `通过`、`阻断问题` 为 `无` 后，才能进入合并。
- 低风险 PR 可以不触发官方 Codex Code Review，但必须填写 `AI Review 风险分级`、本地 AI review 报告、CI 通过证据和 P2 保留说明。
- 官方 Codex Code Review 应按 PR 中的 Review Scope 聚焦 P0/P1 风险，并在结论中说明是否发现规则冲突或漂移。
- 必须保留本地检查证据，至少包括 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate`。
- `@codex review` 触发后由 Codex Review Monitor 监听结果。该监控在 PR head 更新、PR 描述更新、触发评论、Codex review 和 inline review comment 事件上汇总当前 head 的所有 Codex review 状态，并写入 `Codex Review Monitor` commit status；`Codex Review Monitor` 必须列为 GitHub `main` 的 required status check，但它不替代 Codex review 结论和 PR body 证据。
- `pr-review-evidence` 与 `Codex Review Monitor` 必须读取 GitHub review thread 状态；只要存在未解决且未过期的 Codex P0/P1 thread，即使最新 Codex completion comment 显示无重大问题，也不得通过。
- 如果 Codex review 显示无法读取当前 PR diff、要求额外提供 unified diff、引用不存在或非当前 head 的提交，门禁必须按 review 上下文失效处理并阻断合并；不得用额外评论粘贴 PR diff 链接来替代正常 review 链路。

## 本地 AI Review

- Codex 本地 AI review 必须使用 Superpowers 和 Codex Security，并在本地报告 `security_review.tool` 记录 `codex-security`。
- Claude 本地 AI review 必须使用 pr-review-toolkit 和 security-guidance，并在本地报告 `security_review.tool` 记录 `security-guidance`。
- 所有 AI review provider 必须输出统一报告 schema。
- 统一报告 schema 的 `reviewers` 必须列出至少两个独立 reviewer；重复 reviewer 不算交叉评审；`cross_review.review_skills` 必须包含 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` 和 `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`。
- 统一报告 schema 的 `security_review.evidence` 必须记录本地安全 review 证据；PR body 的 `本地安全 review` 字段必须记录 `provider`、`tool` 和 `evidence`。
- 统一报告 schema v2 默认 `review_mode=complete`；`complete_review.iterations` 必须证明每个 reviewer 最后一轮为 `no_new_findings=true` 且 `new_findings=[]`。
- `review_mode=partial` 必须填写 `review_mode_authorization.authorized_by`、`reason` 和 `evidence`。
- PR body 的 `子 agent 交叉评审` 字段必须使用 `reviewers: A, B` 记录两个独立 reviewer 名称。
- 本地 AI review 必须输出具体问题、评级、文件位置、建议修复、处理状态和验证证据。
- 本地 AI review 不是 PR 模板生成器；它必须推动 P0/P1 修复闭环。

## 问题评级

- `P0`：严重错误交易、密钥泄露、主干保护绕过、明确安全漏洞。阻塞。
- `P1`：高概率 bug、回归、治理门禁失效、关键测试缺失。阻塞。
- `P2`：中等风险，可以保留，但必须写不修原因、风险接受理由和处理方式。
- `P3`：风格、可读性、小优化，不阻塞。
- P0/P1 阻塞，必须修复或证明误报。
- P2 可以保留，但必须写不修原因、风险接受理由和处理方式。
- P3 不阻塞。

## 官方 Codex Review 触发条件

- 风险等级为 `high` 或 `unknown`。
- PR 存在 `ai-risk-review` label。
- 本地 AI review 报告缺失、无法解析或无法证明低风险。
- 高风险路径或高风险规则命中。
- 用户显式授权跳过官方 Codex Review 时，上述触发条件可以不触发官方 review，但 PR body 必须填写 `官方 Codex Review 跳过授权`。已有未解决且未过期的 Codex P0/P1 thread 仍然阻断。

## 官方 Codex Review 触发评论格式

```markdown
@codex review

请基于当前 PR 的仓库上下文和 GitHub diff 做 review。

- PR: https://github.com/<owner>/<repo>/pull/<number>
- 当前 head: `<full-head-sha>`
- Review Scope: `.local/ai-review/codex-review-scope.md`
- 本地门禁: `make pre-pr`、`make ai-review`、`make risk-check`

请聚焦 P0/P1 风险：交易逻辑、治理门禁、安全边界、数据解释和测试缺口。P2/P3 只在影响合并判断时说明。
```

## 评审重点

- 代码风险：bug、未来函数、边界条件、参数不一致、回归风险。
- 聚宽策略风险：本地不可完整运行策略，不得把本地结果写成云端实盘结论。
- 治理风险：规则入口、CODEOWNERS、workflow、registry、catalog、waiver、pathref 是否漂移。
- 测试风险：相关单测、语法检查、治理 gate、策略或研究工具回归是否缺失。
- 报告风险：研究结论必须追溯 source table、manifest、audit log、run artifact，不只读最终报告。

## 规则关注点

Codex review 发现治理相关风险时，应优先对照以下规则文件定位冲突或漂移：

- [index.md](index.md) <!-- pathref: docs/rules/index.md -->：规则入口、规则分级、ADR 链接是否同步。
- [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->：核心 PR 工作流、分支模型、review 与主干同步是否遵守。
- [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->：CI、主干保护、CODEOWNERS、waiver、周期审计是否遵守。
- [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->：Codex Code Review 触发、范围和证据是否遵守。
- [commands.md](commands.md) <!-- pathref: docs/rules/commands.md -->：本地环境、虚拟环境和常用命令是否遵守。
- [research-workflow.md](research-workflow.md) <!-- pathref: docs/rules/research-workflow.md -->：本地研究、云端确认、报告同步是否遵守。
- [code-style.md](code-style.md) <!-- pathref: docs/rules/code-style.md -->：策略代码、注释、参数、测试是否遵守。
- [docs-and-pathref.md](docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->：Markdown、pathref、报告索引是否遵守。

## PR 证据格式

```markdown
## AI Review 风险分级

- 风险等级: low / high / unknown
- 是否需要官方 Codex Review: 是 / 否（低风险无需 / 用户授权跳过）
- 官方 Codex Review 跳过授权: 无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>
- 本地 AI review: `.local/ai-review/latest.md`
- 本地安全 review: provider=codex / claude；tool=codex-security / security-guidance；evidence=<安全 review 证据>
- 本地 AI review 模式: complete / partial
- 不完全 Review 模式授权: 无 / authorized_by=<授权人>；reason=<原因>；evidence=<授权证据>
- 子 agent 交叉评审: 填写 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` + `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`；reviewers: <规格评审子agent>, <代码质量评审子agent>；见 `.local/ai-review/latest.md`
- 任务分发说明: 填写已分发任务；未分发时写原因
- Codex Review Scope: `.local/ai-review/codex-review-scope.md`
- P0/P1 未关闭项: 无

## P2 保留项

- 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review`
- 结论: 通过
- 阻断问题: 无
- 关键证据:
  - Codex review 链接：https://github.com/<owner>/<repo>/pull/<number>#pullrequestreview-<id>
  - `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate`
```
