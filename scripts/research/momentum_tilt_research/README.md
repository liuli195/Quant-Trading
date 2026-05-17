# momentum_tilt_research — 动量倾斜研究工具

对 ETF 因子轮动策略中的动量倾斜（MomentumTilt）信号进行本地回放校准、分阶段分析、
A/B 实验计划和云端回测稳健性评估。

**入口**：`python -m scripts.research.momentum_tilt_research`

## 子命令

### replay-calibrate — 本地回放校准

将本地回放结果与已知云端回测对照，校准回放精度。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.momentum_tilt_research replay-calibrate `
  [--raw-data <path>] [--audit-log <path>] [--baseline-returns <path>] [--output <path>]
```

参数：
- `--raw-data` — 原始价格数据 JSON 路径（默认：`<project_dir>/raw_price_bundle.json`）
- `--audit-log` — 审计日志 JSONL 路径（默认：`<project_dir>/audit_log.jsonl`）
- `--baseline-returns` — 基线收益 Markdown 路径（默认：`<project_dir>/baseline_returns.md`）
- `--output` — 可选，结果 JSON 输出路径

### analyze — 分阶段本地分析

运行分阶段动量倾斜本地分析。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.momentum_tilt_research analyze `
  [--project-dir <dir>] --run-id <id> [--stage {phase0,phase1,phase2,all}] `
  [--raw-data <path>] [--audit-log <path>] [--baseline-returns <path>]
```

参数：
- `--project-dir` — 研究项目目录（默认自动确定）
- `--run-id` — 必填，运行 ID
- `--stage` — 可选，分析阶段：`phase0`、`phase1`、`phase2`、`all`（默认：`all`）
- `--raw-data` — 原始价格数据路径
- `--audit-log` — 审计日志路径
- `--baseline-returns` — 基线收益路径

### ab-plan — 生成 A/B 实验计划

本地通过全部门禁后，生成云端批量 A/B 实验配置。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.momentum_tilt_research ab-plan `
  --local-decision <path> [--batch-id <id>] --output-dir <dir> [--created <datetime>]
```

参数：
- `--local-decision` — 必填，本地分析 `full_decision.json` 路径
- `--batch-id` — 可选，批次 ID（默认：`20260517-momentum-strength-confirmation`）
- `--output-dir` — 必填，输出目录
- `--created` — 可选，创建时间戳（默认：`2026-05-17T00:00:00`）

### cloud-robustness — 云端稳健性报告

为已完成的云端回测生成稳健性对比报告。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.momentum_tilt_research cloud-robustness `
  --baseline-run <id> --variant-run <id> --label <name> [--raw-data <path>]
```

参数：
- `--baseline-run` — 必填，基线回测 run ID
- `--variant-run` — 必填，变体回测 run ID
- `--label` — 必填，对比标签（如 `gold-start-080`）
- `--raw-data` — 原始价格数据路径

## 典型工作流

```
replay-calibrate → analyze (phase0→phase1→phase2) → ab-plan → 云端执行 → cloud-robustness
```

依赖的 ETF 标的与策略名称定义在 `spec.py` 中。

## 依赖

- `scripts.research.research_core`（审计事件加载、收益解析、价格加载、指标计算、报告输出）
