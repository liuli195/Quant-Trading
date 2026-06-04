# 跨 AI 工具 Skill 管理实施计划

## 目标

建立一套可扩展的跨 AI 工具 Skill 管理流程，让系统级 Skill 可以通过 `cc-switch` 在 Claude Code、Codex、Gemini、OpenCode 等工具间同步，同时保留本仓库的规则入口、仓库级 Skill、MCP 和治理门禁边界。

## 已知事实

- `cc-switch` 已支持跨应用管理 Skills、MCP 和 prompts，说明见 [cc-switch-cli.md](cc-switch-cli.md) <!-- pathref: docs/design/cc-switch-cli.md -->。
- 本仓库的 AI 通用入口是 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；Claude Code 专属入口是 [CLAUDE.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。
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
  .agents/skills/
        |
        | Git + PR + governance gate
        v
本仓库 Claude Code Symlink 与 Codex 仓库级 Skill

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
- 读取 `.agents/skills/`，把本仓库 Skill 先标记为 `repo-local`；`.claude/skills` 只作为生成后的 Symlink。
- 输出一份盘点表，列出 Skill 名称、来源、目标工具、是否依赖 MCP、是否适合系统级复用。

验收标准：

- 能区分 `global` 和 `repo-local`。
- 不产生跨工具写入。
- 不覆盖 `.claude/skills/`。

#### 第 1 步产出：现状盘点

执行范围：只读盘点，不执行 `cc-switch skills sync`，不写入各工具用户级目录，也不修改 [.agents/skills](../../.agents/skills) <!-- pathref: repo/.agents/skills -->。

命令结果：

| 命令 | 结果 | 结论 |
| --- | --- | --- |
| `cc-switch skills scan-unmanaged` | `No unmanaged skills found.` | 当前未发现用户级工具目录里的未管理 Skill。 |
| `cc-switch skills list` | `No installed skills found.` | `cc-switch` SSOT 当前没有已安装的系统级 Skill。 |
| `cc-switch --app claude skills scan-unmanaged` | `No unmanaged skills found.` | `cc-switch` 没有把 Claude Code 用户 Skill 或插件 Skill 当成未管理 Skill。 |
| `cc-switch --app claude skills list` | `No installed skills found.` | Claude 目标应用下也没有 `cc-switch` 已安装 Skill。 |
| `cc-switch --app codex skills scan-unmanaged` | `No unmanaged skills found.` | `cc-switch` 没有把 Codex 运行时内置 Skill 或插件缓存 Skill 当成未管理 Skill。 |
| `cc-switch --app codex skills list` | `No installed skills found.` | Codex 目标应用下也没有 `cc-switch` 已安装 Skill。 |
| 磁盘盘点 `C:\Users\liuli\.claude\skills` | 3 个 `SKILL.md` | Claude Code 用户级 Skill 目录存在独立 Skill，但不在 `cc-switch` SSOT 中。 |
| 磁盘盘点 `C:\Users\liuli\.claude\plugins\installed_plugins.json` | 1 个已安装插件 | 已安装 `chrome-devtools-mcp@claude-plugins-official` 1.0.1。 |
| 磁盘盘点 `C:\Users\liuli\.claude\plugins\cache\...\chrome-devtools-mcp\1.0.1` | 6 个 `SKILL.md` | 已安装 Claude 插件自带 6 个 Skill，由 Claude Code 插件运行时管理。 |
| 磁盘盘点 `C:\Users\liuli\.claude\plugins\marketplaces` | 34 个 `SKILL.md` | marketplace 中有可用插件 Skill，但这些目录不等同于已安装插件。 |
| 磁盘盘点 `C:\Users\liuli\.codex\skills` | 6 个 `SKILL.md` | Codex 用户/系统 Skill 目录存在独立 Skill，但不在 `cc-switch` SSOT 中。 |
| 磁盘盘点 `C:\Users\liuli\.codex\plugins\cache` | 38 个非 fixture `SKILL.md` | Codex 插件自带 Skill 存在于插件缓存，由 Codex 插件运行时管理，不属于 `cc-switch skills scan-unmanaged` 的发现结果。 |

`cc-switch` 系统级盘点：

| Skill 名称 | 来源 | 目标工具 | 是否依赖 MCP | 是否适合系统级复用 |
| --- | --- | --- | --- | --- |
| 无 | `cc-switch` SSOT | 未配置 | 否 | 暂无 `cc-switch` 管理对象；第二步应先定义准入规则，再决定是否安装系统级 Skill。 |

Claude Code 运行时 / 插件 Skill 盘点：

| Skill 组 | 来源 | 目标工具 | 是否依赖 MCP | 是否适合系统级复用 |
| --- | --- | --- | --- | --- |
| Claude 用户级 Skill（`create-skill`、`setup-autochrome`、`setup-mcp`） | `C:\Users\liuli\.claude\skills\` | Claude Code 用户级 | `setup-mcp` 和 `setup-autochrome` 涉及 MCP/浏览器配置；`create-skill` 未声明 MCP | 不通过 `cc-switch` 复制；属于用户级 Claude Code 配置，若要复用应先转成 `cc-switch` SSOT 或明确只读导入规则。 |
| 已安装插件 `chrome-devtools-mcp@claude-plugins-official` 1.0.1 | `C:\Users\liuli\.claude\plugins\cache\claude-plugins-official\chrome-devtools-mcp\1.0.1\` | Claude Code 插件 | 依赖 Chrome DevTools MCP 插件运行时 | 不通过 `cc-switch` 复制；由 Claude Code 插件安装状态管理。 |
| `chrome-devtools-mcp` 插件 Skill（`a11y-debugging`、`chrome-devtools`、`chrome-devtools-cli`、`debug-optimize-lcp`、`memory-leak-debugging`、`troubleshooting`） | 已安装插件目录 `skills/` | Claude Code 插件 | 依赖 Chrome DevTools MCP 工具或 CLI | 不通过 `cc-switch` 复制；跨工具复用需单独处理 MCP、CLI 和浏览器依赖。 |
| Claude 插件 marketplace Skill | `C:\Users\liuli\.claude\plugins\marketplaces\` | Claude Code 可安装插件来源 | 取决于具体插件 | marketplace 是可用来源，不是当前已安装插件；第二步不应把 marketplace Skill 当成已启用能力。 |

Codex 运行时 / 插件 Skill 盘点：

| Skill 组 | 来源 | 目标工具 | 是否依赖 MCP | 是否适合系统级复用 |
| --- | --- | --- | --- | --- |
| Codex 系统 Skill（`imagegen`、`openai-docs`、`plugin-creator`、`skill-creator`、`skill-installer`） | `C:\Users\liuli\.codex\skills\.system\` | Codex 运行时 | 未在 Skill 元数据中声明 MCP | 不通过 `cc-switch` 复制；这是 Codex 自带系统能力。 |
| `playwright` | `C:\Users\liuli\.codex\skills\playwright\SKILL.md` | Codex 运行时 | 未在 Skill 元数据中声明 MCP | 暂不纳入 `cc-switch`；如要跨工具复用，应先确认浏览器/CLI 依赖。 |
| Browser / Chrome 插件 Skill | `C:\Users\liuli\.codex\plugins\cache\openai-bundled\...\skills\` | Codex 插件 | 依赖对应插件运行时，不是 `cc-switch mcp` 依赖 | 不通过 `cc-switch` 复制；由插件安装状态决定。 |
| CircleCI 插件 Skill（4 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\circleci\...\skills\` | Codex 插件 | 依赖对应插件/CLI 能力 | 不通过 `cc-switch` 复制；跨工具复用需单独评估。 |
| Codex Security 插件 Skill（6 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\codex-security\...\skills\` | Codex 插件 | 依赖对应插件流程 | 不通过 `cc-switch` 复制；跨工具复用需单独评估。 |
| GitHub 插件 Skill（4 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\github\...\skills\` | Codex 插件 | 依赖 GitHub 插件、GitHub App 或 `gh` | 不通过 `cc-switch` 复制；跨工具复用需单独评估授权和工具链。 |
| Plugin Eval 插件 Skill（5 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\plugin-eval\...\skills\` | Codex 插件 | 依赖对应插件能力 | 不通过 `cc-switch` 复制；跨工具复用需单独评估。 |
| Superpowers 插件 Skill（15 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\superpowers\...\skills\` | Codex 插件 | 依赖 Codex 技能调度能力，不是 `cc-switch mcp` 依赖 | 不通过 `cc-switch` 复制；当前作为 Codex 插件能力使用。 |
| Documents / Presentations / Spreadsheets 插件 Skill（3 个） | `C:\Users\liuli\.codex\plugins\cache\openai-primary-runtime\...\skills\` | Codex 插件 | 依赖对应运行时插件 | 不通过 `cc-switch` 复制；跨工具复用需单独评估运行时依赖。 |

仓库级盘点：

| Skill 名称 | 来源 | 目标工具 | 是否依赖 MCP | 是否适合系统级复用 |
| --- | --- | --- | --- | --- |
| `agent-doc-add` | 旧 `.claude/skills/agent-doc-add`，已迁移到 `skill-system` | Claude Code 仓库级 | 否 | 暂不直接复用；当前依赖本仓库 `AGENTS.md`、`CLAUDE.md`、索引和治理规则，可在后续抽取通用“入口文档新增”方法。 |
| `agent-doc-refactor` | 旧 `.claude/skills/agent-doc-refactor`，已迁移到 `skill-system` | Claude Code 仓库级 | 否 | 暂不直接复用；当前依赖本仓库入口分层、索引和治理扫描，可在后续抽取通用“入口文档重构”方法。 |
| `jq-ab-test` | 旧 `.claude/skills/jq-ab-test`，已迁移到 `strategy-experiment` | Claude Code 仓库级 | 否 | 否；依赖 JoinQuant、策略变体库、云端额度和本仓库脚本。 |
| `jq-analyze` | 旧 `.claude/skills/jq-analyze`，已迁移到 `research-report-analysis` | Claude Code 仓库级 | 否 | 否；依赖本仓库回测产物目录、报告模板和 JoinQuant 数据结构。 |
| `jq-fix` | 旧 `.claude/skills/jq-fix`，已迁移到 `joinquant-strategy-fix` | Claude Code 仓库级 | 否 | 否；依赖本仓库策略代码、测试和 JoinQuant 错误处理流程。 |
| `jq-param-scan` | 旧 `.claude/skills/jq-param-scan`，已迁移到 `strategy-experiment` | Claude Code 仓库级 | 否 | 否；依赖 `jq-run`、云端额度、扫描配置和本仓库报告模板。 |
| `jq-research` | 旧 `.claude/skills/jq-research`，已迁移到 `research-local-first` | Claude Code 仓库级 | 否 | 否；依赖 `scripts.research.cli`、研究项目结构、候选漏斗和治理审计。 |
| `jq-run` | 旧 `.claude/skills/jq-run`，已迁移到 `joinquant-cloud-run` | Claude Code 仓库级 | 否 | 否；依赖 `jq-auto`、JoinQuant 云端、Playwright 自动化和本仓库脚本路径。 |

第一步结论：

- `cc-switch-global` 当前为空：`cc-switch` 没有已安装系统级 Skill，也没有发现它能管理的未管理 Skill。
- `claude-runtime/plugin-managed` 不为空：Claude Code 用户目录中有 3 个用户级 Skill，已安装插件 `chrome-devtools-mcp` 1.0.1 带 6 个 Skill；marketplace 还有 34 个可用 Skill，但不代表已安装。
- `codex-runtime/plugin-managed` 不为空：Codex 系统目录和插件缓存中存在多组 Skill，但它们由 Codex 运行时或插件安装状态管理，不属于 `cc-switch` SSOT。
- `repo-local` 当前为仓库内 `.agents/skills` SSOT，`.claude/skills` 是生成后的 Symlink，权威源仍在仓库 Git。
- 当前仓库级 Skill 均未声明 MCP 依赖；`jq-run` 明确使用 Playwright CLI，不再使用 MCP Chrome DevTools。
- 第二步应使用四层分类：`cc-switch-global`、`claude-runtime/plugin-managed`、`codex-runtime/plugin-managed`、`repo-local`。旧仓库 Skill 已迁移为 `.agents/skills` SSOT 与 `.claude/skills` Symlink，再单独讨论 `agent-doc-add` 和 `agent-doc-refactor` 是否能抽取出系统级通用版本。

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

#### 第 2 步产出：分层规则和当前归类

执行范围：只定义分层和准入结论，不执行 `cc-switch skills sync`，不导入运行时或插件 Skill，不修改 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 或 [CLAUDE.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

分层定义：

| 层级 | 权威来源 | 管理方式 | 当前结论 |
| --- | --- | --- | --- |
| `cc-switch-global` | `cc-switch` SSOT，例如 `~/.cc-switch/skills/` | 通过 `cc-switch skills install/enable/sync` 管理 | 当前为空；只接收已经显式安装到 SSOT、带元数据、可跨至少两个工具复用的 Skill。 |
| `claude-runtime/plugin-managed` | Claude Code 用户目录或插件目录 | 由 Claude Code 用户配置或插件安装状态管理 | 不自动导入 `cc-switch`；只作为只读盘点对象。 |
| `codex-runtime/plugin-managed` | Codex 系统 Skill 或插件缓存 | 由 Codex 运行时或插件安装状态管理 | 不自动导入 `cc-switch`；只作为只读盘点对象。 |
| `repo-local` | 本仓库 [.agents/skills](../../.agents/skills) <!-- pathref: repo/.agents/skills --> | 通过 Git、PR、CODEOWNERS 和治理门禁管理 | 当前仓库 Skill 全部保持在此层，不允许被用户级 `cc-switch skills sync` 自动覆盖。 |

`cc-switch-global` 准入规则：

- 必须有稳定 `id`、`owner`、`lifecycle`、`target_apps`、`requires_mcp`、`source` 和 `sync_method` 元数据。
- 必须能脱离本仓库路径、策略目录、JoinQuant 云端流程和本仓库治理门禁独立运行。
- 必须明确目标工具，且至少有两个目标工具具备相同或等价能力。
- 如果依赖 MCP、CLI、浏览器或插件运行时，必须先进入第 3 步的依赖校验，不得只复制 Skill 正文。
- 运行时内置 Skill、插件自带 Skill、marketplace 可用 Skill 不等于系统级可同步 Skill；除非先转成受管 SSOT 副本，否则不进入 `cc-switch-global`。

`repo-local` 保留规则：

- 依赖本仓库路径、脚本、策略代码、报告模板、研究平台、JoinQuant 云端额度或治理审计的 Skill 必须留在 `repo-local`。
- `repo-local` 的权威文件是 `.agents/skills/**/SKILL.md` 和同目录 `references/ownership.yaml`；`.claude/skills/<同名>/SKILL.md` 只作为 Symlink 输出，变更必须先改 `.agents/skills` 并走仓库 Git diff 和 PR 流程。
- `repo-local` 未来若要跨工具复用，只能先做只读导入或显式导出副本；不得从用户级目录写回仓库。
- 入口文件继续按 ADR 0005 分层：[AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只保留通用入口，[CLAUDE.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md --> 只保留 Claude Code 专属指针。

旧仓库 Skill 迁移归类：

| Skill | 迁移前层级 | 判定依据 | 后续处理 |
| --- | --- | --- | --- |
| `agent-doc-add` | `repo-local` | 依赖本仓库 `AGENTS.md`、`CLAUDE.md`、规则索引、ADR 索引、pathref 和治理扫描。 | 暂不直接同步；后续可抽取通用“入口文档新增”方法，作为新的系统级 Skill 候选。 |
| `agent-doc-refactor` | `repo-local` | 依赖本仓库入口分层、规则文档、索引和治理检查。 | 暂不直接同步；后续可抽取通用“入口文档重构”方法，作为新的系统级 Skill 候选。 |
| `jq-ab-test` | `repo-local` | 依赖策略变体库、JoinQuant 云端额度、`jq-run` 和本仓库 A/B 报告结构。 | 不纳入系统级同步。 |
| `jq-analyze` | `repo-local` | 依赖本仓库回测产物、报告模板、`tabs_raw` 和 JoinQuant 数据结构。 | 不纳入系统级同步。 |
| `jq-fix` | `repo-local` | 依赖本仓库策略代码、测试、JoinQuant 错误处理和本地验证流程。 | 不纳入系统级同步。 |
| `jq-param-scan` | `repo-local` | 依赖 `jq-run`、扫描配置、云端额度和本仓库报告模板。 | 不纳入系统级同步。 |
| `jq-research` | `repo-local` | 依赖 `scripts.research.cli`、研究项目结构、候选漏斗、治理审计和云端交接规则。 | 不纳入系统级同步。 |
| `jq-run` | `repo-local` | 依赖 `jq-auto`、JoinQuant 云端、Playwright 自动化和本仓库脚本路径。 | 不纳入系统级同步；其 Playwright 依赖不是 MCP 依赖。 |

第二步结论：

- 当前没有任何现有 Skill 被提升为 `cc-switch-global`。
- 当前 `.agents/skills` SSOT 与 `.claude/skills` Symlink 全部明确归为 `repo-local`。
- `agent-doc-add` 和 `agent-doc-refactor` 只有方法论可抽取为系统级候选，旧 Skill 文件已迁移并删除。
- Claude / Codex 运行时和插件 Skill 均不自动导入 SSOT，后续若要复用必须先做元数据、依赖和授权评估。
- 验收标准已满足：每个现有仓库 Skill 已有明确层级；入口文件不需要新增大段 Skill 细节；`CLAUDE.md` 继续只保留 Claude 专属指针。

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

#### 第 3 步产出：依赖门禁与插件 Skill 准入评估

执行范围：只读研究，不执行 `cc-switch skills sync`，不从插件缓存导入 Skill，不写入 `~/.cc-switch/skills/`，也不修改任何工具用户级目录。

命令结果：

| 命令 | 结果 | 结论 |
| --- | --- | --- |
| `cc-switch --version` | `cc-switch 5.5.0` | 当前研究基于 5.5.0 行为。 |
| `cc-switch skills list` | `No installed skills found.` | `cc-switch-global` 仍为空。 |
| `cc-switch --app codex skills list` | `No installed skills found.` | Codex 目标应用下没有 `cc-switch` 已安装 Skill。 |
| `cc-switch mcp list` | `No MCP servers found.` | 当前没有可由 `cc-switch mcp` 审计的 MCP 依赖。 |

第 3 步结论需要扩展：这些插件 Skill 大多不是 MCP 依赖，而是 CLI、连接器、插件运行时或 Agent 能力依赖。只看 `requires_mcp` 会误判。

新增依赖字段建议：

| 字段 | 含义 | 示例 |
| --- | --- | --- |
| `requires_mcp` | 由 `cc-switch mcp` 管理的 MCP server id | 当前评估对象均未确认需要此字段。 |
| `requires_cli` | 本机命令行工具 | `npx`、`playwright-cli`、`circleci`、`chunk-cli`、`gh`、`git`、`python`。 |
| `requires_app_connector` | 工具内置或插件提供的连接器 | GitHub 插件的 GitHub app connector。 |
| `requires_plugin_runtime` | 必须由特定插件加载的运行时能力 | Codex 插件 Skill、GitHub 插件 Skill、Superpowers Skill 调度。 |
| `requires_agent_feature` | Agent 平台能力 | Skill 调用、Todo 列表、子 Agent、工作区隔离。 |
| `distribution_unit` | 同步单位 | `single-skill` 或 `bundle`。 |
| `permission_scope` | 权限边界 | 只读、本地写入、远端读写、推送/PR、CI 触发。 |

逐组准入判断：

| Skill 组 | 当前来源 | 主要依赖 | 是否可直接进入 `cc-switch-global` | 建议 |
| --- | --- | --- | --- | --- |
| `playwright` | `C:\Users\liuli\.codex\skills\playwright\SKILL.md` | `npx`、`@playwright/cli`、`playwright_cli.sh`、浏览器运行环境 | 否 | 可作为第 6 步“无 MCP 试点”候选，但需先改造成与 Codex 路径无关、Windows/macOS/Linux 都可用的 `cc-switch` SSOT 副本。 |
| CircleCI 插件 Skill（4 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\circleci\...\skills\` | CircleCI CLI、Chunk CLI/UI、CircleCI token、组织权限、可能的 GitHub App | 否 | `circleci-builds` 和 `circleci-config` 可抽成通用流程型 Skill；`circleci-cli` 和 `chunk` 必须声明 CLI、认证和远端写入权限。 |
| Codex Security 插件 Skill（6 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\codex-security\...\skills\` | Codex Security 插件流程、跨 Skill 编排、扫描产物路径、仓库读写；插件许可为 Proprietary | 否 | 不应从插件缓存复制到 `cc-switch-global`。若要复用，只能由权利方发布受管 bundle，并先去掉 Codex 专属假设或限制 `target_apps`。 |
| GitHub 插件 Skill（4 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\github\...\skills\` | GitHub app connector、`gh` CLI、`gh` auth、网络、GitHub Actions API、本地 `git` | 否 | 不能只同步 Skill 正文；需先让 `cc-switch` 能表达 `requires_app_connector=github` 和 `requires_cli=gh`，并区分只读与远端写操作。 |
| Superpowers 插件 Skill（15 个） | `C:\Users\liuli\.codex\plugins\cache\openai-curated\superpowers\...\skills\` | Skill 调用机制、子 Agent、Todo 列表、工作区/分支操作、平台工具映射 | 否 | 最适合做“整包受管候选”，但不能按单个 Skill 零散导入；必须以 bundle 方式保留内部依赖和平台降级规则。 |

细分评估：

| Skill | 主要依赖 | 直接准入结论 | 后续处理 |
| --- | --- | --- | --- |
| `playwright` | `npx`、`@playwright/cli`、`playwright_cli.sh`、`CODEX_HOME` 路径 | 否 | 抽取跨平台版本后，可做无 MCP 试点。 |
| `circleci-builds` | CircleCI pipeline/job 信息、日志、可能的 CLI 或 UI | 否 | 可抽通用诊断流程，但要声明 CircleCI 服务依赖。 |
| `chunk` | Chunk UI、`chunk-cli`、token、组织级开关、GitHub App | 否 | 需声明 beta 状态、认证和远端权限；暂不进全局。 |
| `circleci-cli` | `circleci` CLI、token/auth、项目权限、远端 rerun/trigger | 否 | 需 `requires_cli=circleci` 和权限门禁。 |
| `circleci-config` | `.circleci/config.yml`、CI 指标、CircleCI 配置语义 | 否 | 可抽通用流程型 Skill，但当前仍是插件缓存副本。 |
| `security-scan` | Codex Security 分阶段编排、其他 4 个安全分析 Skill、扫描产物路径 | 否 | 只能作为安全扫描 bundle 的入口，不能单独导入。 |
| `threat-model` | 仓库级安全上下文、扫描产物路径、报告写入 | 否 | 可移植方法论，但需去 Codex 化和路径元数据。 |
| `finding-discovery` | 仓库读文件工具、安全扫描上下文、报告写入 | 否 | 需作为 bundle 内部阶段管理。 |
| `validation` | 构建/测试/PoC 工具、验证产物路径、仓库写入 | 否 | 需声明本地写入和测试执行权限。 |
| `attack-path-analysis` | 威胁模型、验证结果、报告写入，可能使用网络确认上下文 | 否 | 需作为 bundle 内部阶段管理。 |
| `fix-finding` | 代码编辑、回归测试、验证产物 | 否 | 属于高风险写操作 Skill，不能自动全局启用。 |
| `github` | GitHub app connector、`gh` fallback、本地 `git` | 否 | 等 `cc-switch` 支持连接器依赖后再评估。 |
| `gh-address-comments` | GitHub app、`gh api graphql`、bundled script、网络 | 否 | 需要连接器和 `gh` 双门禁。 |
| `gh-fix-ci` | GitHub app、`gh`、GitHub Actions 日志、bundled script | 否 | 需要 `requires_cli=gh`、Actions 权限和网络门禁。 |
| `yeet` | 本地 `git`、`gh`、GitHub app、push、draft PR | 否 | 远端写操作，必须保持显式授权流程。 |
| `brainstorming` | Skill 调用链、后续 `writing-plans` | 否 | 可作为 Superpowers bundle 内部 Skill。 |
| `dispatching-parallel-agents` | 子 Agent 能力、并行任务调度 | 否 | 仅目标工具明确支持子 Agent 时可启用。 |
| `executing-plans` | Todo 列表、验证步骤、可选子 Agent、`finishing-a-development-branch` | 否 | 需平台能力映射，作为 bundle 管理。 |
| `finishing-a-development-branch` | `git`、分支/PR/工作区清理、用户选择 | 否 | 涉及合并、删除分支、推送，不能默认启用写操作。 |
| `receiving-code-review` | 代码审查上下文、验证流程 | 否 | 可作为通用方法论，但需保留 Superpowers 触发规则。 |
| `requesting-code-review` | 子 Agent 审查流程 | 否 | 仅目标工具支持子 Agent 时可启用。 |
| `subagent-driven-development` | 子 Agent、Todo 列表、两阶段审查、其他 Superpowers Skill | 否 | 必须 bundle 管理，不能单独同步。 |
| `systematic-debugging` | 调试流程、验证 Skill | 否 | 可作为通用方法论，但当前仍属插件运行时。 |
| `test-driven-development` | 测试运行、实现修改、验证 | 否 | 可作为通用方法论，但需目标工具有等价编辑/测试能力。 |
| `using-git-worktrees` | `git worktree`、分支创建、目录忽略检查、沙箱权限 | 否 | 需显式用户授权和平台工作区规则。 |
| `using-superpowers` | Skill 加载机制、平台工具映射 | 否 | 只能作为 Superpowers bundle 的入口。 |
| `verification-before-completion` | 验证命令、测试证据 | 否 | 可作为通用方法论，但需绑定目标工具命令执行能力。 |
| `writing-plans` | 计划文档、子 Agent 或执行计划 Skill | 否 | 可作为 bundle 内部流程。 |
| `writing-skills` | Skill 编写规范、子 Agent 测试、示例/模板 | 否 | 可移植，但需目标工具支持 Skill 格式和测试方法。 |

第三步结论：

- 当前评估对象都不应“直接”进入 `cc-switch-global`；原因不是 MCP 缺失，而是它们还没有被转成 `cc-switch` SSOT 副本，也没有依赖元数据。
- `playwright` 是最适合做下一步无 MCP 小试点的候选，但当前文件硬编码 Codex 用户目录和 shell wrapper，不能原样同步。
- CircleCI 和 GitHub 属于外部服务 Skill，必须先把 CLI、认证、网络和远端写权限纳入门禁。
- Codex Security 和 Superpowers 都应按 bundle 管理，不能拆成单个 Skill 零散同步。
- 第 4 步设计同步命令时，应把 `requires_cli`、`requires_app_connector`、`requires_plugin_runtime`、`requires_agent_feature` 与 `requires_mcp` 一起纳入同步前置检查。

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
# 在仓库内通过 PR 修改 .agents/skills/<skill>/SKILL.md
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
- `CLAUDE.md` 只保留 Claude Code 专属指针，并继续引用 `.claude/skills` Symlink。
- `.agents/skills/**/SKILL.md` 与 `references/ownership.yaml` 是仓库级 Skill 的权威文件；`.claude/skills/**/SKILL.md` 只作为 Symlink 输出。
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
- 仓库 `.agents/skills/` 与 `.claude/skills` Symlink 无变化。
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
- 第三步已确认：插件 Skill 的主要风险不是 MCP，而是 CLI、连接器、插件运行时、Agent 能力和远端权限依赖。
- 当前重点评估的 30 个 Skill 均不直接进入 `cc-switch-global`；`playwright` 可作为无 MCP 试点候选，Superpowers 可作为 bundle 候选。
- 仓库级 Skill 目前不建议通过 `cc-switch` 自动同步，应继续由仓库 Git 流程管理。
- 第二步已确认：当前仓库级 `.agents/skills` Skill 全部为 `repo-local`，暂不提升为 `cc-switch-global`。
