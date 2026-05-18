# CLAUDE.md

## 背景

本项目是 A 股/场内基金量化交易策略仓库，回测与交易环境为 **聚宽 (JoinQuant)**。
策略仅在聚宽云端运行；本地负责编写、静态检查、单测、本地研究、文档与分析。

## 重要约束

- AI 助手统一以本文件为入口；仓库级规则正文见 [docs/rules/index.md](docs/rules/index.md) <!-- pathref: docs/rules/index.md -->，重大治理决策见 [docs/adr](docs/adr) <!-- pathref: docs/adr -->。
- 策略代码**仅能在聚宽云端运行**，本地不可执行完整策略。
- 本地 Python 命令必须通过 `.\.venv\Scripts\python.exe`，不使用系统 Python。
- Markdown 内部文件引用采用双轨格式（可点击路径 + `pathref` 注释），确保机器可校验。
- 每次任务后清理临时产物。
- 所有回答和输出使用简体中文。

## 开发约定

- **开发流程**：本地修改 → 语法/单测校验 → 本地研究 → 云端回测 → 分析结果。
- **代码规范**：`initialize` 集中配置与注册，`handle_data`/`run_daily` 实现调仓。参数集中定义、避免魔法数字。先筛选后计算、优先批量向量化、处理停牌缺失等边界。明确仓位上下限与风控参数。
- **注释规范**：解释"为什么"而非逐行翻译；推荐三层（模块头/函数/关键语句）。研究结论写入分析文档，不留在代码注释。报告使用 `<topic>_YYYY/MM/DD.md` 命名。
- **提交检查**：语法/单测通过、无未来函数、参数一致、分析文档同步。

## 日常命令

```powershell
# 语法检查
.\.venv\Scripts\python.exe -m py_compile strategies\<s>\<s>.py
# 单元测试
.\.venv\Scripts\python.exe -m pytest strategies\<s>\tests -q
# 云端回测（完整参考: scripts/tools/jq_automation/README.md）
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation compile-check|upload|run|fetch|batch|ab
# 路径引用校验
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
# 本地研究（完整参考: docs/guides/research-workflow.md）
.\.venv\Scripts\python.exe -m scripts.research.cli init|run|promote|resume|handoff-cloud|status
# 数据中心
.\.venv\Scripts\python.exe -m scripts.research.datasets import-price-json|import-audit-log|import-backtest-run|inspect
# 文档报告索引
.\.venv\Scripts\python.exe -m scripts.research.docs index
# 策略变体登记、快照和 Git 计划
.\.venv\Scripts\python.exe -m scripts.research.variants list|register|materialize|branch-plan|branch-create|merge-plan|merge-apply
# 中央工具注册与治理审计
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry list|validate
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

## Skills

`.claude/skills/` 中的 AI agent 技能：`jq-run`、`jq-analyze`、`jq-fix`、`jq-param-scan`、`jq-ab-test`、`jq-research`。
每个技能有独立的 `SKILL.md`，包含完整指令与约束。

## 目录速查

- `strategies/<name>/` — 策略代码、测试、报告、回测产物、A/B 实验
- `scripts/tools/` — jq_automation（云端回测）、path_tools（路径治理）
- `scripts/research/` — 本地研究 CLI、数据中心、变体库、工具注册、治理审计与专项工具
- `scripts/research/workflows/templates/` — 本地研究流程模板
- `scripts/research/research_core/` — 指标、稳健性、回放和报告基础库
- `docs/` — 文档入口、规则、研究流程、架构、参考资料
- `.claude/skills/` — AI agent 技能定义
- 目录路径统一通过 `path_aliases.json` 的别名解析，禁止硬编码。

## 详细文档索引

| 文档 | 路径 |
| ---- | ---- |
| 云端回测完整参考（命令签名、参数表、schema、错误索引） | [jq_automation/README.md](scripts/tools/jq_automation/README.md) |
| 路径别名与重构工具说明 | [path_tools/README.md](scripts/tools/path_tools/README.md) |
| 仓库级规则总索引 | [rules/index.md](docs/rules/index.md) <!-- pathref: docs/rules/index.md --> |
| 架构决策记录 | [docs/adr](docs/adr) <!-- pathref: docs/adr --> |
| 本地优先研究流程与命令行示例 | [docs/guides/research-workflow.md](docs/guides/research-workflow.md) <!-- pathref: docs/guides/research-workflow.md --> |
| 本地研究平台架构与治理 | [research-platform-architecture.md](docs/architecture/research-platform-architecture.md) <!-- pathref: docs/architecture/research-platform-architecture.md --> |
| 研究流程模板说明 | [workflows/README.md](scripts/research/workflows/README.md) <!-- pathref: scripts/research/workflows/README.md --> |
| 本地 Python 环境约定与修复 | [docs/guides/local-python-env.md](docs/guides/local-python-env.md) <!-- pathref: docs/guides/local-python-env.md --> |
| 聚宽 API 文档 | [docs/reference/joinquant-api.md](docs/reference/joinquant-api.md) <!-- pathref: docs/reference/joinquant-api.md -->（离线优先） \| [在线 API](https://www.joinquant.com/help/api/help#name:api) |
