# Execution Timing Research

本库用于本地评估 ETF 轮动策略的信号刷新和执行时点影响。它只做本地方向性拆解，不直接替代云端回测确认。

## 命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.execution_timing_research.cli analyze `
  --run-id <run_id> `
  [--project-dir strategies\etf_factor_rotation\reports\research\execution_timing] `
  [--raw-price-path <price_bundle.json>] `
  [--audit-log-path <audit_log.jsonl>]
```

## 输入

- 价格包，至少包含 `open` 和 `close`。
- 聚宽审计日志 `audit_log.jsonl`。
- 项目目录下的 `project.json` 和运行目录。

## 输出

- `tables/timing_path_compare.csv`
- `tables/signal_shift_summary.json`
- `reports/timing_local_decision.md`
- `manifest.json`

## 边界

- 本地结果用于判断是否值得上云确认。
- 不修改策略默认参数。
- 不创建或合并 Git 分支。

## 关联测试

- `scripts/research/execution_timing_research/tests/test_analysis.py`
