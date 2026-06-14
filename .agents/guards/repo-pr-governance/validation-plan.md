# Validation Plan（验证计划）

## 输入校准

- 已要求使用 `$grill-with-docs`（带文档拷问方法）完成术语、决策、边界、场景、例外和文档变更校准。
- 已确认决策：Guard Profile ID 使用 `repo-pr-governance`。
- 已确认决策：目标只守卫 repo-pr-governance PR 流程的 local review 和 security review 两个阶段。
- 已确认决策：本轮不守卫 pr-submit、official Codex review、required checks、merge 或 cleanup。
- 已确认决策：Subject Key 使用 `context.repo + context.worktree + context.branch`；本次不把 PR number 放入可选 KEY 配置，避免 PR 创建后实例 ID 升级导致旧实例与后续 Hook 事件断链；head/diff 只作 evidence freshness，不进入 Subject Key。
- 已确认决策：状态线精简为 `local_review_required -> security_review_required -> completed`。
- 已确认决策：在 local_review_required 阶段禁止运行 security review。
- 已确认决策：两个 review 阶段使用 `permissions.default: deny` 和窄 allowlist。
- 已确认决策：允许问题 FIX，但 FIX 后仍必须重新 review 并生成当前状态轮次的新 fragment。
- 已确认决策：启用工具级 deny 权限，并已获得用户明确授权。
- 已确认决策：启用 Hook 安装意向，并增加 SubagentStart gate，防止阶段不匹配的子 agent 派发。
- 文档变更摘要：本轮不更新 CONTEXT.md 或 ADR；所有已确认事实只进入本轮 confirmed-notes 和 Guard Profile 草案。

## 验证项

- 运行 validate_guard_profile.py，确认画像文件、状态、artifact、guard point、hook binding 引用合法。
- 在 local_review_required 下模拟 SubagentStart security reviewer，应返回 deny。
- 在 local_review_required 下模拟 SubagentStart Standards / Spec reviewer，应返回 allow。
- 在 security_review_required 下模拟 SubagentStart Standards / Spec reviewer，应返回 deny。
- 在 security_review_required 下模拟 SubagentStart security reviewer，应返回 allow。
- 模拟 PreToolUse 跑 pr-submit 或 git push，两个状态都应 deny。
- 准备当前状态轮次的 Standards / Spec fragments，提交 state_completed 后应进入 security_review_required。
- 准备当前状态轮次的 Security fragment，提交 state_completed 后应进入 completed。
- 确认安装计划不覆盖现有 `.githooks/pre-push`。
- 校验所有必需 Guard Profile（守卫画像）文件存在。
- 校验状态机、守卫点、产物、观察信号和 Hook Binding（钩子绑定）引用完整。
- 确认生成过程只写入 Guard Profile（守卫画像）草案目录，不修改被守卫对象。
## 项目级初始化验证

- 校验项目级 Guard Runtime（守卫运行时）骨架存在。
- 校验项目级 Guard Profile（守卫画像）能通过最小契约校验。
- 校验初始化未安装 Codex Hook（Codex 钩子）或 Git Hook（Git 钩子）。
- 校验初始化未修改被守卫对象。
