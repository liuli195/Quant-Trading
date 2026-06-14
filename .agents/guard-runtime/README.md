# Guard Runtime（守卫运行时）

此目录是项目级 Guard Runtime（守卫运行时）骨架。它只保留通用入口和目录约定，不写具体业务规则。

稳定入口：

```powershell
.\.venv\Scripts\python.exe .agents\guard-runtime\guard_runner.py activate --profile <id> --scope current_context --source agent-guard-skill --context-json '{"session_id":"..."}'
.\.venv\Scripts\python.exe .agents\guard-runtime\guard_runner.py run --event <event-file>
.\.venv\Scripts\python.exe .agents\guard-runtime\guard_runner.py brief --profile <id> --subject <subject-key-hash> --format json
.\.venv\Scripts\python.exe .agents\guard-runtime\guard_runner.py brief --profile <id> --subject <subject-key-hash> --session <session-id> --format json
```

`repo-pr-governance` 的显式激活必须传入和 Hook Adapter（钩子适配器）一致的 Subject Key（主体键）字段：

```powershell
.\.venv\Scripts\python.exe .agents\guard-runtime\guard_runner.py activate --profile repo-pr-governance --scope current_context --source agent-guard-skill --context-json '{"repo":"github.com/liuli195/Quant-Trading.git","worktree":"D:\\My Project\\Quant Trading","branch":"codex/repo-pr-governance-guard","session_id":"..."}'
```

目录约定：

- `.agents/guards/`：Guard Profile（守卫画像）配置。
- `.local/guard/state/`：按 `<guard-profile-id>/<subject-key-hash>/state.json` 保存状态。
- `.local/guard/runs/`：保存每次运行审计。
- `.local/guard/overrides/`：保存人工覆盖记录。
- `.local/guard/confirmations/`：保存人工确认记录。
- `.local/guard/latest/`：保存 latest Guard Brief（最新守卫简报）。
- `.local/guard/injections/`：按 session（会话）保存 Guard Brief（守卫简报）注入去重记录。

显式激活会按 Guard Profile（守卫画像）里的 Subject Resolver（主体解析器）计算 Subject Key（主体键），优先匹配已有 Guard Instance（守卫实例），没有匹配且策略允许时创建新实例。缺少必填字段会返回 `no_subject_match` 并写审计；多个候选实例会返回 `ambiguous_subject` 并写审计。

标准事件运行会读取 JSON envelope（JSON 信封），按 `guard_profile_id` 或 `profile_ref` 加载 Guard Profile（守卫画像），只匹配已有 Guard Instance（守卫实例）。主 agent（主代理）提交 `state_completed` 后，Runtime（运行时）会按当前状态、转换条件、required artifacts（必需产物）和 Guard Point（守卫点）决定是否推进状态。守卫点失败不推进状态，并输出失败守卫点、修复建议和覆盖记录位置。

`brief --session <session-id>` 会先校验 `subject-key-hash`、`state_version` 和 `expires_at`，再在 `.local/guard/injections/` 中记录已注入的 `brief_hash`。同一 session（会话）内相同 brief（简报）第二次返回 `already_injected`。

初始化阶段只写 Runtime（运行时）和 Profile（画像）配置，不预建 `.local/guard/*` 运行态目录，不安装 Hook（钩子），不会修改被守卫对象。当前项目随后已安装 Codex lifecycle Hook（生命周期钩子），并保留既有 Git Hook（Git 钩子）不改。
