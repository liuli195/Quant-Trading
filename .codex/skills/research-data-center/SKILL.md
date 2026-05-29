---
name: research-data-center
description: 处理回测 run 数据快照、数据中心压缩、catalog、pointer 和可追溯证据时使用。
---

# Research Data Center

本技能负责历史回测 run、数据快照、数据中心压缩、catalog、pointer 和可追溯证据。

## 必读规则

- `docs/rules/research-workflow.md`

## 执行规则

- 不把本地 replay 包装成云端确认。
- 数据快照、pointer 和 catalog 必须可追溯。
- 新数据快照后刷新相关索引。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets
.\.venv\Scripts\python.exe -m scripts.research.docs index
```
