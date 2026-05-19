# ADR 0006: PR 风险分级评审流程

## Status

Accepted

## Context

当前流程要求所有 PR 合并前都完成官方 Codex Code Review。该规则安全边界清晰，但在低风险 PR 和大型 PR 上造成等待时间过长、重复 review 过多、CI 循环过多。

## Decision

采用风险分级评审流程：

- 所有 PR 必须先完成本地静态扫描、本地 AI review 和问题评级。
- P0/P1 问题必须修复或证明误报后才能继续。
- P2 问题可以保留，但必须记录不修原因、风险接受理由和处理方式。
- 低风险 PR 不强制触发官方 Codex Code Review。
- 高风险或 unknown PR 必须触发官方 Codex Code Review。
- 大型 PR 的官方 Codex Review 必须使用定向 scope，只审高风险目录和高风险命中改动的 P0/P1 逻辑风险。

## Consequences

- 官方 Codex Review 从全量门禁变成高风险复核。
- 本地 AI review 和 CI gate 承担低风险 PR 的主要自动化检查责任。
- 无法证明低风险的 PR 一律按高风险处理。
- 规则、PR 模板、workflow 和 governance gate 必须使用同一套风险评级语义。
