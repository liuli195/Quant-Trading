---
name: joinquant-strategy-fix
description: 处理 JoinQuant 云端策略编译报错、本地兼容定位、compile-check 和最小策略修复时使用。
---

# JoinQuant Strategy Fix Adapter

对应 Codex owner Skill：`.codex/skills/joinquant-strategy-fix/SKILL.md`。

## 必读规则

- `docs/rules/environments.md`
- `docs/rules/code-style.md`
- `docs/rules/commands.md`

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation compile-check <策略文件>
.\.venv\Scripts\python.exe -m py_compile <策略文件>
```
