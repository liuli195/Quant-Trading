# 研究数据中心

`research_datasets/` 保存可复用、不可变的研究数据快照。回测数据默认进入这里；`backtest_runs/<run_id>/` 只保留轻量索引、报告和指向数据中心的 pointer。

## 标准结构

- `raw/source.json.gz`：原始 run 文件清单与哈希。
- `raw/*.gz`：压缩保存的原始回测文件，包括 API 导出、审计日志、收益表、明细 Markdown 和摘要 JSON。大压缩文件本地保留，不进入 Git。
- `data/data.parquet`：累计收益序列主存储，使用 `zstd` 压缩，供本地研究快速读取。
- `data/audit_events.parquet`：审计事件主存储。
- `dataset.json`：机器可读元数据、fingerprint、文件映射和原始文件完整性哈希。
- `views/profile.md`、`views/schema.md`、`views/sample.csv`、`views/profile.json`：给人和 AI 快速查看的轻量摘要。

程序读取优先使用 `data/data.parquet` 和 `DataViewLoader`。需要追溯原始表时，通过 `dataset.json` 的 `files.*_source` 读取对应的 `raw/*.gz`。

## 常用命令

导入价格数据：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-price-json `
  strategies\etf_factor_rotation\reports\research\window_heterogeneity\inputs\raw\etf_window_research_prices.json `
  --dataset-id etf_window_prices
```

登记单个完整回测 run，并把原 run 大文件替换成 pointer：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-backtest-run `
  strategies\etf_factor_rotation\backtest_runs\<run_id> `
  --dataset-id etf_factor_rotation_<topic>_run `
  --compact-source
```

批量迁移历史 run：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets migrate-backtest-runs --compact-source
```

`import-backtest-run` 至少要求 run 目录包含：

- `summary_metrics.json`
- `tabs_raw/daily_returns.md`
- `tabs_raw/audit_log.jsonl`
- `detail_api_export.json` 或 `api_export.json`

三类冗余的标准处理：

- 明确重复数据：`summary_metrics.json`、`tabs_raw/daily_returns.md` 压缩进数据中心，RUN 只保留 pointer。
- 数据中心派生冗余：保留 `data/data.parquet`，不再生成 `data/daily_returns.parquet` 和 `views/daily_returns.csv`。
- RUN 明细大文件：`positioninfo.md`、`transactioninfo.md`、`balances.md`、`period_risks.md`、`logs.md` 压缩进数据中心，RUN 只保留 pointer。
