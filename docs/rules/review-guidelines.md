# Codex Code Review 指南

本文件是仓库级 Codex Code Review 规则。AI 助手主入口仍是 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->；[AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只保留给 Codex 读取的 Review guidelines 指向。

## MUST

- PR 合并前必须完成官方 Codex Code Review，不再使用 `.claude/agents/pr-governance-review.md` 子 Agent 作为评审门禁。
- Codex Code Review 必须由 PR 评论明确触发。评论内容必须包含 `@codex review`，并要求按 `AGENTS.md` 与 `docs/rules/review-guidelines.md` 审查。
- Automatic reviews 可以作为补充，但不能替代上面的明确触发评论。
- PR 中如存在 Codex 标出的 P0/P1 问题，不得填写通过结论。
- PR 描述必须填写 `Codex Code Review 结论`，且 `结论` 为 `通过`、`阻断问题` 为 `无` 后，才能进入合并。
- Codex Code Review 必须逐条检查 [docs/rules](.) <!-- pathref: docs/rules --> 下所有规则文件，并在结论中说明是否发现规则冲突或漂移。
- 必须保留本地检查证据，至少包括 `.\.venv\Scripts\python.exe -m scripts.research.governance gate`。
- `@codex review` 触发后由 Codex Review Monitor 监听结果。该监控在 PR head 更新、触发评论、Codex review 和 inline review comment 事件上汇总当前 head 的所有 Codex review 状态，并写入 `Codex Review Monitor` commit status；`Codex Review Monitor` 必须列为 GitHub `main` 的 required status check，但它不替代 Codex review 结论和 PR body 证据。

## 评审重点

- 代码风险：bug、未来函数、边界条件、参数不一致、回归风险。
- 聚宽策略风险：本地不可完整运行策略，不得把本地结果写成云端实盘结论。
- 治理风险：规则入口、CODEOWNERS、workflow、registry、catalog、waiver、pathref 是否漂移。
- 测试风险：相关单测、语法检查、治理 gate、策略或研究工具回归是否缺失。
- 报告风险：研究结论必须追溯 source table、manifest、audit log、run artifact，不只读最终报告。

## 规则逐条检查

Codex review 必须逐条检查以下规则文件：

- [index.md](index.md) <!-- pathref: docs/rules/index.md -->：规则入口、规则分级、ADR 链接是否同步。
- [ai-agents.md](ai-agents.md) <!-- pathref: docs/rules/ai-agents.md -->：多 AI 协作、分支模型、主干禁止本地合并是否遵守。
- [governance.md](governance.md) <!-- pathref: docs/rules/governance.md -->：CI、主干保护、CODEOWNERS、waiver、周期审计是否遵守。
- [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->：Codex Code Review 触发、范围和证据是否遵守。
- [research-workflow.md](research-workflow.md) <!-- pathref: docs/rules/research-workflow.md -->：本地研究、云端确认、报告同步是否遵守。
- [code-style.md](code-style.md) <!-- pathref: docs/rules/code-style.md -->：策略代码、注释、参数、测试是否遵守。
- [docs-and-pathref.md](docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->：Markdown、pathref、报告索引是否遵守。

## PR 证据格式

```markdown
## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review 按 AGENTS.md 和 docs/rules/review-guidelines.md 审；逐条检查 docs/rules/*.md`
- 结论: 通过
- 阻断问题: 无
- 关键证据:
  - Codex review 链接：https://github.com/<owner>/<repo>/pull/<number>#pullrequestreview-<id>
  - `.\.venv\Scripts\python.exe -m scripts.research.governance gate`
```
