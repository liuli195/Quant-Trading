# Skill 系统迁移审查

## Why
删除旧兼容入口前，需要人工确认旧 Skill 到新 owner Skill 的覆盖关系。10 条发现样例必须唯一命中新 owner，Claude adapter 与 Codex owner description 必须等价。

## What Changes
- 确认旧 Skill → 新 Owner Skill 的覆盖关系
- 确认删除前置条件由 skill_ownership check 和 governance gate 覆盖
- 结论：迁移删除旧 Skill 兼容入口，只保留 10 个新 owner Skill

## Impact
删除前必须确认 10 条发现样例都唯一命中新 owner、Claude adapter 与 Codex owner description 等价、治理 gate 不再依赖旧 Skill 名称。删除动作必须经人工明确同意。

---
source: docs/design/skill-system-migration-review.md
