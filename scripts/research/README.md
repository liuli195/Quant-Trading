# research — 本地优先研究平台

研究脚本的总入口，包含研究平台 CLI、数据集管理 CLI、现金拆解分析库和稳健性验证工具。

## CLI 工具

### 研究平台（cli.py）

本地优先研究平台的命令行入口。管理研究项目的完整生命周期：创建项目骨架 → 本地 fast/full 运行 → 候选漏斗 → promote → 云端交接。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli <子命令> ...
```

#### init — 创建研究项目

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli init `
  --project-dir <dir> --strategy <name> --project <name> `
  --template {factor_scan,parameter_followup,robustness_check,generic,portfolio_volatility} `
  [--plugin <name>] [--dataset-id <id> --snapshot-id <id>] [--raw-data <path>] `
  [--audit-log <path>] [--baseline-returns <path>] [--variant-return label=path ...]
```

参数：
- `--project-dir` — 必填，项目目录
- `--strategy` — 必填，策略名称（如 `etf_factor_rotation`）
- `--project` — 必填，项目名称
- `--template` — 必填，研究模板：`factor_scan` / `parameter_followup` / `robustness_check` / `generic` / `portfolio_volatility`
- `--plugin` — 可选，插件名（默认与 template 同名）
- `--dataset-id` / `--snapshot-id` — 可选，关联的数据集快照
- `--raw-data` — 可选，原始数据路径
- `--audit-log` — 可选，审计日志路径
- `--baseline-returns` — 可选，基线收益路径
- `--variant-return` — 可选，可重复的 `label=path` 对（用于 robustness_check）

生成产物：`project.json`、`README.md`、`docs/` 下 6 个模板文档文件。

#### run — 执行研究运行

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli run `
  --project-dir <dir> --run-id <id> --mode {fast,full} `
  [--top-k <n>] [--cloud-top-k <n>]
```

参数：
- `--project-dir` — 必填，项目目录
- `--run-id` — 必填，运行 ID
- `--mode` — 必填，`fast`（快速筛选）或 `full`（完整评估）
- `--top-k` — 可选，候选数（默认 20）
- `--cloud-top-k` — 可选，云端候选数（默认 3）

#### promote — 从 fast 升级到 full

将 fast 运行的 shortlist 作为候选升级为 full 运行。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli promote `
  --project-dir <dir> --fast-run-id <id> --full-run-id <id> `
  [--top-k <n>] [--cloud-top-k <n>]
```

#### handoff-cloud — 云端交接

为 full 运行生成云端交接材料（策略参数差异、执行指令）。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli handoff-cloud `
  --project-dir <dir> --run-id <id>
```

#### status — 查看运行状态

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli status --project-dir <dir>
```

输出所有 run 的 `status.json` 摘要。

#### resume — 恢复中断的运行

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli resume `
  --project-dir <dir> --run-id <id>
```

读取 `request.json` 重新执行。若为 full 模式且有 `source_run_id`，自动重新 promote。

### 数据集管理（datasets.py）

仓库级不可变研究数据集管理。将 JoinQuant 导出的 JSON/JSONL 转为 Parquet 快照。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets <子命令> ...
```

#### import-price-json — 导入价格数据

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-price-json `
  <source.json> --dataset-id <id> [--snapshot-id <id>]
```

- `source` — 必填，JoinQuant 价格导出 JSON 路径
- `--dataset-id` — 必填，数据集标识
- `--snapshot-id` — 可选，快照 ID（默认自动生成：时间戳 + 内容 SHA256 前 12 位）
- 价格字段按导出内容原样保留，当前研究基线约定为 `open / close / high / low / money`

产物：`raw/source.json.gz`、`data/data.parquet`、`views/`（profile.md、schema.md、sample.csv、profile.json）、`dataset.json`、`README.md`。自动更新 `research_datasets/catalog.json` 和 `catalog.md`。

#### import-audit-log — 导入审计日志

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-audit-log `
  <audit_log.jsonl> --dataset-id <id> [--snapshot-id <id>]
```

将聚宽审计日志 JSONL 转换为 Parquet 主存储。自动：
- 解析 `run_start` 中的 `etf_pool`、`benchmark` 参数
- 从 `rebalance_signals` 事件中展平数组字段（趋势门槛、RP 权重、动量/RSRS 倾斜、拥挤度惩罚、各阶段权重、组合波动率缩放等）
- 写入 `data/data.parquet`

#### import-backtest-run — 导入完整回测 run

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-backtest-run `
  strategies\etf_factor_rotation\backtest_runs\<run_id> `
  --dataset-id <id> [--snapshot-id <id>]
