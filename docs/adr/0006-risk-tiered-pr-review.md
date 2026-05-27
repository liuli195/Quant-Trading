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
- 低风险 PR 不强制触发官方 Codex Code Review。
- 高风险或 unknown PR 必须加 `ai-risk-review` label，并默认触发官方 Codex Code Review；用户显式授权时可以跳过，但必须记录授权人、原因和证据。
- `Codex Review Monitor` 保持 GitHub `main` 全局 required status check；低风险且无需官方 review 的 PR 可快速通过/空跑。
- 大型 PR 的官方 Codex Review 必须使用定向 scope，只审高风险目录和高风险命中改动的 P0/P1 逻辑风险。

## Consequences

- 官方 Codex Review 从全量必跑变成高风险复核；`Codex Review Monitor` 仍是全局 required check。
- 本地 AI review 和 CI gate 承担低风险 PR 的主要自动化检查责任。
- 本地 AI review 报告 schema 需要机器校验至少两个独立 reviewer、两个 Superpowers 评审模板、安全 review provider/tool/evidence、完全 review 终止条件和不完全模式授权；PR 模板需要用 `reviewers: A, B` 记录子 agent 交叉评审，并记录任务分发和本地安全 review 说明。
- 官方 Codex Review 跳过授权只影响是否等待官方 review，不影响未解决 Codex P0/P1 thread 的阻断。
- 无法证明低风险的 PR 一律按高风险处理。
- 规则、PR 模板、workflow 和 governance gate 必须使用同一套风险评级语义。
