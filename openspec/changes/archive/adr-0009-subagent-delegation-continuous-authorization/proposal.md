# ADR 0009: 子 agent 派发使用持续显式授权

## Why
仓库规则要求独立任务并行并优先派发子 agent。部分运行环境的子 agent 工具要求用户显式授权后才能调用；如果每次都重新确认，会让规则和工具约束之间反复产生流程阻断。

## What Changes
凡仓库规则要求或建议派发子 agent 的场景，均视为已满足子 agent 工具的显式授权前提。主会话仍负责编排、确认、汇总和验证。该授权只覆盖子 agent 派发本身，不覆盖直写主干等需要单独授权的动作。

## Impact
无可用子 agent 能力、只读查询、强串行依赖或权限只在主会话可用时，必须记录不分发原因和替代证据。PR review 仍按 review-guidelines.md 执行。

---
source: docs/adr/0009-subagent-delegation-continuous-authorization.md
migration: 历史 ADR 迁移 — 极简归档
