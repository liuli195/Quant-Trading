# JQ Run 产物契约

单次回测产物写入：

```text
strategies/<strategy>/backtest_runs/<run_id>/
```

批次索引写入：

```text
strategies/<strategy>/test_batches/<batch_id>/manifest.json
```

`jq-run` 只负责原始数据、`backtest_report.md`、批次映射和额度账本；`strategy-analysis.md`、`performance-analysis.md`、`batch-comparison.md` 由 `jq-analyze` 生成。

DOM 降级抓取时，必须在 `all_data.json` 标记对应标签 `partial=true`。
