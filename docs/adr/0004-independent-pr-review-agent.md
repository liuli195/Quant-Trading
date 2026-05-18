# ADR 0004: 独立 PR 评审治理 Agent

## 背景

仅有治理文档、PR 模板和普通 CI gate，不能证明合并前已经做过独立代码评审、治理规则 review 和测试回归判断。尤其当实现者直接提交或自审时，规则容易变成形式。

## 决策

- 新增独立评审 Agent：[pr-governance-review.md](../../.claude/agents/pr-governance-review.md) <!-- pathref: repo/.claude/agents/pr-governance-review.md -->。
- 该 Agent 只负责 review，不负责实现或修复。
- PR 描述必须包含 `评审治理 Agent 结论`，且结论必须为 `通过`、阻断问题必须为 `无`。
- CI job `pr-review-evidence` 必须校验 PR 描述中的 Agent 结论。
- GitHub `main` 的 required checks 必须包含 `Research Governance / governance` 和 `Research Governance / pr-review-evidence`。

## 后果

合并前检查从“实现者自报”升级为“独立评审结论 + CI 强校验”。这不能替代真人 owner review，但可以把 AI 评审、治理规则 review 和测试回归证据变成可阻断的合并条件。
