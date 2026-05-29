# Skill 系统精简重构方案

## 目标

1. **规则/命令自然发现**：每条规则和命令都应该能被 AI 通过 Skill 的自然语言触发语义发现，避免每次都全量扫描命令和规则文档；该目标通过现有命令注册机制做轻量设计，并纳入治理流程。
2. **Codex 标准 Skill 结构**：所有 owner Skill 先设计成 Codex 标准 Skill，再为 Claude 生成同名 adapter；Claude 侧不维护第二套规则。
3. **语义清楚、自然可发现**：每个 Codex owner Skill 和 Claude adapter 的名称、`description` 都要让 agent 从自然语言请求中准确识别用途；禁止把多个弱相关流程塞进一个语义模糊的大 Skill。

## Skill 逻辑结构

Skill 按四个逻辑组管理。逻辑组只用于分类和 owner 分配。
旧SKILL 全部迁移入新SKILL 后不再保留。

### Skill System

| Skill | owner 范围 |
| --- | --- |
| `skill-system` | Skill 创建/修改、触发语义、description 优化、adapter 维护、owner/发现规则和索引校验 |

### Repo Governance

| Skill | owner 范围 | 典型归属 |
| --- | --- | --- |
| `repo-python-env` | Python 环境、`.venv`、跨平台 wrapper、云端/本地边界 | `docs/rules/commands.md`、`docs/rules/environments.md` 中的 Python 环境规则 |
| `repo-docs-pathref` | Markdown、pathref、文档索引、报告索引 | `docs/rules/docs-and-pathref.md`、`scripts.tools.path_tools.refactor`、`scripts.research.docs index` |
| `repo-pr-governance` | PR 准备、review 证据、风险分级、官方 Codex review、required checks、governance gate、主干保护、合并前状态和分支清理 | `docs/rules/pr-workflow.md`、`docs/rules/review-guidelines.md`、`docs/rules/governance.md`、`make pr-ready`、`make ai-review`、`make risk-check`、`scripts.research.governance.pr_flow` |

### Strategy Research

| Skill | owner 范围 | 典型归属 |
| --- | --- | --- |
| `research-local-first` | 本地优先研究、候选漏斗、云端交接判断 | `docs/rules/research-workflow.md` 中的本地优先研究规则、`scripts.research.cli` |
| `research-data-center` | 数据快照、回测 run 导入/压缩、catalog、可追溯 | `scripts.research.datasets`、`research_datasets/**` |
| `research-report-analysis` | 回测结果分析、报告生成、缺失报告补全、跨 run 对比 | 报告分析脚本、报告模板、报告 catalog 规则 |
| `strategy-experiment` | 策略变体、参数扫描、A/B 实验、控制变量、delta 归因、物化、分支计划和写回边界 | `scripts.research.variants`、variant registry、参数扫描配置、A/B 实验配置、实验报告和执行规则 |

### JoinQuant Automation

| Skill | owner 范围 | 典型归属 |
| --- | --- | --- |
| `joinquant-strategy-fix` | JoinQuant 策略编译错误、云端兼容、本地编译测试 | compile-check、strategy local check、JoinQuant 兼容修复流程 |
| `joinquant-cloud-run` | 上传策略、启动云端回测、抓取结果、配额保护 | upload/run/fetch/batch、JoinQuant 云端执行和结果抓取流程 |

## 目录落地

所有 Codex owner Skill 使用一层目录：

```text
.codex/
  skills/
    skill-system/
    repo-python-env/
    repo-docs-pathref/
    repo-pr-governance/
    research-local-first/
    research-data-center/
    research-report-analysis/
    strategy-experiment/
    joinquant-strategy-fix/
    joinquant-cloud-run/
```

Claude 侧只保留同名 adapter：

```text
.claude/
  skills/
    <same-skill-name>/
```

## Skill 标准结构

Codex owner Skill：

```text
.codex/skills/<skill>/
  SKILL.md
  agents/
    openai.yaml
  references/
    ownership.yaml
    workflow.md
    commands.md
  templates/
```

要求：

- `SKILL.md` 只写触发语义、必读规则、推荐命令和验证提醒。
- `references/workflow.md` 和 `references/commands.md` 只写短流程和命令说明，不复制规则正文。
- 不把 `docs/rules/**` 搬进 Skill。
- 不把 `scripts/**` 搬进 Skill。

Claude adapter：

```text
.claude/skills/<same-skill-name>/
  SKILL.md
  references/
  templates/
```

要求：

- `name` 与 Codex owner Skill 一致。
- `description` 与 Codex owner Skill 等价，可补充 Claude 常用触发语义。
- 正文写清对应 Codex owner Skill、必读规则、推荐命令和失败处理。
- 不声明第二 owner。
- 不复制规则正文、命令表或脚本实现。

## Owner 索引

`ownership.yaml` 为 Skill ownership 的结构化 SSOT；`docs/rules/skills.md` 只作为人类可读规则说明和汇总索引，不重复维护 ownership 明细。

