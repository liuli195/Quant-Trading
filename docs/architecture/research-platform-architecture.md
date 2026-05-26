# 本地研究平台架构

本地研究平台采用 5 层结构：策略库、数据中心、流程编排层、研究工具库、文档报告库。Git 只管理代码结构变体；参数变体默认用 `variant_id` 和配置文件登记。

## 核心入口

- 研究流程 CLI：[cli.py](../../scripts/research/cli.py) <!-- pathref: scripts/research/cli.py -->
- 数据中心 CLI：[datasets.py](../../scripts/research/datasets.py) <!-- pathref: scripts/research/datasets.py -->
- 策略变体 CLI：[variants.py](../../scripts/research/variants.py) <!-- pathref: scripts/research/variants.py -->
- 文档索引 CLI：[docs.py](../../scripts/research/docs.py) <!-- pathref: scripts/research/docs.py -->
- 工具注册表：[tool_registry.py](../../scripts/research/registry/tool_registry.py) <!-- pathref: scripts/research/registry/tool_registry.py -->
- 治理审计：[audit.py](../../scripts/research/governance/audit.py) <!-- pathref: scripts/research/governance/audit.py -->

## 策略库

策略目录可包含：

```text
strategies/<strategy>/
  strategy.json
  variants/
    variants.json
    <variant_id>.json
  reports/
  backtest_runs/
  test_batches/
```

实现入口：[strategy_variants.py](../../scripts/research/platform/strategy_variants.py) <!-- pathref: scripts/research/platform/strategy_variants.py -->

- `VariantRegistry` 登记参数变体和结构变体。
- 结构变体注册必须提供 `code_source`；参数变体默认不需要 Git 分支。
- `StrategyMaterializer` 生成可上传策略快照，并写入 `uploaded_code_sha256`。
- `StructuralBranchManager` 只默认生成分支计划；创建分支必须显式授权。
- `VariantMergeManager` 只默认生成合并计划；合并必须显式授权。合并成功后只能进入 `merged_pending_validation`。
- `StrategyManifestReader` 读取 `strategy.json`，缺失时可从策略目录保守推断。

结构变体状态流转：

```text
candidate -> in_research -> cloud_confirmed -> merge_ready -> merged_pending_validation -> merged_confirmed
```

## 数据中心

数据中心目录为 [research_datasets](../../research_datasets) <!-- pathref: research_datasets -->。

新增能力：

- `DatasetRegistry` 读取和校验 `catalog.json`。
- `BacktestRunImporter` 对应 `import-backtest-run`，把 `backtest_runs/<run_id>` 登记为不可变快照，并把大文件压缩保存到数据中心。
- `DataViewLoader` 统一读取 `summary_metrics`、`daily_returns`、`audit_log` 等常用视图。

回测 run 快照会生成 `raw/source.json.gz`、`raw/*.gz`、`data/data.parquet`、`data/audit_events.parquet` 和 `views/` 轻量摘要。原始回测文件压缩保存在本地数据中心，不进入 Git；`data/daily_returns.parquet` 和 `views/daily_returns.csv` 不再生成。

历史 `backtest_runs/` 使用 `scripts.research.datasets migrate-backtest-runs --compact-source` 迁移到数据中心；迁移后 run 目录只保留轻量索引、报告和 pointer。
新增云端回测抓取完成后，`scripts.tools.jq_automation run/fetch/batch/ab run` 默认会把 run 登记到 `research_datasets/<strategy>_backtest_runs/<run_id>`，并把 `api_export.json`、`detail_api_export.json`、`summary_metrics.json`、`tabs_raw/audit_log.jsonl`、`tabs_raw/daily_returns.md` 和明细 Markdown 替换为数据中心 pointer；只有显式传入 `--no-dataset-register` 才跳过登记。

## 流程编排层

现有流程仍以 `scripts.research.cli` 为准：

```text
init -> run --mode fast -> promote -> full review -> handoff-cloud -> cloud confirmation -> report + decision
```

候选漏斗产物继续使用 `candidate_ranking.csv`、`discarded_candidates.csv`、`shortlist.csv`、`cloud_candidates.csv`。

正式流程模板位于 [workflows/templates](../../scripts/research/workflows/templates) <!-- pathref: scripts/research/workflows/templates -->，由 [workflows.py](../../scripts/research/platform/workflows.py) <!-- pathref: scripts/research/platform/workflows.py --> 校验 schema。

研究工具库位于 [research_core](../../scripts/research/research_core) <!-- pathref: scripts/research/research_core -->，包含 `MetricToolkit`、`RobustnessToolkit`、`ReplayAdapter` 和 `ReportPrimitives`。

## 文档报告库

报告仍贴近产物保存，但由 [docs_index.py](../../scripts/research/platform/docs_index.py) <!-- pathref: scripts/research/platform/docs_index.py --> 生成统一索引：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.docs index
```

索引输出：

- [docs_catalog.json](../indexes/docs_catalog.json) <!-- pathref: docs/indexes/docs_catalog.json -->
- [reports_catalog.json](../indexes/reports_catalog.json) <!-- pathref: docs/indexes/reports_catalog.json -->
- [datasets_catalog.json](../indexes/datasets_catalog.json) <!-- pathref: docs/indexes/datasets_catalog.json -->
- [variants_catalog.json](../indexes/variants_catalog.json) <!-- pathref: docs/indexes/variants_catalog.json -->

兼容旧入口仍会写出 [reports.json](../indexes/reports.json) <!-- pathref: docs/indexes/reports.json --> 和 [reports.md](../indexes/reports.md) <!-- pathref: docs/indexes/reports.md -->。

## 治理审计

固定审计命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance audit
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance gate
```

审计覆盖工具登记、README/文档/测试锚点、CLI help、workflow template schema、`AGENTS.md`、`indexes.md`、`CLAUDE.md`、`jq-research`/`jq-ab-test` Skill、数据 catalog、报告 catalog 和 pathref。`gate` 是本地 hook 和 CI 使用的门禁入口，会同时运行治理审计和 pathref 校验。

## 工具注册结构

中央工具注册表按 `library` 管理正式工具。`scripts.research`、`scripts.research.research_core`、专题研究库、`scripts.tools.jq_automation` 和 `scripts.tools.path_tools` 都必须有明确登记项。

登记项包含 `tool_id`、`library`、`layer`、`kind`、`entry_module`、`cli`、README、文档、测试锚点、输入和输出。CLI 元数据必须使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m ...`。

[layers](../../scripts/research/layers) <!-- pathref: scripts/research/layers --> 是按5层生成的工具索引目录，来源仍是同一份 registry；源码继续按库维护，避免为了分层视图重复搬迁实现。

刷新命令：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry write-layers
```

治理审计会：

- 校验 registry 字段、README 和测试锚点。
- 从 registry 自动执行正式 CLI 的 `--help`。
- 扫描 `scripts/research` 和 `scripts/tools` 下未登记的 CLI 模块。
- 校验 workflow template 与 engine 支持的模板一致。
- 校验5层工具索引是否缺失或过期。
