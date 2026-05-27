# 仓库规则总索引

本目录是仓库级规则正文。通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；根索引见 [indexes.md](../../indexes.md) <!-- pathref: repo/indexes.md -->；Claude Code 指针见 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->；规则来源见 [docs/adr](../adr) <!-- pathref: docs/adr -->。

## 分级

| 等级 | 含义 | 执行 |
| --- | --- | --- |
| MUST | 不得违反 | `governance gate`、CI、主干保护 |
| SHOULD | 默认遵守，可说明偏离 | PR 说明、review |
| MAY | 可选建议 | 文档、示例 |

## 文件

| 文档 | 规则范围 |
| --- | --- |
| [commands.md](commands.md) <!-- pathref: docs/rules/commands.md --> | `.venv`、wrapper、常用命令 |
| [environments.md](environments.md) <!-- pathref: docs/rules/environments.md --> | 本地、聚宽回测/模拟/研究环境边界 |
| [code-style.md](code-style.md) <!-- pathref: docs/rules/code-style.md --> | 策略代码、测试、注释、兼容写法 |
| [research-workflow.md](research-workflow.md) <!-- pathref: docs/rules/research-workflow.md --> | 本地研究、云端确认、数据和报告 |
| [docs-and-pathref.md](docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md --> | Markdown、pathref、报告索引 |
| [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md --> | 分支、PR、主干同步、分支清理 |
| [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> | 本地 AI review、Codex Code Review、PR 证据 |
| [governance.md](governance.md) <!-- pathref: docs/rules/governance.md --> | CI、hooks、CODEOWNERS、waiver、漂移检查 |

## 变更

MUST 规则变更必须同步规则文档、依赖脚本、测试、索引；影响协作模型、目录结构、门禁或策略流程时，同步 [docs/adr](../adr) <!-- pathref: docs/adr --> 并经过 CODEOWNER review。
