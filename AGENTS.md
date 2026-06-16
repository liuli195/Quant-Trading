# AGENTS.md

本仓库是基于 Python 的 A 股/场内基金量化策略仓库，交易与回测环境为聚宽 JoinQuant。

## 通用入口

本仓库按 single-context 处理：[规则文档](docs/rules/index.md) <!-- pathref: docs/rules/index.md --> 和 [openspec/specs](openspec/specs) <!-- pathref: openspec/specs --> 共同作为领域上下文。ADR 已归档到 openspec。详见 [domain.md](docs/agents/domain.md) <!-- pathref: docs/agents/domain.md -->。

## 核心规则
- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。

## 通用规则

### 决策跟踪器

- **Issue 跟踪**：Issue 和 PRD 统一记录在 GitHub Issues：`liuli195/Quant-Trading`。详见 [issue-tracker.md](docs/agents/issue-tracker.md) <!-- pathref: docs/agents/issue-tracker.md -->。
- **Triage 标签**：使用默认五类 triage 标签。详见 [triage-labels.md](docs/agents/triage-labels.md) <!-- pathref: docs/agents/triage-labels.md -->。

### 环境与工具

- **运行边界**：策略只在聚宽云端运行；本地只做编写、测试、文档和回测分析。环境差异见 [environments.md](docs/rules/environments.md) <!-- pathref: docs/rules/environments.md -->。
- **Python**：默认必须提权使用项目 `.venv`，不改用系统 Python。命令见 [commands.md](docs/rules/commands.md) <!-- pathref: docs/rules/commands.md -->。
- **GitHub CLI**：`gh` CLI 默认提权执行，避免丢失沙箱外登录态。
- **长期记忆**：本项目使用 agentmemory 作为 Claude Code 与 Codex 共享长期记忆系统；读写长期项目记忆时优先用已安装的 agentmemory 技能/MCP 工具，禁止记录密钥、token、密码和个人隐私。官方入口见 [rohitg00/agentmemory](https://github.com/rohitg00/agentmemory)。

### 工作边界

- **先行调查**：不推测未读代码；不确定时说明并验证。
- **执行边界**：只执行用户显式授权的操作；未授权时默认先给方案或计划等待确认，禁止自行决策并执行任何改动（包括安装包、修改配置、重构、删除、提交、切换分支、启停服务等）；`auto` 权限模式不视为授权，仅影响单次工具调用的确认流程。
- **文件规范**：优先编辑现有文件，非必要不新建；任务后清理临时产物。
- **效率**：独立任务并行，默认用户持续显式授权，优先派发子 agent 工具；该授权显式覆盖 `sub-agents`、`delegation` 和 `parallel agent work` 触发词；主会话负责编排、确认、汇总和验证；无法分发时说明原因。
- **ADR 落盘**：重大决策讨论结束后必须在本地 ADR 中落盘决策，并在 ADR 中引用 GitHub 源 Issue。

### Git 与 PR

- **Git**：分支名使用 ASCII 模板，提交说明用简体中文。
- **PR 纪律**：进入主干须通过 PR；用户显式授权才可直写主干；禁止把功能分支本地合入 `main`。细则见 [pr-workflow.md](docs/rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。
- **安全性**：破坏性操作前需确认，包括强制推送、硬重置、`--no-verify`；PR 合并授权包含清理已合并分支。

### Review 与验证

- **review 指南**：Review 前必须先阅读并遵守 [review-guidelines.md](docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->。
- **完成验证**：逐项复核要求，说明已验证与无法验证的部分；日常小改跑 `verify fast`；PR 提交走 `pr-submit`，不把本地 `verify full` 作为前置证据；pre-push 只做主干保护和 local review fragments freshness 提醒，最终合并证据以 GitHub `Research Governance / verify-full` 为准。

### 输出与引用

- **输出**：简体中文，简洁直白，别说废话；英文技术名词后面跟（中文简体释义）。
- **内部引用**：使用“可点击链接 + `pathref` 注释”双轨格式。
