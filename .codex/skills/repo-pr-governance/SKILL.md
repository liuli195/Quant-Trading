---
name: repo-pr-governance
description: 准备进入主干的 PR、review 证据、required checks、Codex review、主干保护和分支清理时使用。
---

# Repo PR Governance

本技能负责 PR 准备、review 证据、required checks、主干保护、Codex review 等待和分支清理。

## 必读规则

- `AGENTS.md` — 仓库通用入口和核心规则（含「规则优先」元规则）
- `docs/rules/pr-workflow.md`
- `docs/rules/review-guidelines.md`
- `docs/rules/governance.md`

## 执行规则

- 不把功能分支本地合入 `main`。
- 不伪造本地 AI review、交叉 review、安全 review 或官方 Codex review。
- `gh` CLI 默认按仓库规则提权执行。

## 推荐命令

```powershell
make verify-full
make pr-ready TITLE="<PR标题>"
make pr-diagnose PR=<PR号>
make pr-complete TITLE="<PR标题>"
make pr-cleanup PR=<PR号>
make ai-review
make risk-check
```
