# AGENTS.md

本仓库是基于 Python 的 A 股/场内基金量化策略仓库，交易与回测环境为聚宽 JoinQuant。

## 通用入口

本文件是所有 AI 编码助手的通用入口；根文档索引见 [indexes.md](indexes.md) <!-- pathref: repo/indexes.md -->。

Claude Code 专属补充见 [CLAUDE.md](CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->。

## 通用规则

- **输出**：简体中文，简洁直白。
- **运行边界**：策略代码仅运行于聚宽云端；本地负责编写、测试、文档、回测分析。环境差异及库白名单见 [environments.md](docs/rules/environments.md) <!-- pathref: docs/rules/environments.md -->。
- **Python 环境**：须走项目 `.venv`，相关 Python 命令默认提权执行。命令参考 [commands.md](docs/rules/commands.md) <!-- pathref: docs/rules/commands.md -->。
- **先调查**：不推测未读代码；不确定时说明并提出验证方法。
- **请求范围**：只做要求的事，不明确时默认研究建议。不擅自重构或过度抽象。
- **完成前验证**：逐项复核要求，跑测试与检查，说明已验证和无法验证的部分。
- **PR 纪律**：进入主干须通过 PR；用户显式授权可直写主干。禁止本地合并主干。细则见 [pr-workflow.md](docs/rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。
- **Git**：分支名和提交说明使用简体中文。
- **文件规范**：优先编辑现有文件，非必要不新建。任务后清理临时产物。
- **安全性**：破坏性操作前需确认（删除/强制推送/硬重置/`--no-verify`）。
- **效率**：优先派发子 agent，主会话负责编排、确认、汇总、验证。无法分发时说明原因。独立任务并行，有依赖串行。
- **内部引用**：使用”可点击链接 + `pathref` 注释”双轨格式。

## Review guidelines

Before reviewing, read and apply [review-guidelines.md](docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->. If you cannot access that file, treat the review as blocked.
