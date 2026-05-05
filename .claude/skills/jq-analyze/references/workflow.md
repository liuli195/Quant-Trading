# JQ Analyze 流程

## 单次回测

读取 `backtest_runs/<run_id>/`：

- `metadata.json`
- `summary_metrics.json`
- `all_data.json`
- `tabs_raw/*.md`

生成：

```text
report/strategy-analysis.md
report/performance-analysis.md
```

若 `profile.md` 为空，明确写“无性能剖析数据”。

## 批次对比

读取：

```text
strategies/<strategy>/test_batches/<batch_id>/manifest.json
```

只比较各场景 `primary_run_id` 指向的回测结果。

生成：

```text
strategies/<strategy>/test_batches/<batch_id>/report/batch-comparison.md
```

问题追加到：

```text
strategies/<strategy>/test_batches/<batch_id>/report/issue-log.md
```

不要把原始回测数据复制到批次目录。
