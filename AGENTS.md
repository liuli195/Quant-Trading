# AGENTS.md

## 项目身份

基于 Python 的 A 股/场内基金量化交易策略仓库，交易与回测环境为 **聚宽 (JoinQuant)**。
策略代码仅在聚宽云端可运行；本地负责编写、静态检查、单元测试、文档维护、回测结果分析。

## 规则入口

所有 AI 编码助手（Claude Code、Cursor、Copilot、Codex 等）统一以 **[CLAUDE.md](CLAUDE.md) 为权威规则源**。

CLAUDE.md 是 AI 助手入口。仓库级规则正文在 **[docs/rules/index.md](docs/rules/index.md) <!-- pathref: docs/rules/index.md -->**，重大规则和治理决策记录在 **[docs/adr](docs/adr) <!-- pathref: docs/adr -->**。

CLAUDE.md 包含：目录结构约定、工具入口与命令、策略代码规范、注释与文档约定、提交前检查清单、Skills 说明。

本文件仅记录跨工具通用的补充约束，内容稳定不随项目迭代频繁变更。

## 跨工具约束

### Python 环境

- 本地 Python 命令必须通过 `.\.venv\Scripts\python.exe`，不使用系统 Python。
- **Codex 环境中须提权执行**，否则可能无法访问 `.venv` 或解析项目目录，导致误用系统 Python。

### 输出语言

所有回答和输出使用简体中文。

### 文件引用格式

Markdown 内部文件引用采用双轨格式（可点击路径 + `pathref` 注释），确保机器可校验。
