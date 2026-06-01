# Skill 规则

通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->；规则总索引见 [index.md](index.md) <!-- pathref: docs/rules/index.md -->。

## 规则

- `.agents/skills/<skill>/` 是仓库级 Skill 的唯一事实来源，版本控制完整 `SKILL.md`、`agents/openai.yaml` 和 `references/*`。
- Codex 直接读取 `.agents/skills/`；Claude Code 通过 `.claude/skills` Windows Junction 指向 `.agents/skills` 读取同一份内容。
- `.claude/skills/` 是生成产物，必须被 `.gitignore` 排除，不得双重追踪。
- `.codex/skills/` 是旧路径，必须保持删除；`.codex/environments/environment.toml` 仍保留。
- `ownership.yaml` 是机器可读 SSOT；本文只说明人类规则，不维护 ownership 明细。
- `ownership.yaml` 使用 `tools` 声明使用方，当前允许值为 `claude-code`、`codex`。
- Skill 正文只写触发语义、必读规则、推荐命令和验证提醒，不复制 `docs/rules/**` 正文。
- 同一条规则、命令或脚本只能有一个 Skill 负责；跨流程依赖使用 `uses` 表达。
- 修改 Skill 时同步 `.agents/skills/<skill>/`、`ownership.yaml`、测试和文档索引。
- Skill 小改的日常检查入口是 `scripts.research.governance verify fast --files <Skill文件>`；PR 前仍跑完整门禁。

## 发现

- 自然语言请求必须能唯一命中目标 Skill。
- 命中后先读 `read_rules` 列出的规则文件，再执行推荐命令。
- 推荐命令必须是当前仓库有效入口，优先使用项目 `.venv`。

## Skill 汇总

`ownership.yaml` 是机器可读 SSOT；本表只做人类浏览，不维护 ownership 明细。

| Skill | 范围 |
| --- | --- |
| `repo-skill-governance` | Skill 创建/修改、单一来源、Junction、触发语义和 ownership 治理 |
| `repo-python-env` | Python 环境、项目 `.venv`、UTF-8、本地/云端运行边界 |
| `repo-docs-pathref` | Markdown 链接、pathref、文档索引、报告索引和 catalog |
| `repo-pr-governance` | PR 准备、review 证据、required checks、Codex review、主干保护和分支清理 |
| `research-local-first` | 本地优先研究、候选漏斗、fast/full 筛选和云端交接判断 |
| `research-data-center` | 回测 run 数据快照、数据中心压缩、catalog、pointer 和可追溯证据 |
| `research-report-analysis` | 本地回测报告补齐、结果分析、多个 run 收益回撤对比和报告索引 |
| `strategy-experiment` | 策略参数扫描、A/B 实验、variant registry、控制变量和 delta 归因 |
| `joinquant-strategy-fix` | JoinQuant 云端策略编译报错、本地兼容定位、compile-check 和最小策略修复 |
| `joinquant-cloud-run` | JoinQuant 上传、云端回测 run、fetch、batch、结果落盘和配额保护 |

## 验证

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance.skill_ownership check
.\.venv\Scripts\python.exe -m scripts.research.governance verify explain --files .agents\skills\repo-python-env\SKILL.md
.\.venv\Scripts\python.exe -m scripts.research.governance verify full
.\.venv\Scripts\python.exe -m scripts.research.governance gate
.\.venv\Scripts\python.exe -m scripts.research.docs index
```
