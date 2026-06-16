# ADR 0010: 本地分支禁止默认 history rewrite

## Why
PR Flow 的 commit intent、local review fragments 和 PR Evidence 都依赖稳定的 commit SHA。git commit --amend 会让旧 commit intent 留在 branch intent 中，并可能让修复后的 diff 绕过第二轮本地 review。

## What Changes
本地 refs/heads/* 默认只允许 fast-forward 更新；新建和删除分支允许，commit --amend、rebase、squash、reset 后重做提交等 history rewrite 默认阻断。例外只通过 repo-native wrapper 单次授权。

## Impact
review finding 的修复默认使用追加 commit。该门禁优先防止 rewrite 发生，不把 stale branch intent 自动视为可修复的正常路径。

---
source: docs/adr/0010-local-branch-history-rewrite-gate.md
migration: 历史 ADR 迁移 — 极简归档
