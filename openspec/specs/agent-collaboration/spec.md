## Purpose

TBD

## Requirements

### Requirement: 分支隔离

Agent 协作系统 SHALL 要求多个 AI agent 并行写入时，每个 agent 使用独立 Git 分支，禁止并行写入同一 repo-tracked 分支。

#### Scenario: 并行工作分配

- **WHEN** 多个 AI agent 需要同时修改仓库代码
- **THEN** 系统为每个 agent 分配独立 Git 分支（命名模板 `agent/<tool>/<topic>`），禁止共享同一分支写入

### Requirement: 任务分发授权

当子 agent 能力可用时，系统 SHALL 默认以用户持续显式授权模式优先将任务分发给子 agent，无能力或强串行依赖时记录原因和替代证据。

#### Scenario: 任务分发

- **WHEN** 主会话面临可独立执行的并行任务
- **THEN** 系统优先将任务分发给子 agent 执行，主会话负责编排、确认和汇总
