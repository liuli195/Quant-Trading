# 跨 AI 工具 Skill 管理实施计划

## 目标

建立一套可扩展的跨 AI 工具 Skill 管理流程，让系统级 Skill 可以通过 `cc-switch` 在 Claude Code、Codex、Gemini、OpenCode 等工具间同步，同时保留本仓库的规则入口、仓库级 Skill、MCP 和治理门禁边界。

## 已知事实

- `cc-switch` 已支持跨应用管理 Skills、MCP 和 prompts，说明见 [cc-switch-cli.md](../cc-switch-cli.md) <!-- pathref: docs/cc-switch-cli.md -->。
- 本仓库的 AI 通用入口是 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；Claude Code 专属入口是 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->。
- 入口分层已经由 [ADR 0005](../adr/0005-ai-entry-progressive-disclosure.md) <!-- pathref: docs/adr/0005-ai-entry-progressive-disclosure.md --> 确认：通用规则进 `AGENTS.md`，工具专属内容进对应工具入口，细则进 `docs/rules/*.md`。
- 本仓库治理要求规则入口、Skill、README、workflow、registry、catalog 和 pathref 不漂移，见 [governance.md](../rules/governance.md) <!-- pathref: docs/rules/governance.md -->。
- Markdown 内部引用必须使用可点击链接加 `pathref` 注释，见 [docs-and-pathref.md](../rules/docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md -->。

## 设计边界

- 系统级 Skill：由 `cc-switch` 的 SSOT 管理，目标是跨工具同步。
- 仓库级 Skill：当前继续由 Git、PR、CODEOWNERS 和治理门禁管理，不默认通过 `cc-switch` 自动同步。
- MCP：不是所有 Skill 的必需项；只有 Skill 声明依赖 MCP 时才纳入同步前置检查。
- Prompts / `AGENTS.md` / `CLAUDE.md`：只做入口指针和分层规则，不把完整 Skill 内容复制进根入口文件。
- 本计划先落设计和门禁，再启用真实同步；避免用户级配置覆盖仓库级行为。

## 推荐架构

```text
系统级 Skill 源
  ~/.cc-switch/skills/
        |
        | cc-switch skills enable/sync
        v
各工具用户级目录
  ~/.claude/skills 或等价目录
  ~/.codex/...
  ~/.gemini/...
  ~/.config/opencode/...

仓库级 Skill 源
  .claude/skills/
        |
        | Git + PR + governance gate
        v
本仓库 Claude Code 专属工作流

MCP 注册
  cc-switch mcp list/enable/sync
        |
        v
仅服务声明了 MCP 依赖的 Skill
```

## 元数据模型

后续为每个受管 Skill 增加一份轻量元数据。字段建议如下：

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定 Skill 标识 |
| `name` | 展示名称 |
| `scope` | `global` 或 `repo-local` |
| `owner` | 维护负责人或维护团队 |
| `lifecycle` | `active`、`experimental`、`deprecated` |
| `target_apps` | 允许同步到的工具，例如 `claude`、`codex`、`gemini` |
| `requires_mcp` | 依赖的 MCP server id 列表，可为空 |
| `source` | 来源：`cc-switch`、repo path、外部仓库等 |
| `sync_method` | `symlink`、`copy` 或 `auto` |
| `last_sync_hash` | 上次同步内容摘要，用于漂移检查 |

## 分步实施计划

### 第 1 步：盘点现状

目标：确认系统级和仓库级 Skill 的来源，不直接改同步行为。

- 运行 `cc-switch skills scan-unmanaged`，盘点各工具目录中的未管理 Skill。
- 运行 `cc-switch skills list`，确认 `cc-switch` SSOT 中已有 Skill。
- 读取 `.claude/skills/`，把本仓库 Skill 先标记为 `repo-local`。
- 输出一份盘点表，列出 Skill 名称、来源、目标工具、是否依赖 MCP、是否适合系统级复用。

验收标准：

- 能区分 `global` 和 `repo-local`。
- 不产生跨工具写入。
- 不覆盖 `.claude/skills/`。

### 第 2 步：定义 Skill 分层规则

目标：确定哪些 Skill 能进入系统级 SSOT，哪些必须留在仓库。

规则：

- 通用开发方法、文档处理、跨项目工具 Skill 可以进入 `global`。
- 依赖本仓库路径、策略、JoinQuant 流程、治理门禁的 Skill 留在 `repo-local`。
- `repo-local` Skill 不通过用户级 `cc-switch skills sync` 自动覆盖。
- 如果未来需要跨工具使用仓库级 Skill，应先增加元数据和审计，再开放同步。

验收标准：

- 每个现有 Skill 都有明确层级。
- `AGENTS.md` 不新增大段 Skill 细节。
- `CLAUDE.md` 继续只保留 Claude 专属指针。

### 第 3 步：建立 MCP 依赖规则

目标：避免把 MCP 同步变成无条件步骤。

规则：

- `requires_mcp` 为空时，跳过 MCP 同步。
- `requires_mcp` 非空时，先执行 MCP 校验，再同步 Skill。
- MCP 同步失败时，不继续启用依赖它的 Skill。
- MCP 配置归 `cc-switch mcp` 管理，不写死在 Skill 正文里。

建议命令顺序：

```powershell
cc-switch mcp list
cc-switch mcp validate <command>
cc-switch --app <app> mcp enable <mcp_id>
cc-switch mcp sync
cc-switch --app <app> skills enable <skill_id>
cc-switch skills sync
```

验收标准：

- 纯文档型、流程型 Skill 不要求 MCP。
- 依赖 MCP 的 Skill 有前置校验。
- MCP 注册和 Skill 启用状态能分别审计。

### 第 4 步：设计同步命令规范

目标：让同步动作可复现、可回滚。

系统级 Skill 推荐流程：

```powershell
cc-switch skills list
cc-switch skills install <skill_id>
cc-switch --app <app> skills enable <skill_id>
cc-switch skills sync-method auto
cc-switch skills sync
```

仓库级 Skill 当前流程：

```powershell
git status --short
# 在仓库内通过 PR 修改 .claude/skills/<skill>/SKILL.md
# 修改后运行治理门禁和 pathref 检查
```

验收标准：

- 系统级同步通过 `cc-switch` 完成。
- 仓库级 Skill 仍通过 Git diff 和 PR 审核。
- 同步前后能看到目标应用、目标 Skill、同步方式和结果。

### 第 5 步：扩展治理审计

目标：把关键边界纳入机器检查。

建议新增检查：

- `AGENTS.md` 只保留通用入口，不复制工具专属 Skill 细节。
- `CLAUDE.md` 只保留 Claude Code 专属指针，并继续引用 `.claude/skills`。
- `.claude/skills/**/SKILL.md` 仍是仓库级 Skill 的权威文件。
- `repo-local` Skill 不应出现在系统级自动同步白名单。
- 声明 `requires_mcp` 的 Skill 必须能在 MCP 注册表中找到依赖。
- Skill 元数据必须包含 `owner`、`lifecycle`、`scope`、`target_apps`。

验收标准：

- `scripts.research.governance gate` 能发现入口漂移。
- `pathref` 检查继续通过。
- 未声明边界的 Skill 不能进入自动同步。

### 第 6 步：小范围试点

目标：先验证一个无 MCP 依赖的系统级 Skill。

试点选择标准：

- 不依赖本仓库路径。
- 不修改项目文件。
- 不需要 MCP。
- 能在至少两个工具中使用。

流程：

1. 安装到 `cc-switch` SSOT。
2. 对两个目标工具启用。
3. 执行 `cc-switch skills sync`。
4. 比较两个工具目录中的 Skill 内容摘要。
5. 记录回滚命令。

验收标准：

- 两个工具中的系统级 Skill 内容一致。
- 仓库 `.claude/skills/` 无变化。
- 可通过 `cc-switch skills disable <skill_id>` 回滚启用状态。

### 第 7 步：再试点一个 MCP 依赖 Skill

目标：验证 MCP 作为条件依赖的同步流程。

流程：

1. 在 Skill 元数据中声明 `requires_mcp`。
2. 先运行 MCP validate。
3. 对目标工具启用 MCP。
4. 同步 MCP。
5. 再启用和同步 Skill。
6. 失败时阻断 Skill 启用，并输出依赖缺失原因。

验收标准：

- MCP 未通过时 Skill 不启用。
- MCP 通过后 Skill 才同步。
- 审计能复现依赖关系。

### 第 8 步：决定是否扩展到仓库级 Skill

目标：在试点稳定后，再评估 `repo-local` 是否需要 `cc-switch` 参与。

开放条件：

- 已有元数据。
- 已有漂移审计。
- 已有同步白名单。
- 已有回滚路径。
- 明确不会覆盖 PR 管理下的仓库文件。

可选模式：

- 只读导入：`cc-switch` 只识别仓库级 Skill，不写回。
- 显式导出：用户手动把某个仓库级 Skill 导出为系统级副本。
- 禁止自动覆盖：任何从用户目录写回仓库的动作都必须走 PR。

验收标准：

- 仓库级 Skill 的权威源仍在 Git。
- 用户级同步不会静默改变仓库行为。
- 任何仓库文件变更都能通过 PR、CODEOWNERS 和治理门禁追踪。

## 验证清单

实施到代码或配置阶段后，至少运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

如只修改设计文档，也应至少运行 pathref 检查。

## 风险与处理

| 风险 | 处理 |
| --- | --- |
| 系统级 Skill 覆盖仓库级 Skill | 默认禁止 `repo-local` 自动同步 |
| MCP 配置失败导致 Skill 不可用 | `requires_mcp` 作为前置门禁 |
| 多工具入口重复规则 | 入口继续按 ADR 0005 分层 |
| 用户级目录手工修改导致漂移 | 用 `last_sync_hash` 和审计发现 |
| cc-switch 行为升级导致同步路径变化 | 同步前记录 `cc-switch --version` 和 `cc-switch config path` |

## 当前结论

- 系统级 Skill 可以通过 `cc-switch` 在多个工具间保持同步。
- MCP 同步不是必须项，只在 Skill 有 MCP 依赖时作为前置条件。
- 仓库级 Skill 目前不建议通过 `cc-switch` 自动同步，应继续由仓库 Git 流程管理。
