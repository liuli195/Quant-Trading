---
name: skill-system
description: 创建、修改、验证 Codex owner Skill、Claude adapter、触发语义、ownership 索引和 Skill 发现治理时使用。
---

# Skill System

本技能负责新增、修改、验证 owner Skill、Claude adapter、触发语义和 ownership 索引。

## 必读规则

- `docs/rules/skills.md`
- `docs/rules/governance.md`

## 执行规则

- Codex owner Skill 是事实入口；Claude adapter 只做同名指针。
- 不把 `docs/rules/**` 正文或 `scripts/**` 实现复制进 Skill。
- 修改 Skill 后同步 `ownership.yaml`、测试和文档索引。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```
