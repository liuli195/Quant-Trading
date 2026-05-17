# research_core — 共享研究基础库

所有研究工具和 CLI 的底层依赖库，提供审计日志解析、交易日历、文件布局、绩效指标、价格加载和报告输出 6 个模块。

无 CLI 入口，所有符号通过 Python import 使用。

## 模块概览

| 模块 | 用途 | 公开符号 |
|---|---|---|
| `audit.py` | 聚宽审计日志解析 | `load_rebalance_events`, `load_run_start_params` |
| `calendar.py` | 周频交易日历与前向收益 | `first_trading_days_by_week`, `build_weekly_anchor_frame`, `forward_return_frame` |
| `layout.py` | 研究项目文件布局 | `ResearchProjectLayout`, `ResearchRunLayout` |
| `metrics.py` | 绩效指标与统计检验 | `parse_cumulative_returns_md`, `performance_metrics`, `paired_block_bootstrap`, `rolling_sharpe`, `yearly_metrics` |
| `prices.py` | 价格数据加载 | `load_price_bundle`, `PriceFrames` |
| `reporting.py` | 报告与持久化 | `markdown_table`, `write_json` |

---

## audit.py — 审计日志解析

```python
from scripts.research.research_core.audit import load_rebalance_events, load_run_start_params
```

### load_rebalance_events(path) → list[dict]

从审计日志 JSONL 中提取所有 `rebalance_signals` 事件，保持原始顺序返回。每行 JSONL 中 `event == "rebalance_signals"` 的事件会被收集。

### load_run_start_params(path) → dict

返回第一个 `run_start` 事件的 `params` 字段（策略参数快照）。若文件不含 `run_start` 事件则抛 `ValueError`。

---

## calendar.py — 交易日历

```python
from scripts.research.research_core.calendar import (
    first_trading_days_by_week, build_weekly_anchor_frame, forward_return_frame,
)
```

### first_trading_days_by_week(calendar, start, end) → pd.DatetimeIndex

返回 `[start, end]` 区间内每个自然周（周日为界）的第一个交易日。

### build_weekly_anchor_frame(calendar, start, end, horizons) → pd.DataFrame

构建周频信号锚点表。每行一个周信号日，包含：
- `signal_date` — 信号日（当周第一个交易日）
- `asof_date` — 数据截止日（信号日前一交易日）
- `future_{N}d` — 未来第 N 个交易日历日期

### forward_return_frame(close, anchors, horizons, codes=None) → pd.DataFrame

计算前向收益。以 `anchors` 中的 `asof_date` 收盘价为基准，计算到 `future_{N}d` 的收益率。

返回 `[signal_date, asof_date, etf, forward_{N}d, ...]` 长格式 DataFrame。

---

## layout.py — 文件布局

```python
from scripts.research.research_core.layout import ResearchProjectLayout, ResearchRunLayout
```

### ResearchProjectLayout

研究项目目录布局的不可变 dataclass。

```python
layout = ResearchProjectLayout.from_path("my_project")

# 属性
layout.root            # Path
layout.docs_dir        # root/docs/
layout.raw_inputs_dir  # root/inputs/raw/
layout.exports_dir     # root/exports/
layout.runs_dir        # root/runs/

# 方法
layout.raw_input_path("prices.json")  # root/inputs/raw/prices.json
layout.run("my-run-id")               # → ResearchRunLayout
layout.ensure_project_dirs()          # 创建所有子目录
```

### ResearchRunLayout

单次分析运行的目录布局。

```python
run = layout.run("fast-01")

# 属性
run.root           # root/runs/fast-01/
run.reports_dir    # root/runs/fast-01/reports/
run.tables_dir     # root/runs/fast-01/tables/
run.curves_dir     # root/runs/fast-01/curves/
run.checkpoints_dir # root/runs/fast-01/checkpoints/
run.manifest_path  # root/runs/fast-01/manifest.json
run.status_path    # root/runs/fast-01/status.json

run.ensure_dirs()  # 创建所有子目录
```

---

## metrics.py — 绩效指标

```python
from scripts.research.research_core.metrics import (
    parse_cumulative_returns_md, performance_metrics, paired_block_bootstrap,
    rolling_sharpe, yearly_metrics,
)
```

### parse_cumulative_returns_md(path) → pd.Series

解析仓库 `daily_returns.md` 文件。注意：该文件存储的是**累计收益**，函数自动转换为逐日收益。

返回 `pd.Series`，index 为 `DatetimeIndex`，values 为日收益率。

### performance_metrics(returns) → dict

从日收益序列计算：

| 键 | 含义 |
|---|---|
| `total_return` | 总收益率 |
| `annual_return` | 年化收益率 |
| `volatility` | 年化波动率 |
| `sharpe` | 年化 Sharpe ratio |
| `max_drawdown` | 最大回撤（负值） |

空序列返回全零字典。

### paired_block_bootstrap(lhs, rhs, *, n_boot=2000, block=40, seed=42) → dict

配对 block bootstrap 检验。H₀：`mean(rhs - lhs) = 0`。

返回 `{observed, ci_low, ci_high, p_value}`，均为 float。

### rolling_sharpe(returns, window=252) → pd.Series

滚动年化 Sharpe ratio。

### yearly_metrics(returns) → pd.DataFrame

按日历年分组计算绩效指标。返回 `[year, days, total_return, annual_return, volatility, sharpe, max_drawdown]`。

---

## prices.py — 价格数据

```python
from scripts.research.research_core.prices import load_price_bundle, PriceFrames
```

### PriceFrames

不可变 dataclass，包含归一化日频价格数据：

```python
frames = PriceFrames(
    close=...,    # pd.DataFrame: dates × codes
    high=...,
    low=...,
    money=...,
    calendar=..., # pd.DatetimeIndex
)
```

### load_price_bundle(path, codes=None) → PriceFrames

加载仓库标准的聚宽价格导出 JSON（支持 `.gz` 压缩）。`codes` 参数可按需筛选标的。

---

## reporting.py — 报告输出

```python
from scripts.research.research_core.reporting import markdown_table, write_json
```

### markdown_table(frame) → str

将 DataFrame 渲染为 Markdown 表格字符串。空 DataFrame 返回 `"_无可用记录。_"`。

### write_json(path, payload) → None

将 Python 对象以 UTF-8 编码、2 空格缩进写入 JSON 文件。

---

## 依赖关系

```
research_core  ←  platform  ←  cli.py
    ↑               ↑
    ├── etf_window_research
    ├── momentum_tilt_research
    └── cash_decomposition (via platform.datasets)
```

`research_core` 是零依赖基础层：不依赖 `platform`、不依赖任何具体策略代码。仅依赖 `pandas`、`numpy` 标准数据科学栈。