`ownership.yaml` 代替 `indexes.md` 的机器发现职责；`skills.md` 只保留人类可读汇总。删除 `indexes.md` 前，必须先让治理检查改为读取 `ownership.yaml`，并确认自然语言请求能通过 Skill 触发语义找到规则、命令和脚本 owner。

`ownership.yaml` 建议路径为：

```text
.codex/skills/<skill>/references/ownership.yaml
```

索引字段：

| 字段 | 含义 |
| --- | --- |
| `skill` | owner Skill 名 |
| `group` | 四个逻辑组之一 |
| `owned_rules` | 唯一拥有的规则文档或规则条目 |
| `owned_commands` | 唯一拥有的命令入口 |
| `owned_scripts` | 唯一拥有的可执行脚本或模块 |
| `uses` | 只引用、不拥有的其他 Skill |
| `adapters` | 对应 Claude adapter 或兼容入口 |
| `trigger_phrases` | 自然语言触发短语，用于发现性测试 |
| `read_rules` | 命中后必须读取的规则文件 |
| `recommended_commands` | 命中后优先推荐的有效命令 |
| `status` | `active`、`compat`、`planned`、`deprecated` |

治理检查：

- 每个 owner Skill 必须存在。
- 每个 owner Skill 必须有 `references/ownership.yaml`。
- 同一条规则、命令或可执行脚本只能出现在一个 owner Skill 的 `owned_*` 中。
- Claude adapter 和兼容入口只能指向 owner Skill，不能声明第二 owner。
- Skill 推荐命令必须是当前有效命令。

## Description / adapter 校验

治理检查必须覆盖 Codex owner Skill 和 Claude adapter 的触发语义：

- Codex owner Skill 与 Claude adapter 的 `name` 必须一致。
- Claude adapter 的 `description` 必须与 Codex owner Skill 等价：覆盖同一用途、同一 owner 范围和同一排除边界；Claude 可补充 Claude 常用触发语义，但不能扩大 owner 范围。
- `description` 必须覆盖 `ownership.yaml` 中的 `trigger_phrases`；每个触发短语至少能匹配一个 owner Skill。
- Claude adapter 不得声明 `owned_rules`、`owned_commands` 或 `owned_scripts`，只能引用 Codex owner Skill。
- 同一触发短语不能命中多个 owner Skill；确需复用时，用 `uses` 表达依赖关系，不能声明第二 owner。

## 发现性测试样例

新增一组固定样例，用自然语言请求校验 Skill 发现闭环。每条样例都必须能确定应命中的 Skill、必读规则和推荐命令。

| 自然语言请求 | 应命中 Skill | 必读规则 | 推荐命令 |
| --- | --- | --- | --- |
| “这个仓库本地 Python 应该怎么跑，为什么不能用系统 Python？” | `repo-python-env` | `docs/rules/commands.md`、`docs/rules/environments.md` | `.\.venv\Scripts\python.exe -m <module>` |
| “我移动了文档和报告链接，怎么检查 pathref 和索引？” | `repo-docs-pathref` | `docs/rules/docs-and-pathref.md` | `.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check`、`.\.venv\Scripts\python.exe -m scripts.research.docs index` |
| “准备一个进入主干的 PR，确认 review 证据和 required checks。” | `repo-pr-governance` | `docs/rules/pr-workflow.md`、`docs/rules/review-guidelines.md`、`docs/rules/governance.md` | `make pr-ready`、`make ai-review`、`make risk-check` |
| “先本地筛选研究候选，别直接消耗 JoinQuant 云端额度。” | `research-local-first` | `docs/rules/research-workflow.md` | `.\.venv\Scripts\python.exe -m scripts.research.cli` |
| “把历史回测 run 做成可追溯数据快照。” | `research-data-center` | `docs/rules/research-workflow.md` | `.\.venv\Scripts\python.exe -m scripts.research.datasets` |
| “补齐回测报告并对比多个 run 的收益和回撤。” | `research-report-analysis` | `docs/rules/research-workflow.md` | 报告分析脚本、`.\.venv\Scripts\python.exe -m scripts.research.docs index` |
| “做一个策略参数 A/B 实验，保留控制变量和 delta 归因。” | `strategy-experiment` | `docs/rules/research-workflow.md` | `.\.venv\Scripts\python.exe -m scripts.research.variants` |
| “JoinQuant 云端策略编译报错，帮我本地定位兼容问题。” | `joinquant-strategy-fix` | `docs/rules/environments.md`、`docs/rules/code-style.md` | compile-check、strategy local check |
| “上传策略到 JoinQuant 跑云端回测并抓结果，但注意配额。” | `joinquant-cloud-run` | `docs/rules/environments.md`、`docs/rules/research-workflow.md` | upload/run/fetch/batch |
| “新增或修改一个 owner Skill，并同步 Claude adapter。” | `skill-system` | `docs/rules/skills.md` | Skill 校验脚本、adapter 生成/校验脚本 |
