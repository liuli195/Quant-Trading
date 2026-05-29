---
name: repo-python-env
description: 处理本仓库 Python 环境、项目 .venv、PYTHONUTF8、UTF-8、本地/云端运行边界和系统 Python 禁用规则时使用。
---

# Repo Python Env

本技能负责本仓库 Python 环境、项目 `.venv`、UTF-8 环境变量、本地/云端运行边界。

## 必读规则

- `docs/rules/commands.md`
- `docs/rules/environments.md`

## 执行规则

- 默认使用项目 `.venv`，不改用系统 Python。
- 策略代码只在 JoinQuant 云端运行；本地只做编写、测试、文档和回测分析。
- 声明环境已配置前，先运行实际命令验证。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```
