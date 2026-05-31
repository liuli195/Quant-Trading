# 仓库规则总索引

本目录是仓库级规则正文。通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；Claude 侧入口见 [CLAUDE.md](../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->；规则来源见 [ADR 索引](../adr/index.md) <!-- pathref: docs/adr/index.md -->。

## 分级

| 等级 | 含义 | 执行 |
| --- | --- | --- |
| MUST | 不得违反 | `governance gate`、CI、主干保护 |
| SHOULD | 默认遵守，可说明偏离 | PR 说明、review |
| MAY | 可选建议 | 文档、示例 |

## 文件

| 文档 | 规则范围 |
| --- | --- |
| [commands.md](commands.md) <!-- pathref: docs/rules/commands.md --> | `.venv`、常用命令 |
| [skills.md](skills.md) <!-- pathref: docs/rules/skills.md --> | Skill owner、adapter、自然语言发现和 ownership 治理 |
| [environments.md](environments.md) <!-- pathref: docs/rules/environments.md --> | 本地、聚宽回测/模拟/研究环境边界 |
| [code-style.md](code-style.md) <!-- pathref: docs/rules/code-style.md --> | 策略代码、测试、注释、兼容写法 |
| [research-workflow.md](research-workflow.md) <!-- pathref: docs/rules/research-workflow.md --> | 本地研究、云端确认、数据和报告 |
| [collaboration.md](collaboration.md) <!-- pathref: docs/rules/collaboration.md --> | AI 协作、分支命名、共享工作区 |
| [docs-and-pathref.md](docs-and-pathref.md) <!-- pathref: docs/rules/docs-and-pathref.md --> | Markdown、pathref、报告索引 |
| [pr-workflow.md](pr-workflow.md) <!-- pathref: docs/rules/pr-workflow.md --> | PR、主干同步、分支清理 |
| [review-guidelines.md](review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> | 本地 AI review、Codex Code Review、PR 证据 |
| [governance.md](governance.md) <!-- pathref: docs/rules/governance.md --> | CI、hooks、CODEOWNERS、waiver、漂移检查 |

## 变更

MUST 规则变更必须同步规则文档、依赖脚本、测试、索引；影响协作模型、目录结构、门禁或策略流程时，同步 [ADR 索引](../adr/index.md) <!-- pathref: docs/adr/index.md --> 并经过显式 owner 授权或远端实际要求的 review。任何与规则冲突的改动、对规则本身的改动都必须显式获得授权（见 AGENTS.md 核心规则「规则优先」）。
