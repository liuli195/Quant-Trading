---
name: repo-docs-pathref
description: 处理 Markdown 链接、pathref、docs index、文档索引、报告索引和 catalog 同步时使用。
---

# Repo Docs Pathref

本技能负责文档链接、pathref、docs index、报告索引和 catalog 同步。

## 必读规则

- `docs/rules/docs-and-pathref.md`
- `docs/rules/governance.md`

## 执行规则

- 移动文档、报告或内部链接后刷新索引并检查 pathref。
- 不把 Skill 治理规则塞进文档链接流程；Skill 规则归 `repo-skill-governance`。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
.\.venv\Scripts\python.exe -m scripts.research.docs index
```
