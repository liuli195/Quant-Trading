# AGENTS.md

本仓库是基于 Python 的 A 股/场内基金量化策略仓库，交易与回测环境为聚宽 JoinQuant。

## 通用入口

本文件是所有 AI 编码助手的通用入口；根文档索引见 [indexes.md](indexes.md) <!-- pathref: repo/indexes.md -->。

Claude Code 专属补充见 [CLAUDE.md](CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->。

## 核心规则
- **规则优先**：仓库规则最优先是元规则。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权，否则不得执行。

## 通用规则

- **运行边界**：策略代码仅运行于聚宽云端；本地负责编写、测试、文档、回测分析。环境差异及库白名单见 [environments.md](docs/rules/environments.md) <!-- pathref: docs/rules/environments.md -->。
- **Python 环境**：默认必须提权使用项目 `.venv`，不改用系统 Python。命令参考 [commands.md](docs/rules/commands.md) <!-- pathref: docs/rules/commands.md -->。
- **GitHub CLI**：`gh` CLI 默认提权执行，否则无法获取沙箱外的登录状态。
- **Git**：分支名使用 ASCII 模板，提交说明使用简体中文。
- **先行调查**：不推测未读代码；不确定时说明并提出验证方法。
- **请求范围**：只做要求的事，不明确时默认研究建议。不擅自重构或过度抽象。
- **文件规范**：优先编辑现有文件，非必要不新建。任务后清理临时产物。
- **review 指南**：Review 前必须先阅读并遵守 [review-guidelines.md](docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->
- **完成验证**：逐项复核要求，跑对应测试、治理并说明已验证与无法验证的部分。日常小改跑 `verify fast`；PR 准备、push 前、CI 及最终交付跑 `verify full`。
- **PR 纪律**：进入主干须通过 PR；用户显式授权可直写主干。禁止把功能分支本地合入 `main`。细则见 [pr-workflow.md](docs/rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。
- **安全性**：破坏性操作前需确认（强制推送/硬重置/`--no-verify`）；PR 合并授权包含清理已合并分支。
- **效率**：优先派发子 agent，主会话负责编排、确认、汇总、验证。无法分发时说明原因。独立任务并行，有依赖串行。
- **输出**：简体中文，简洁直白，别说废话。
- **内部引用**：使用"可点击链接 + `pathref` 注释"双轨格式。
