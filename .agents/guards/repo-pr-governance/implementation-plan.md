# Implementation Plan（实施计划）

Guard Profile（守卫画像）：repo-pr-governance

## 初始化

- 根据本次调用确认画像：`repo-pr-governance`。
- 在目标范围显式初始化 Guard Runtime（守卫运行时）和 Guard Profile（守卫画像）目录。
- 初始化阶段只生成配置和验证计划，不预建 `.local/guard/*` 运行态目录，不修改被守卫对象。
- 初始化输入必须是本轮调研生成并校验通过的 Guard Profile（守卫画像）草案目录。

## 守卫注入

- Guard Injection（守卫注入）默认启用。
- 初始化后 agent（代理）通过 latest Guard Brief（最新守卫简报）读取当前状态和下一步要求。
- 使用 `brief --session <session-id>` 时按 session（会话）记录 `brief_hash`，避免重复注入。

## Hook（钩子）

- 调研已确认启用 Hook（钩子）。
- 已安装 Codex lifecycle Hook（生命周期钩子）：`UserPromptSubmit`、`SubagentStart`、`SubagentStop`、`PreToolUse`。
- 不安装 agent-guard Git Hook（Git 钩子），保留仓库既有 `.githooks/pre-push`。

## 配置

- activation.initial_state：`local_review_required`。
- activation.on_existing_subject：`reuse`。
- activation.on_missing_subject：`create`。
- subject.identity_fields：`context.repo`, `context.worktree`, `context.branch`。
- subject.required_fields：`context.repo`, `context.worktree`, `context.branch`。
- `context.repo` 必须使用 Hook Adapter（钩子适配器）输出的 canonical remote id（规范远端标识）：`github.com/liuli195/Quant-Trading.git`。
- 显式 activate（激活）必须同时传入 `repo`、`worktree` 和 `branch`，避免和 Hook 事件计算出不同 Subject Key（主体键）。
- 业务规则只放在 Guard Profile（守卫画像）配置中，Runtime（运行时）和 Hook（钩子）只做通用执行。

## 守卫点划分

- `local_review_gate`：依赖产物=`standards_fragment`, `spec_fragment`。
- `security_review_gate`：依赖产物=`security_fragment`。

## 单个守卫点单独实施计划

### `local_review_gate`

1. 确认该守卫点的目标、触发事件、依赖产物和失败行为。
2. 只启用该守卫点关联的状态转换、产物引用和 Hook Binding（钩子绑定）。
3. 运行 `validate_guard_profile.py <guard-profile-dir>` 校验文件和引用。
4. 验证该守卫点失败时不会推进状态，并能输出清晰修复建议。
5. 如果误报或检查错误，只回滚该守卫点，不回滚整个 Guard Profile（守卫画像）。

### `security_review_gate`

1. 确认该守卫点的目标、触发事件、依赖产物和失败行为。
2. 只启用该守卫点关联的状态转换、产物引用和 Hook Binding（钩子绑定）。
3. 运行 `validate_guard_profile.py <guard-profile-dir>` 校验文件和引用。
4. 验证该守卫点失败时不会推进状态，并能输出清晰修复建议。
5. 如果误报或检查错误，只回滚该守卫点，不回滚整个 Guard Profile（守卫画像）。

## 产物和 Hook（钩子）接入

- Artifact（产物）`standards_fragment`：owner（所有者）=`repo-pr-governance pr_flow builder`。
- Artifact（产物）`spec_fragment`：owner（所有者）=`repo-pr-governance pr_flow builder`。
- Artifact（产物）`security_fragment`：owner（所有者）=`repo-pr-governance pr_flow builder`。
- Artifact（产物）`review_fragments_handoff`：owner（所有者）=`pr-submit`。
- Artifact（产物）`local_review_builder_payload`：owner（所有者）=`main-agent`。
- Artifact（产物）`security_builder_payload`：owner（所有者）=`main-agent`。
- Hook Binding（钩子绑定）`codex_pre_tool_use_permission`：event_type=`codex.pre_tool_use`。
- Hook Binding（钩子绑定）`codex_subagent_start_gate`：event_type=`codex.subagent_start`。
- Hook Binding（钩子绑定）`codex_subagent_stop_audit`：event_type=`codex.subagent_stop`。
- Hook Binding（钩子绑定）`codex_user_prompt_submit_injection`：event_type=`codex.user_prompt_submit`。
