---
name: repo-skill-governance
description: 创建、修改、验证仓库级 Skill、.agents/skills 单一来源、Junction 分发、ownership 索引和 Skill 发现治理时使用。
---

# Repo Skill Governance

本技能负责仓库级 Skill 的新增、修改、迁移、发现语义和 ownership 治理。

## 必读规则

- `docs/rules/skills.md`
- `docs/rules/governance.md`

## 执行规则

- `.agents/skills/<skill>/` 是仓库级 Skill 的唯一来源，目录内保留完整 `SKILL.md`、`agents/openai.yaml` 和 `references/*`。
- Codex 直接读取 `.agents/skills/`；Claude Code 通过 `.claude/skills` Junction 读取同一份内容。
- 不再维护 `.codex/skills/` owner 与 `.claude/skills/` adapter 两份副本。
- 修改 Skill 后同步 `ownership.yaml`、治理测试、规则文档和文档索引。
- `ownership.yaml` 使用 `tools` 声明使用方，当前有效值为 `claude-code` 和 `codex`。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```
