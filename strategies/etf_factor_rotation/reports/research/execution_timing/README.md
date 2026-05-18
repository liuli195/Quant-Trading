# 执行时序影响研究项目

这是一个独立的本地研究项目，用来拆开量化：

1. 只晚一天成交带来的执行延迟影响
2. 多看一天收盘数据带来的信号刷新影响
3. `baseline / logic-2 / logic-3` 三组近似路径的总差异

## 目录结构

| 路径 | 用途 |
|---|---|
| [docs/](docs) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=execution_timing) --> | 研究规格、执行计划、数据契约 |
| [inputs/raw/](inputs/raw) <!-- pathref: strategy_research_project_raw_inputs(strategy=etf_factor_rotation, project=execution_timing) --> | 后续刷新后的带 `open` 行情包 |
| [exports/joinquant/](exports/joinquant) <!-- pathref: strategy_research_project_exports(strategy=etf_factor_rotation, project=execution_timing)/joinquant --> | 聚宽侧行情导出脚本 |
| [runs/](runs) <!-- pathref: strategy_research_project_runs(strategy=etf_factor_rotation, project=execution_timing) --> | 每次本地运行产物 |

## 当前运行方式

```powershell
.\.venv\Scripts\python.exe -m scripts.research.execution_timing_research.cli analyze `
  --project-dir strategies\etf_factor_rotation\reports\research\execution_timing `
  --run-id 2026-05-18-phase1-initial
```

## 当前状态

- 带 `open` 的行情包已刷新到 [execution_timing_prices.json](inputs/raw/execution_timing_prices.json) <!-- pathref: strategy_research_project_raw_inputs(strategy=etf_factor_rotation, project=execution_timing)/execution_timing_prices.json -->
- baseline 本地复算已校准通过，最大最终权重误差约 `3.23e-09`
- 当前有效本地运行：[2026-05-18-phase1-open-refresh](runs/2026-05-18-phase1-open-refresh) <!-- pathref: strategy_research_run(strategy=etf_factor_rotation, project=execution_timing, run_id=2026-05-18-phase1-open-refresh) -->
- 当前有效云端确认：[2026-05-18-cloud-confirmation](runs/2026-05-18-cloud-confirmation) <!-- pathref: strategy_research_run(strategy=etf_factor_rotation, project=execution_timing, run_id=2026-05-18-cloud-confirmation) -->
