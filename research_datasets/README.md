# 研究数据集

`research_datasets/` 用于保存可复用、不可变的研究快照。每个快照同时服务人和程序：

- `raw/source.json.gz`：保留原始导出件，便于追溯。
- `data/data.parquet`：主存储，使用 `zstd` 压缩，供本地研究快速读取。
- `dataset.json`：机器可读元数据与 fingerprint。
- `views/profile.md`、`views/schema.md`、`views/sample.csv`：给人和 AI 快速查看的摘要包。

推荐先看根目录的 `catalog.md`，再进入单个快照查看 `README.md` 与 `views/`；程序读取优先使用 `data/data.parquet`。

导入命令：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-price-json `
  strategies\etf_factor_rotation\reports\research\window_heterogeneity\inputs\raw\etf_window_research_prices.json `
  --dataset-id etf_window_prices
```

完整回测 run 需要复用时也可登记为快照：

```powershell
.\.venv\Scripts\python.exe -m scripts.research.datasets import-backtest-run `
  strategies\etf_factor_rotation\backtest_runs\<run_id> `
  --dataset-id etf_factor_rotation_<topic>_run
```

`import-backtest-run` 要求 run 目录至少包含：

- `summary_metrics.json`
- `tabs_raw/daily_returns.md`
- `tabs_raw/audit_log.jsonl`
- `detail_api_export.json` 或 `api_export.json`

输出包括：

- `raw/source.json.gz`：原始 run 文件清单与哈希。
- `raw/audit_log.jsonl.gz`：压缩保存的审计日志。
- `raw/daily_returns.md`：原始累计收益表。
- `data/data.parquet`、`data/daily_returns.parquet`、`data/audit_events.parquet`：本地研究主存储。
- `views/profile.md`、`views/schema.md`、`views/sample.csv`、`views/profile.json`：便读视图。
