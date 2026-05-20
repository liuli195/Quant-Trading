# 回测数据冗余压缩实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将回测数据的三类冗余分别处理，保留数据完整性，同时减少仓库占用。

**Architecture:** 数据中心保存可追溯压缩原始快照，RUN 目录只保留轻量 pointer 和报告。常规分析继续读取 Parquet 或统一 loader；追溯原始表时由 loader 解压读取。

**Tech Stack:** Python、pandas、gzip、SHA256 manifest、pytest、research governance gate。

---

## 范围

涉及三类数据：

1. 明确重复数据：`daily_returns.md`、`summary_metrics.json`。
2. 数据中心内部派生冗余：`data/data.parquet`、`data/daily_returns.parquet`、`views/daily_returns.csv`。
3. RUN 里的大 Markdown 明细：`positioninfo.md`、`transactioninfo.md`、`balances.md`、`period_risks.md`、`logs.md`。

关键文件：

- [datasets.py](../../../scripts/research/platform/datasets.py) <!-- pathref: scripts/research/platform/datasets.py -->
- [datasets.py](../../../scripts/research/datasets.py) <!-- pathref: scripts/research/datasets.py -->
- [metrics.py](../../../scripts/research/research_core/metrics.py) <!-- pathref: scripts/research/research_core/metrics.py -->
- [audit.py](../../../scripts/research/research_core/audit.py) <!-- pathref: scripts/research/research_core/audit.py -->
- [test_platform.py](../../../scripts/research/platform/tests/test_platform.py) <!-- pathref: scripts/research/platform/tests/test_platform.py -->
- [test_core.py](../../../scripts/tools/jq_automation/tests/test_core.py) <!-- pathref: scripts/tools/jq_automation/tests/test_core.py -->
- [.gitignore](../../../.gitignore) <!-- pathref: repo/.gitignore -->

## 任务

- [ ] **Task 1: 测试三类数据边界**
  - 增加 importer 测试：原始 Markdown 明细进入 `raw/*.gz`，RUN 文件变为 pointer。
  - 增加派生冗余测试：新快照不再写 `data/daily_returns.parquet` 和 `views/daily_returns.csv`。
  - 增加读取兼容测试：`DataViewLoader.daily_returns()`、`parse_cumulative_returns_md()`、`load_rebalance_events()` 能读取 pointer。

- [ ] **Task 2: 实现压缩和 pointer**
  - 扩展回测 raw 文件清单，将 `daily_returns.md`、`summary_metrics.json` 和 Markdown 明细纳入数据中心压缩保存。
  - pointer 记录 `dataset_id`、`snapshot_id`、`dataset_file`、原始 SHA256、压缩 SHA256、原始字节数。
  - importer 写入压缩原始文件前先计算 hash；compact 时只在目标压缩文件存在且 hash 可校验时替换 RUN 文件。

- [ ] **Task 3: 裁剪派生冗余**
  - `daily_returns` 和 `canonical` 都指向 `data/data.parquet`。
  - 停止生成 `data/daily_returns.parquet` 和 `views/daily_returns.csv`。
  - 保留 `views/sample.csv`、`views/profile.*`、`views/schema.md` 作为轻量索引。

- [ ] **Task 4: 刷新当前数据**
  - 运行 `scripts.research.datasets migrate-backtest-runs --compact-source`。
  - 刷新 docs/data catalog。
  - 确认压缩大文件被 Git 忽略，RUN 中只剩 pointer 和轻量报告。

- [ ] **Task 5: 验证**
  - 运行平台和自动化测试。
  - 运行 `py_compile`。
  - 运行 `scripts.research.governance gate`。
  - 复核空间节省、未迁移文件、Git 状态。
