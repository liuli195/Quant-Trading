# Issue 跟踪：GitHub

本仓库的 Issue 和 PRD 统一记录在 GitHub Issues：`liuli195/Quant-Trading`。相关操作使用 `gh` CLI。

## 约定

- **创建 Issue**：`gh issue create --title "..." --body "..."`
- **读取 Issue**：`gh issue view <number> --comments`
- **列出 Issue**：`gh issue list --state open --json number,title,body,labels,comments`
- **评论 Issue**：`gh issue comment <number> --body "..."`
- **添加 / 移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 Issue**：`gh issue close <number> --comment "..."`

在本仓库内运行时，`gh` 应从 `git remote -v` 自动识别仓库。

## 当技能要求“发布到 issue tracker”

创建 GitHub Issue。

## 当技能要求“读取相关 ticket”

运行 `gh issue view <number> --comments`。
