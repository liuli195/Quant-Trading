---
name: research-report-analysis
description: 处理本地回测报告补齐、fix-missing、结果分析、多个 run 收益回撤对比和报告索引时使用。
---

# Research Report Analysis

本技能负责本地回测报告补齐、结果分析、多个 run 收益回撤对比和报告索引。

## 必读规则

- `docs/rules/research-workflow.md`
- `docs/rules/docs-and-pathref.md`

## 执行规则

- 不启动云端 run，不修改策略代码。
- 新报告必须进入报告索引并保留可追溯证据。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.docs index
```
