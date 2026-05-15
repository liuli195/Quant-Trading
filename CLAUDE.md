# CLAUDE.md

## 背景

本项目是基于 Python 的 A 股/场内基金量化交易策略仓库，交易与回测环境为 **聚宽 (JoinQuant)**。
策略代码仅在聚宽云端可运行；本地负责编写、静态检查、单元测试、文档维护、回测结果分析。

## 结构

- `strategies/<name>/<name>.py` — 策略代码
- `strategies/<name>/tests/` — pytest 本地单元测试
- `strategies/<name>/reports/` — 专题分析报告
- `strategies/<name>/test_batches/<batch_id>/scenarios/<scenario_id>/` — 批量测试场景
- `strategies/<name>/backtest_runs/<run_id>/` — 单次回测产物
  - `metadata.json` / `summary_metrics.json` — 运行元数据与汇总指标
  - `report/backtest_report.md` — 回测数据汇总
  - `report/strategy-analysis.md` — 策略分析（每次回测必须产出）
  - `report/performance-analysis.md` — 性能分析（每次回测必须产出）
  - `tabs_raw/` — 聚宽原始指标（收益、回撤、夏普、换手等）
- `strategies/<name>/ab_experiments/<name>/report/` — A/B experiment delta reports
- `docs/` / `docs/joinquant-data/` — 聚宽文档镜像与研究资料
- `scripts/jq_automation/` — jq-auto 云端回测工具
- `scripts/path_tools/` — 路径治理工具（aliases.py / refactor.py）
- `scripts/etf_window_research/` — ETF 时间窗异质性研究工具
- `.claude/skills/` — AI agent 技能，详见 ## Skills
- `path_aliases.json` — 目录别名配置，新增脚本引用结果目录时须通过别名解析，不硬编码路径

## 工具入口

- 聚宽 API 文档：`docs/joinquant-api.md`（离线，优先）| <https://www.joinquant.com/help/api/help#name:api>（在线）
- 语法检查：`.\.venv\Scripts\python.exe -m py_compile <策略文件>`
- 单元测试：`.\.venv\Scripts\python.exe -m pytest <策略>/tests -q`
- 云端回测：`python -m scripts.jq_automation`（首次需在 Chrome 手动登录聚宽，后续工具自动复用登录态）
  子命令：`compile-check` / `upload` / `run` / `fetch` / `batch` / `ab expand|run|report`
- 路径别名解析：`python -m scripts.path_tools.aliases resolve <别名> <key=value...>`；`list` 列出所有别名
- 路径引用校验：`python -m scripts.path_tools.refactor check`；其他子命令：`rewrite-md` / `replace` / `move` / `rewrite`
- ETF 窗异质性研究：`python -m scripts.etf_window_research.cli`（子命令：`export-script`、`fetch`、`analyze`）

## Skills

`.claude/skills/` 中的 AI agent 技能：

- `jq-run` — 云端回测全流程（上传、编译、运行、抓取），消耗每日额度
- `jq-analyze` — 本地分析回测结果（报告、批次对比、趋势跟踪、跨策略对比）
- `jq-fix` — 本地修复策略代码，不启动云端回测
- `jq-param-scan` — 参数扫描（生成网格 → 批量回测 → 对比报告），消耗额度
- `jq-ab-test` — A/B 实验（设计校验 → 执行 → bootstrap 显著性检验），消耗额度

## 通用约定

### 开发流程
本地修改 → 语法/单测校验 → 云端回测 → 分析结果 → 模拟交易。

### 策略代码规范

- **生命周期**：`initialize` 集中完成环境选项、参数初始化、费用/滑点设置、定时任务注册；`handle_data` 或 `run_daily/run_weekly` 实现调仓主逻辑。
- **参数管理**：统一在 `initialize` 中集中定义，避免魔法数字，命名体现含义与单位。
- **数据与性能**：先筛选后计算，优先批量接口与向量化，缓存可复用数据，处理停牌、缺失值、上市时长不足等边界。
- **风控与执行**：明确仓位上下限与调仓步长；记录关键风控参数（最大回撤、换手、仓位漂移）；下单前后记录目标权重与实际成交偏差。

### 注释与文档

- 注释解释"为什么"，不逐行翻译代码；推荐三层结构：
  - **模块头**：策略思想、适用标的、核心公式与约束
  - **函数**：输入、输出、关键副作用
  - **关键语句**：复杂计算、风控裁剪、边界处理
- 研究结论、参数变更理由写入分析文档，不留在代码注释里。
- **reports 命名约定**：报告文件使用 ISO 日期前缀 `YYYY-MM-DD-<topic>.md`，便于排序和追溯。

### 提交前检查

语法/单测通过、无未来函数、参数一致、分析文档同步。

## 重要约束

- 策略代码**仅能在聚宽云端运行**，本地不可执行完整策略。
- 本地 Python 命令必须通过 `.\.venv\Scripts\python.exe`，不使用系统 Python。Codex 环境中须提权执行，否则可能无法访问 `.venv`。
- Markdown 内部文件引用采用双轨格式（可点击路径 + `pathref` 注释），确保机器可校验。
- 每次执行任务后记得清理临时产物。
- 所有回答和输出使用简体中文。
