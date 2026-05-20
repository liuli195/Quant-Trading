# AGENTS.md

本仓库是基于 Python 的 A 股/场内基金量化策略仓库，交易与回测环境为聚宽 JoinQuant。

## 通用入口

本文件是所有 AI 编码助手的通用入口；根文档索引见 [indexes.md](indexes.md) <!-- pathref: repo/indexes.md -->。

Claude Code 专属补充见 [CLAUDE.md](CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->。

## 通用规则

- 所有回答和输出使用简体中文；对话风格简洁直白，不要过度使用专业词汇。
- 策略代码仅在聚宽云端运行；本地负责编写、静态检查、单元测试、文档维护、回测结果分析。
- 使用项目虚拟环境运行 Python，遇到沙箱/权限阻断时申请提权；使用项目.venv 运行 Python 时，必须申请提权。具体命令见 [commands.md](docs/rules/commands.md) <!-- pathref: docs/rules/commands.md -->。
- 先调查： 切勿对未读过的代码进行推测。在提出主张前，请先阅读文件并根据根文档索引搜索相关用法。若不确定，请如实说明并提出验证方法。
- 请求范围： 只做要求的事情；不多做。当要求不明确时，默认为研究和建议——仅在明确要求时进行编辑。不要重构相邻的代码，也不要为单一用途创建抽象。
- 完成前验证： 重新检查每个要求。运行测试和代码检查。说明变更内容、已验证项以及无法验证的部分。
- 所有进入主干的改动必须通过 PR；如用户在当前对话中显式授权，可以按“直写主干”链路直接提交和推送主干；禁止本地合并主干，细则见 [pr-workflow.md](docs/rules/pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md -->。
- 所有GIT分支名称和GIT提交说明都使用简体中文。
- 文件规范： 在原有文件上直接编辑。除非必要，否则不要创建新文件。每次任务后清理临时产物。
- 安全性： 执行破坏性操作前需确认（删除文件/分支、强制推送、硬重置、--no-verify）
- 效率： 主会话只负责流程编排，任务全部分发子agent执行。并行化独立工具调用；串行化依赖项调用
- Markdown 内部文件引用使用“可点击链接 + `pathref` 注释”的双轨格式。

## Review guidelines

Before reviewing, read and apply [review-guidelines.md](docs/rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md -->. If you cannot access that file, treat the review as blocked.
