# ADR 0009: 子 agent 派发使用持续显式授权

## 状态

Accepted

## 背景

仓库规则要求独立任务并行，并在有可用子 agent 能力时优先派发。部分运行环境的子 agent 工具要求用户显式授权后才能调用；如果每次都重新确认，会让仓库规则和工具约束之间反复产生流程阻断。

## 决策

在本仓库中，`AGENTS.md` 和协作规则中的“优先派发子 agent”同时记录用户对本仓库的持续显式授权。凡仓库规则要求或建议派发子 agent、`sub-agents`、`delegation` 或 `parallel agent work` 的场景，均视为已满足子 agent 工具的显式授权前提。

PR Flow 的 Standards / Spec review fragment 必须用 `delegation_attempt` 记录派发结果。允许的非 `spawned` 结果只有 `tool_unavailable` 和 `spawn_failed`；`tool_unavailable` 表示工具未注册、不可用或不可调用，`spawn_failed` 表示已派发但没有可用 review 结论且不能满足本地 review evidence。不得用 `user_not_authorized`、`permission_not_allowed`、`explicit_authorization_missing`、`policy_disallowed` 表示授权缺失，因为授权已由本 ADR 和 `AGENTS.md` 持续提供。

该授权只覆盖子 agent 派发本身，不覆盖直写主干、绕过官方 Codex required check、跳过 GitHub Issue 关联、破坏性操作、权限提升、force push、reset 或其他需要单独授权的动作。

## 影响

- 主会话仍负责编排、确认、汇总和验证。
- 无可用子 agent 能力、只读查询、强串行依赖或权限只在主会话可用时，必须记录不分发原因和替代证据。
- PR review 仍按 [review-guidelines.md](../../../../docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> 记录本地 review、官方 Codex required check 和未 resolved thread 阻断。
- 协作边界仍按 [collaboration.md](../../../../docs/rules/collaboration.md) <!-- pathref: docs/rules/collaboration.md --> 执行。