```

将完整 `backtest_runs/<run_id>` 登记为不可变快照。要求存在 `summary_metrics.json`、`tabs_raw/daily_returns.md`、`tabs_raw/audit_log.jsonl`、`detail_api_export.json` 或 `api_export.json`。输出 `raw/*.gz`、`data/data.parquet`、`data/audit_events.parquet` 和 `views/` 轻量摘要；使用 `--compact-source` 时，原始 run 中的大文件会替换成数据中心 pointer。

`scripts.tools.jq_automation run/fetch/batch/ab run` 完成抓取后默认调用该 importer，把新 run 写入 `research_datasets/<strategy>_backtest_runs/<run_id>`。需要临时跳过时使用 `--no-dataset-register`。

#### inspect — 查看数据集元数据

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets inspect `
  <dataset_id> <snapshot_id>
```

输出 `dataset.json` 的完整内容（JSON 格式）。

### 文档索引（docs.py）

扫描仓库 Markdown 报告并生成总索引。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.docs index
```

输出 `docs/indexes/docs_catalog.json`、`reports_catalog.json`、`datasets_catalog.json`、`variants_catalog.json`，并保留 `reports.json`、`reports.md` 兼容旧入口。

### 策略变体（variants.py）

```powershell
.\.venv\Scripts\python.exe -m scripts.research.variants register `
  --strategy <strategy> `
  --variant-id <id> --variant-type parameter `
  --payload-json '{"param_overrides":{"MomentumTiltStrength":0.35}}'

.\.venv\Scripts\python.exe -m scripts.research.variants materialize `
  --strategy <strategy> --variant-id <id>

.\.venv\Scripts\python.exe -m scripts.research.variants branch-plan --variant-id <id>

.\.venv\Scripts\python.exe -m scripts.research.variants merge-plan `
  --strategy <strategy> --variant-id <id>
```

结构变体必须有 `code_source`；`branch-create`、`merge-apply`、标记 `merged_confirmed` 均需要显式 `--yes`。`merge-apply` 成功后只进入 `merged_pending_validation`。

### 流程模板

模板位于 `scripts/research/workflows/templates/`，由 `scripts.research.platform.workflows` 校验。新增模板必须声明输入、阶段、输出和门槛，并通过 `governance audit`。

### 中央工具注册（registry）

Windows：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry list
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry list --group-by-library
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry list --group-by-layer
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry validate
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry write-layers
```

POSIX / Codex Cloud：

```bash
.venv/bin/python -m scripts.research.registry.tool_registry list
.venv/bin/python -m scripts.research.registry.tool_registry list --group-by-library
.venv/bin/python -m scripts.research.registry.tool_registry list --group-by-layer
.venv/bin/python -m scripts.research.registry.tool_registry validate
.venv/bin/python -m scripts.research.registry.tool_registry write-layers
```

登记工具 ID、所属层、入口模块、Windows/POSIX CLI、输入输出、README、文档和测试锚点。
`write-layers` 会从注册表生成 [layers](layers) <!-- pathref: scripts/research/layers --> 下的5层工具索引。

### 治理审计（governance）

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

审计工具登记、README、CLI help、workflow template schema、`AGENTS.md`、`CLAUDE.md`、owner Skill / Claude adapter、数据 catalog、报告 catalog 和 pathref。`gate` 是本地 hook 和 CI 的固定入口。

## 库模块

### cash_decomposition/ — 现金来源拆解

纯函数库，从审计数据集 Parquet 计算四层现金归因。详见 [cash_decomposition/README.md](cash_decomposition/README.md)。

### robustness_verify.py — 单次稳健性验证

一次性脚本，对特定回测 run 对进行配对 block bootstrap + 滚动子样本分析 + 年度分解。硬编码了 baseline/variant run ID，作为研究参考而非通用工具。

## 典型工作流

```
# 1. 导入数据
.\.venv\Scripts\python.exe -m scripts.research.datasets import-audit-log audit_log.jsonl --dataset-id my_audit

# 2. 创建研究项目
.\.venv\Scripts\python.exe -m scripts.research.cli init --project-dir my_project --strategy etf_factor_rotation \
  --project my_study --template generic --dataset-id my_audit --snapshot-id <id>

# 3. 快速筛选
.\.venv\Scripts\python.exe -m scripts.research.cli run --project-dir my_project --run-id fast-01 --mode fast

# 4. 升级到完整评估
.\.venv\Scripts\python.exe -m scripts.research.cli promote --project-dir my_project \
  --fast-run-id fast-01 --full-run-id full-01

# 5. 生成云端交接
.\.venv\Scripts\python.exe -m scripts.research.cli handoff-cloud --project-dir my_project --run-id full-01
```
