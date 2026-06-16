# Skill 系统迁移审查

本文件用于 S12 HITL：删除旧兼容入口前，人工确认旧 Skill 到新 owner Skill 的覆盖关系。

| Old Skill | New Owner | 删除前必须满足 |
| --- | --- | --- |
| `.claude/skills/agent-doc-add` | `skill-system` | `skill-system` 发现样例通过，`docs/rules/skills.md` 已存在 |
| `.claude/skills/agent-doc-refactor` | `skill-system` | `skill-system` adapter 已覆盖入口文档治理 |
| `.claude/skills/jq-research` | `research-local-first` | 本地优先样例通过 |
| `.claude/skills/jq-analyze` | `research-report-analysis` | 报告分析样例通过 |
| `.claude/skills/jq-param-scan` | `strategy-experiment` | 参数扫描触发短语已覆盖 |
| `.claude/skills/jq-ab-test` | `strategy-experiment` | A/B 触发短语已覆盖 |
| `.claude/skills/jq-fix` | `joinquant-strategy-fix` | 编译错误触发短语已覆盖 |
| `.claude/skills/jq-run` | `joinquant-cloud-run` | 云端 run/fetch 触发短语已覆盖 |
| `.codex/skills/quant-pr-workflow` | `repo-pr-governance` | PR 治理样例通过 |
| `.codex/skills/quant-research-workflow` | `research-local-first` + research owners | 研究样例全部通过 |

## 风险

- 删除前必须确认 10 条发现样例都唯一命中新 owner。
- 删除前必须确认 Claude adapter 与 Codex owner description 等价。
- 删除前必须确认治理 gate 不再依赖旧 Skill 名称。
- 删除动作必须经人工明确同意，不能由实现过程自动推进。

## 人工确认问题

结论：本次迁移删除旧 Skill 兼容入口，只保留 10 个新 owner Skill 和同名 Claude adapter。删除前置条件由 `skill_ownership check` 和 `governance gate` 覆盖。
