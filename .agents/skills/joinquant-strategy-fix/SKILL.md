---
name: joinquant-strategy-fix
description: 处理 JoinQuant 云端策略编译报错、本地兼容定位、compile-check 和最小策略修复时使用。
---

# JoinQuant Strategy Fix

本技能负责 JoinQuant 云端策略编译报错、本地兼容定位、compile-check 和最小策略修复。

## 必读规则

- `docs/rules/environments.md`
- `docs/rules/code-style.md`
- `docs/rules/commands.md`

## 执行规则

- 只做本地修复，不上传策略，不启动云端回测。
- 需要云端复验时建议最小 `joinquant-cloud-run` 场景。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation compile-check <策略文件>
.\.venv\Scripts\python.exe -m py_compile <策略文件>
```
