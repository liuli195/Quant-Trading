# AGENTS.md

本仓库是基于 Python 的 A 股/场内基金量化策略仓库，交易与回测环境为聚宽 JoinQuant。

## 通用入口

本仓库按 single-context 处理：[规则文档](docs/rules/index.md) <!-- pathref: docs/rules/index.md --> 和 [ADR 索引](docs/adr/index.md) <!-- pathref: docs/adr/index.md --> 共同作为领域上下文。详见 [domain.md](docs/agents/domain.md) <!-- pathref: docs/agents/domain.md -->。

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
- **请求范围**：只做要求的事；不明确时默认先给研究建议；不擅自重构或过度抽象。
- **文件规范**：优先编辑现有文件，非必要不新建；任务后清理临时产物。
- **效率**：独立任务并行，优先派发子 agent；主会话负责编排、确认、汇总和验证；无法分发时说明原因。

### Git 与 PR

- **Git**：分支名使用 ASCII 模板，提交说明用简体中文。
- **PR 纪律**：进入主干须通过 PR；用户显式授权才可直写主干；禁止把功能分支本地合入 `main`。细则见 [pr-workflow.md](docs/rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。
- **安全性**：破坏性操作前需确认，包括强制推送、硬重置、`--no-verify`；PR 合并授权包含清理已合并分支。

### Review 与验证

- **review 指南**：Review 前必须先阅读并遵守 [review-guidelines.md](docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->。
- **完成验证**：逐项复核要求，说明已验证与无法验证的部分；日常小改跑 `verify fast`，PR 准备、push 前、CI 和最终交付跑 `verify full`。

### 输出与引用

- **输出**：简体中文，简洁直白，别说废话。
- **内部引用**：使用“可点击链接 + `pathref` 注释”双轨格式。
