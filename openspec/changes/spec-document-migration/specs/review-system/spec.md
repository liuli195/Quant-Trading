## ADDED Requirements

### Requirement: 双 Reviewer 交叉评审

Review 系统 SHALL 要求每个 PR 至少完成两个独立 reviewer 的交叉评审，记录评审证据到结构化 fragment。

#### Scenario: 交叉评审完成

- **WHEN** Standards reviewer 和 Spec reviewer 分别产出 review fragment（`.local/ai-review/fragments/standards.json` 和 `spec.json`）
- **THEN** 系统在 fragment 中记录 `reviewers: A, B`，且每个 reviewer 最后一轮 `no_new_findings=true`

### Requirement: 风险分级评审

Review 系统 SHALL 按风险等级决定是否需要官方 Codex review：P0/P1 阻断合并，P2/P3 作为 retained finding 记录。

#### Scenario: P0 阻断

- **WHEN** 任一 reviewer 发现 P0 级 finding 且状态为 `open`
- **THEN** 系统阻断 PR 进入下一阶段，直到 finding 被标记为 `fixed` 或 `false_positive` 并提供当前 head/diff 下的证据

### Requirement: 官方 Codex Review 集成

当 `official_review.decision=required` 时，系统 SHALL 触发 `@codex review` 并等待 current-head verdict，P2/P3 由系统自动接受并 resolve。

#### Scenario: 触发官方 review

- **WHEN** 本地双 reviewer 评审通过且风险等级为 P0/P1
- **THEN** 系统通过 PR comment 触发 `@codex review`，在 3 分钟内等待 Codex bot 的 `eyes` reaction 确认远端已接收
