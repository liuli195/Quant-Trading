# JQ Run 流程

## 步骤

1. 解析 `strategy_file`、日期、资金，可选 `batch_id`、`scenario_id`。
2. 正式云端回测前，先给用户计划：场景、区间、预计耗时、剩余额度。
3. 本地执行 `python -m py_compile <strategy_file>`。
4. 用 `scripts/strip_comments.py` 生成 `<strategy_name>__upload.py`。
5. 打开聚宽，写入代码，编译校验。
6. 编译通过且额度允许时，启动正式回测。
7. 用 API bundle 优先抓取结果，必要时 DOM 降级。
8. 用 `scripts/save_backtest_data.py` 保存结果。
9. 如属于批次，更新 `manifest.json`；如启动正式回测，更新额度账本。

## 产物

单次回测：

```text
strategies/<strategy>/backtest_runs/<run_id>/
├── api_export.json
├── metadata.json
├── summary_metrics.json
├── all_data.json
├── report/backtest_report.md
└── tabs_raw/*.md
```

批次映射：

```text
strategies/<strategy>/test_batches/<batch_id>/
├── manifest.json
├── report/
│   ├── batch-plan.md
│   ├── batch-comparison.md
│   └── issue-log.md
└── scenarios/<scenario_id>/scenario.json
```

## 命名

- `batch_id`: `YYYYMMDD-HHMM-<topic-slug>`
- `scenario_id`: `sNN-<slug>`
- `attempt_id`: `aNN`
- `run_id`: `YYYYMMDD-HHMM-bt<backtest_id>`

映射关系：

```text
batch -> scenario -> attempt -> backtest_runs/<run_id>
```

批次对比只读取场景的 `primary_run_id`。

## 额度

每日正式云端回测预算 60 分钟，账本：

```text
docs/joinquant-data/quota_ledger/YYYYMMDD.json
```

剩余不足 10 分钟、场景已有成功 `primary_run_id`、或用户未确认场景列表时，停止并确认。
