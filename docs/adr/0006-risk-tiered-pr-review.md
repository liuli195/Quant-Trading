# ADR 0006: PR 风险分级评审流程

## Status

Accepted

## Context

当前流程要求所有 PR 合并前都完成官方 Codex Code Review。该规则安全边界清晰，但在低风险 PR 和大型 PR 上造成等待时间过长、重复 review 过多、CI 循环过多。

## Decision

采用风险分级评审流程：

- 所有 PR 必须先完成本地静态扫描、本地 AI review 和问题评级。
- 本地 AI review 必须由至少两个独立 reviewer 完成子 agent 交叉评审；评审子 agent 必须使用 Superpowers 模板 `superpowers:subagent-driven-development/spec-reviewer-prompt.md` 和 `superpowers:subagent-driven-development/code-quality-reviewer-prompt.md`；PR body 必须用 `reviewers: A, B` 记录两个独立 reviewer；实现者或主会话不得作为唯一 reviewer。
- 本地 AI review 必须包含安全 review 证据：Codex provider 必须使用 `codex-security`，Claude provider 必须使用 `security-guidance`；本地报告和 PR body 都必须记录该证据。
- 本地 AI review 默认采用 `complete` 完全 review 模式：两个 reviewer 必须持续查找更多发现，直到各自最后一轮明确记录无新发现。只有用户显式授权时，才能使用 `partial` 不完全模式。
- 有可用子 agent 能力时，PR 任务默认优先分发；无能力、简单只读、强串行依赖或权限只在主会话可用时，记录原因和替代证据。
- P0/P1 问题必须修复或证明误报后才能继续。
- P2 问题可以保留，但必须记录不修原因、风险接受理由和处理方式。
- 新 PR Flow 下，`risk=low` 且标记“官方 Codex Review=否”时，可以不触发官方 Codex Review；高风险、unknown、命中高风险路径或带 `ai-risk-review` label 的 PR 默认必须触发官方 Codex Review。
- 高风险或 unknown PR 必须加 `ai-risk-review` label，用于标记风险和收窄 Review Scope；用户显式授权可以跳过官方 Codex review，但不得绕过 unresolved thread、P0/P1 或 GitHub required checks 的其它阻断。
- `PR Flow / review-status` 保持 GitHub `main` 全局 required status check；官方 Codex review 未返回时保持 pending。
- 大型 PR 的官方 Codex Review 必须使用定向 scope 聚焦 P0/P1 逻辑风险；scope 只能提效，不得绕过 current-head 官方 review。

## Consequences

- 官方 Codex Review 由 `PR Flow / review-status` 统一等待和校验；低风险或用户授权跳过时，该 required check 写 skipped success。
- 本地 AI review、Security fragment 和 CI gate 提供输入与远端验证；GitHub required checks 和 merged state 仍是合并权威。
- 本地 AI review 报告 schema 需要机器校验至少两个独立 reviewer、两个 Superpowers 评审模板、安全 review provider/tool/evidence、完全 review 终止条件和不完全模式授权；PR 模板需要用 `reviewers: A, B` 记录子 agent 交叉评审，并记录任务分发和本地安全 review 说明。
- official-review waiver 仍属于新 PR Flow 合并路径，但必须记录 `authorized_by`、`reason`、`evidence`，且只影响是否等待官方 Codex review。
- 无法证明低风险的 PR 一律按高风险处理；风险分级影响是否默认触发官方 review、scope、本地关注重点和 label。
- 规则、PR 模板、workflow 和 governance gate 必须使用同一套风险评级语义。
