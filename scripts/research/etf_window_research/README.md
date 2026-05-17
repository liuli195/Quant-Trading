# etf_window_research — ETF 时间窗异质性研究工具

研究 ETF 趋势均线窗口长度对策略表现的影响，支持导出聚宽研究脚本、获取远程价格数据和本地分析。

**入口**：`python -m scripts.research.etf_window_research.cli`

## 子命令

### export-script — 导出聚宽研究脚本

生成本地不可运行的 JoinQuant 云端研究 Python 脚本。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.etf_window_research.cli export-script `
  --project-dir <dir> [--output <path>] [--export-path <path>] [--history-start <date>]
```

参数：
- `--project-dir` — 必填，研究项目目录
- `--output` — 可选，输出脚本路径（默认：`<project-dir>/joinquant_research_export.py`）
- `--export-path` — 可选，聚宽导出路径（默认：`/tmp/joinquant_price_export.json`）
- `--history-start` — 可选，历史数据起始日（默认由 `DEFAULT_HISTORY_START` 指定）

### fetch — 获取远程价格数据

通过 Chrome 自动化从聚宽获取原始价格数据包。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.etf_window_research.cli fetch `
  --project-dir <dir> [--output <path>] [--export-path <path>] `
  [--history-start <date>] [--user-data-dir <dir>] [--headless] [--slow-mo <ms>]
```

参数：
- `--project-dir` — 必填，研究项目目录
- `--output` — 可选，输出路径（默认：`<project-dir>/raw_price_bundle.json`）
- `--export-path` — 可选，聚宽导出路径
- `--history-start` — 可选，历史数据起始日
- `--user-data-dir` — 可选，Chrome 用户数据目录（默认：`.local/chrome-jq`）
- `--headless` — 可选，启用无头模式
- `--slow-mo` — 可选，操作间延迟毫秒数（默认：0）

### analyze — 本地分析

运行本地分析并将结果持久化到一次 run。

```powershell
.\.venv\Scripts\python.exe -m scripts.research.etf_window_research.cli analyze `
  --project-dir <dir> --run-id <id> [--raw-data <path>] [--audit-log <path>]
```

参数：
- `--project-dir` — 必填，研究项目目录
- `--run-id` — 必填，运行 ID
- `--raw-data` — 可选，原始价格数据路径
- `--audit-log` — 可选，审计日志路径

## 典型工作流

```
export-script → 在聚宽云端运行导出 → fetch 拉取数据 → analyze 本地分析
```

## 依赖

- `scripts.research.research_core`（共享研究库）
- Chrome 浏览器（`fetch` 子命令需要）
