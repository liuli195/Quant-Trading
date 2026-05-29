---
name: repo-pr-governance
description: 准备进入主干的 PR、review 证据、required checks、Codex review、主干保护和分支清理时使用。
---

# Repo PR Governance Adapter

对应 Codex owner Skill：`.codex/skills/repo-pr-governance/SKILL.md`。

## 必读规则

- `docs/rules/pr-workflow.md`
- `docs/rules/review-guidelines.md`
- `docs/rules/governance.md`

## 推荐命令

```powershell
make pr-ready TITLE="<PR标题>"
make ai-review
make risk-check
```
