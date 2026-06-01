---
name: research-local-first
description: 处理本地优先研究、候选漏斗、fast/full 筛选和云端交接判断时使用。
---

# Research Local First

本技能负责本地优先研究、候选漏斗、fast/full 筛选和云端交接判断。

## 必读规则

- `docs/rules/research-workflow.md`

## 执行规则

- 多候选研究先本地筛选，再消耗 JoinQuant 云端额度。
- 不包办报告、A/B 和云端 run；需要时转交对应 Skill。
- 不把本地 replay 结论包装成云端确认。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```
