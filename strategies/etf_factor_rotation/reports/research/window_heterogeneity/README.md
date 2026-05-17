# ETF 时间窗异质性研究项目

这是一个按“项目 / 输入 / 导出 / 运行”拆开的专题研究目录，用来承载时间窗异质性验证，而不是只保存一次性输出。

## 目录结构

| 路径 | 用途 |
|---|---|
| [docs/](docs) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity) --> | 研究规格、实验计划、性能优化说明 |
| [inputs/raw/](inputs/raw) <!-- pathref: strategy_research_project_raw_inputs(strategy=etf_factor_rotation, project=window_heterogeneity) --> | 聚宽研究环境导出的原始行情输入 |
| [exports/joinquant/](exports/joinquant) <!-- pathref: strategy_research_project_exports(strategy=etf_factor_rotation, project=window_heterogeneity)/joinquant --> | 回传到聚宽研究环境执行的导出脚本 |
| [runs/](runs) <!-- pathref: strategy_research_project_runs(strategy=etf_factor_rotation, project=window_heterogeneity) --> | 每次本地分析运行的产物 |

## 当前资料

| 类型 | 文件 |
|---|---|
| 研究规格 | [research_spec.md](docs/research_spec.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/research_spec.md --> |
| 云端确认计划 | [cloud_confirmation_plan.md](docs/cloud_confirmation_plan.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/cloud_confirmation_plan.md --> |
| 性能优化计划 | [performance_optimization_plan.md](docs/performance_optimization_plan.md) <!-- pathref: strategy_research_project_docs(strategy=etf_factor_rotation, project=window_heterogeneity)/performance_optimization_plan.md --> |
| 当前基线运行 | [2026-05-15-baseline/](runs/2026-05-15-baseline) <!-- pathref: strategy_research_run(strategy=etf_factor_rotation, project=window_heterogeneity, run_id=2026-05-15-baseline) --> |

## 运行约定

- `docs/` 只放研究口径和决策说明，不放结果表。
- `inputs/` 与 `exports/` 只放与外部环境交换的文件。
- `runs/<run_id>/reports/` 放可阅读报告。
- `runs/<run_id>/tables/` 放结构化表格。
- `runs/<run_id>/curves/` 放因子曲线明细。
- 每次运行都生成 `manifest.json`，用于记录输入和产物清单。

## 推荐命令

```powershell
.\.venv\Scripts\python.exe -m scripts.research.cli run `
  --project-dir strategies\etf_factor_rotation\reports\research\window_heterogeneity `
  --run-id 2026-05-17-fast `
  --mode fast

.\.venv\Scripts\python.exe -m scripts.research.cli promote `
  --project-dir strategies\etf_factor_rotation\reports\research\window_heterogeneity `
  --fast-run-id 2026-05-17-fast `
  --full-run-id 2026-05-17-full `
  --top-k 10

.\.venv\Scripts\python.exe -m scripts.etf_window_research.cli export-script `
  --project-dir strategies\etf_factor_rotation\reports\window_heterogeneity

.\.venv\Scripts\python.exe -m scripts.etf_window_research.cli fetch `
  --project-dir strategies\etf_factor_rotation\reports\window_heterogeneity `
  --headless

.\.venv\Scripts\python.exe -m scripts.etf_window_research.cli analyze `
  --project-dir strategies\etf_factor_rotation\reports\window_heterogeneity `
  --run-id 2026-05-15-baseline `
  --audit-log strategies\etf_factor_rotation\backtest_runs\20260514-1959-bt1a70c5cd71fac1c27eed2268045ad80a\tabs_raw\audit_log.jsonl
```
