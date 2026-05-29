# Skill 规则

通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；规则总索引见 [index.md](index.md) <!-- pathref: docs/rules/index.md -->。

## 规则

- Codex owner Skill 是事实入口，位置为 `.codex/skills/<owner>/`。
- Claude 侧只保留同名 adapter，位置为 `.claude/skills/<owner>/`。
- `ownership.yaml` 是机器可读 SSOT；本文只说明人类规则，不维护 ownership 明细。
- Skill 正文只写触发语义、必读规则、推荐命令和验证提醒，不复制 `docs/rules/**` 正文。
- 同一条规则、命令或脚本只能有一个 owner；跨流程依赖使用 `uses` 表达。
- 修改 owner Skill 时同步 Claude adapter、`ownership.yaml`、测试和文档索引。

## 发现

- 自然语言请求必须能唯一命中目标 owner Skill。
- 命中后先读 `read_rules` 列出的规则文件，再执行推荐命令。
- 推荐命令必须是当前仓库有效入口，优先使用项目 `.venv`。

## Owner Skill 汇总

`ownership.yaml` 是机器可读 SSOT；本表只做人工浏览，不维护 ownership 明细。

| Skill | 范围 |
| --- | --- |
| `skill-system` | Skill 创建/修改、Claude adapter、触发语义和 ownership 治理 |
| `repo-python-env` | Python 环境、项目 `.venv`、UTF-8、本地/云端运行边界 |
| `repo-docs-pathref` | Markdown 链接、pathref、文档索引、报告索引和 catalog |
| `repo-pr-governance` | PR 准备、review 证据、required checks、Codex review、主干保护和分支清理 |
| `research-local-first` | 本地优先研究、候选漏斗、fast/full 筛选和云端交接判断 |
| `research-data-center` | 回测 run 数据快照、数据中心压缩、catalog、pointer 和可追溯证据 |
| `research-report-analysis` | 本地回测报告补齐、结果分析、多个 run 收益回撤对比和报告索引 |
| `strategy-experiment` | 策略参数扫描、A/B 实验、variant registry、控制变量和 delta 归因 |
| `joinquant-strategy-fix` | JoinQuant 云端策略编译报错、本地兼容定位、compile-check 和最小策略修复 |
| `joinquant-cloud-run` | JoinQuant 上传、云端回测 run、fetch、batch、结果落盘和额度保护 |

## 验证

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
.\.venv\Scripts\python.exe -m scripts.research.governance gate
.\.venv\Scripts\python.exe -m scripts.research.docs index
```
