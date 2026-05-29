---
name: strategy-experiment
description: 处理策略参数扫描、A/B 实验、variant registry、控制变量和 delta 归因时使用。
---

# Strategy Experiment

本技能负责策略参数扫描、A/B 实验、variant registry、控制变量和 delta 归因。

## 必读规则

- `docs/rules/research-workflow.md`

## 执行规则

- 执行前展示计划，明确控制变量和验证口径。
- 云端额度消耗前必须确认。
- 参数变体不默认开 Git 分支，不自动修改默认参数。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.variants
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```
