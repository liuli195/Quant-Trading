# ADR 0010: 本地分支禁止默认 history rewrite

## 状态

Accepted

## 背景

PR Flow 的 commit intent、local review fragments 和 PR Evidence 都依赖稳定的 commit SHA。Issue <https://github.com/liuli195/Quant-Trading/issues/123> 暴露出 `git commit --amend` 会让旧 commit intent 留在 branch intent 中，并可能让修复后的 diff 绕过第二轮本地 review。

## 决策

本地 `refs/heads/*` 默认只允许 fast-forward 更新；新建和删除分支允许，`commit --amend`、`rebase`、`squash`、`reset` 后重做提交等 history rewrite 默认阻断。例外只通过 repo-native wrapper 对单次 Git 命令注入 `ALLOW_BRANCH_HISTORY_REWRITE=1` 和 `BRANCH_HISTORY_REWRITE_REASON=<reason>`；wrapper 只负责本次授权命令，不负责 review、intent 或 cleanup 后续恢复。

## 影响

review finding 的修复默认使用追加 commit。该门禁优先防止 rewrite 发生，不把 stale branch intent 自动视为可修复的正常路径；未来如确需 rebase 解决冲突，再单独设计例外流程。
