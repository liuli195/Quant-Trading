# PR Review 指南

本文件是仓库级 PR review 规则。AI 助手通用入口是 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；[CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md --> 只保留 Claude Code 专属指针。

## MUST

- 所有 PR 必须完成本地 AI review、问题评级和风险分级。
- P0/P1 问题未以 `fixed` 或 `false_positive` 关闭前，不得进入下一阶段。
- 高风险或 unknown PR 的 Codex Code Review 必须由 PR 评论明确触发。评论内容必须包含 `@codex review`。
- Automatic reviews 可以作为补充，但不能替代上面的明确触发评论。
- PR 中如存在 Codex 标出的 P0/P1 问题，不得填写通过结论。
- 高风险或 unknown PR 描述必须填写 `Codex Code Review 结论`，且 `结论` 为 `通过`、`阻断问题` 为 `无` 后，才能进入合并。
- 低风险 PR 可以不触发官方 Codex Code Review，但必须填写 `AI Review 风险分级`、本地 AI review 报告、CI 通过证据和 P2 保留说明。
- 官方 Codex Code Review 应按 PR 中的 Review Scope 聚焦 P0/P1 风险，并在结论中说明是否发现规则冲突或漂移。
- 必须保留本地检查证据，至少包括 `.\.venv\Scripts\python.exe -m scripts.research.governance gate`。
- `@codex review` 触发后由 Codex Review Monitor 监听结果。该监控在 PR head 更新、触发评论、Codex review 和 inline review comment 事件上汇总当前 head 的所有 Codex review 状态，并写入 `Codex Review Monitor` commit status；`Codex Review Monitor` 必须列为 GitHub `main` 的 required status check，但它不替代 Codex review 结论和 PR body 证据。

## 本地 AI Review

- Codex 本地 AI review 使用 Superpowers 和 Codex Security。
- Claude 本地 AI review 使用 pr-review-toolkit 和 security-guidance。
- 所有 AI review provider 必须输出统一报告 schema。
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
- 是否需要官方 Codex Review: 是 / 否
- 本地 AI review: `.local/ai-review/latest.md`
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
  - `.\.venv\Scripts\python.exe -m scripts.research.governance gate`
```
