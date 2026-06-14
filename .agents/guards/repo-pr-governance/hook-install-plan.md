# Hook Install Plan（钩子安装计划）

Guard Profile（守卫画像）：repo-pr-governance

- 当前状态：已安装 Codex Hook（Codex 钩子）：`.codex/hooks.json`。
- 当前状态：未安装 Git Hook（Git 钩子），并保留仓库现有 `.githooks/pre-push`。
- 用户已确认要安装 Hook（钩子）；本次安装只覆盖 Codex lifecycle hooks（生命周期钩子）。
- Hook（钩子）只负责捕获和标准化事件，不写业务规则。

## Installed Entries（已安装入口）

- Codex Hook（Codex 钩子）：`UserPromptSubmit`、`SubagentStart`、`SubagentStop`、`PreToolUse`。
- Adapter（适配器）：`.agents/guard-runtime/hook_event_adapter.py`。
- `SubagentStart` 无工具名时，adapter 会补充通用工具名 `codex.subagent`，让 Runtime（运行时）能执行状态权限评估。
- Git pre-push Hook（Git 推送前钩子）：未安装 agent-guard 入口，避免覆盖本仓库既有治理 pre-push。

## Runtime Call（运行时调用）

```text
D:\My Project\Quant Trading\.venv\Scripts\python.exe .agents/guard-runtime/guard_runner.py run --event <event-file>
```

## Hook Bindings（钩子绑定）

- `codex_pre_tool_use_permission`：source=`codex`，event_type=`codex.pre_tool_use`。
- `codex_subagent_start_gate`：source=`codex`，event_type=`codex.subagent_start`。
- `codex_subagent_stop_audit`：source=`codex`，event_type=`codex.subagent_stop`。
- `codex_user_prompt_submit_injection`：source=`codex`，event_type=`codex.user_prompt_submit`。

## Rollback（回滚）

- 从 `.codex/hooks.json` 移除 `repo-pr-governance` 的 managed entries。
- 删除 `.agents/guard-runtime/hook_event_adapter.py`。
- 保留 `.githooks/pre-push` 不变。
