# ADR 0008: Skill 使用 .agents/skills/ 单一来源

## Why
仓库级 Skill 原来分成两份维护：.codex/skills/ 保存完整 owner Skill，.claude/skills/ 保存 Claude adapter。每次改 Skill 都要同步两处文件，治理脚本还要校验等价性。

## What Changes
- .agents/skills/ 是仓库级 Skill 的唯一事实来源
- Codex 直接读取 .agents/skills/
- Claude Code 通过 .claude/skills Directory Symlink 指向 .agents/skills
- .codex/skills/ 删除
- ownership.yaml 删除 adapters 字段，改用 tools 字段

## Impact
修改一个 Skill 只需要改 .agents/skills/<skill>/ 一处。治理检查从 adapter 等价性改为 .agents/skills 完整性和 Symlink 有效性检查。

---
source: docs/adr/0008-skill-single-source-agents.md
migration: 历史 ADR 迁移 — 极简归档
