# ADR 0007: PR 强闭环状态机与 Review Evidence 边界

## Why
PR #21/#22 和 PR #25/#26 复盘暴露出 evidence、review、required checks、GitHub review threads、merge policy 和 cleanup 仍经常退回人工判断。需要从"脚本辅助 + 人工判断"升级为强闭环状态机。

## What Changes
- 高频入口收敛为 pr-submit，负责创建/更新 PR、刷新 evidence、wait required checks、head-locked auto-merge 和本地收尾
- review coverage 绑定当前 diff fingerprint
- PR Evidence JSON 只接受 v2 格式
- 官方 Codex P2/P3 review thread 可由 pr_flow 自动接受并 resolve
- cleanup 末尾必须检查 worktree health
- target spec wins：当 PR 目标 Issue/PRD 与旧仓库规则冲突时以目标方案为裁判基准

## Impact
确定性步骤自动推进，只在缺结构化输入、需要回复/修复或外部异常时停止。本地缓存提高恢复能力但不成为 CI 信任来源。

---
source: docs/adr/0007-pr-flow-closed-loop-review-evidence.md
migration: 历史 ADR 迁移 — 极简归档
