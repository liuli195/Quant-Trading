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
