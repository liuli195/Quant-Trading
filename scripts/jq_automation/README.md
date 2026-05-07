# JoinQuant Cloud Automation (jq-auto)

## Quick Reference

`jq-auto` 将本地策略代码上传到聚宽策略编辑器，执行云端编译与正式回测，通过**研究环境 `get_backtest()`** 或**详情页只读 API** 抓取回测结果，按仓库约定落盘。

```powershell
# 最小完整流程
.\.venv\Scripts\python.exe -m scripts.jq_automation compile-check strategies\<s>\<s>.py --write-upload
.\.venv\Scripts\python.exe -m scripts.jq_automation upload strategies\<s>\<s>.py --strategy-name <s>
.\.venv\Scripts\python.exe -m scripts.jq_automation run <scenario.json> --yes --backtest-timeout 240
```

策略仅在聚宽云端运行。本地仅做：语法检查、参数改写、浏览器自动化、产物归档、结果对比。

---

## Command Reference

每个命令的签名、参数、前置条件、副作用、返回码自包含。

### compile-check

```text
签名: python -m scripts.jq_automation compile-check <strategy_file> [--write-upload]
前置: strategy_file 存在且可被 py_compile
副作用: 无（--write-upload 时生成 <strategy>__upload.py）
返回码: 0=通过  2=语法/路径错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `strategy_file` | Path | 是 | — | 本地策略 .py 文件路径 |
| `--write-upload` | flag | 否 | false | 同时生成去注释后的上传文件 |

### upload

```text
签名: python -m scripts.jq_automation upload <strategy_file> [flags]
前置: strategy_file 通过 py_compile；聚宽已登录（首次非 headless）；策略编辑器存在或提供 --edit-url
副作用: 覆盖聚宽编辑器代码；默认触发云端编译
返回码: 0=成功  2=编译失败/浏览器错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `strategy_file` | Path | 是 | — | 本地策略文件 |
| `--strategy-name` | str | 否 | 文件 stem | 聚宽策略列表中的名称 |
| `--edit-url` | str | 否 | — | 直接指定编辑页 URL，跳过列表查找 |
| `--no-compile` | flag | 否 | false | 上传后不触发云端编译 |
| `--user-data-dir` | Path | 否 | `.local/chrome-jq/` | Chrome profile 目录 |
| `--headless` | flag | 否 | false | 无头模式（首次登录不能用） |
| `--slow-mo` | int | 否 | 0 | 浏览器动作间延迟(ms) |

### run

```text
签名: python -m scripts.jq_automation run <scenario.json> [flags]
前置: scenario.json 存在且通过 schema 校验（见配置 schema 节）；已手动确认（--yes 或交互输入 RUN）
副作用: 消耗云端额度、写入 quota ledger、回写 manifest、生成 backtest_runs/<run_id>/
返回码: 0=成功  1=用户取消/执行失败  2=配置/校验错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `scenario_config` | Path | 是 | — | scenario.json 路径 |
| `--yes` | flag | 是(安全) | false | 跳过交互确认，确认发起云端回测 |
| `--backtest-timeout` | int | 否 | 180 | 等待回测完成超时(秒)，不影响云端任务 |
| `--result-source` | enum | 否 | auto | `auto` / `research` / `detail`（见数据提取 pipeline 节） |
| `--user-data-dir` | Path | 否 | `.local/chrome-jq/` | Chrome profile 目录 |
| `--headless` | flag | 否 | false | 无头模式 |
| `--slow-mo` | int | 否 | 0 | 浏览器动作间延迟(ms) |

### fetch

```text
签名: python -m scripts.jq_automation fetch <backtestId|detail-url> [flags]
前置: 回测已完成；浏览器可打开详情页（或研究页）
副作用: 生成 backtest_runs/<run_id>/ 产物目录
返回码: 0=成功  2=抓取/浏览器错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `target` | str | 是 | — | 回测详情页 URL 或 backtestId |
| `--strategy` | str | 是 | — | 策略目录名 |
| `--run-id` | str | 否 | 自动生成 | 本地 run 目录名，格式 `YYYYMMDD-HHMM-bt<id>` |
| `--strategy-name` | str | 否 | strategy 值 | 聚宽策略名 |
| `--start-date` | str | 否 | "" | 用于 metadata 记录 |
| `--end-date` | str | 否 | "" | 用于 metadata 记录 |
| `--capital` | float | 否 | — | 用于 metadata 记录 |
| `--frequency` | str | 否 | "每天" | 用于 metadata 记录 |
| `--py-version` | str | 否 | "Python3" | 用于 metadata 记录 |
| `--backtest-timeout` | int | 否 | 180 | 等待详情页加载超时(秒) |
| `--result-source` | enum | 否 | auto | `auto` / `research` / `detail` |

### batch

```text
签名: python -m scripts.jq_automation batch <manifest.json> [flags]
前置: manifest.json 存在；对应的 scenario.json 文件存在
副作用: 消耗云端额度、更新 manifest 状态、生成 backtest_runs/ 产物
返回码: 0=全部完成(或无待执行项)  1=有 run 失败  2=配置错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `manifest_json` | Path | 是 | — | manifest.json 路径 |
| `--scenario` | str[] | 否 | — | 限制到指定 scenario_id，可重复指定 |
| `--yes` | flag | 是(安全) | false | 跳过交互确认 |
| `--backtest-timeout` | int | 否 | 180 | 每个 run 的等待超时(秒) |
| `--result-source` | enum | 否 | auto | `auto` / `research` / `detail` |
| `--user-data-dir` | Path | 否 | `.local/chrome-jq/` | Chrome profile 目录 |
| `--headless` | flag | 否 | false | 无头模式 |
| `--slow-mo` | int | 否 | 0 | 浏览器动作间延迟(ms) |

### ab expand

```text
签名: python -m scripts.jq_automation ab expand <ab_config.json> [--force-reset-pending]
前置: ab_config.json 存在且通过校验；code_source.ref 可被 git rev-parse 解析；code_source.path 存在于该 commit
副作用: 冻结 commit SHA 到 manifest；物化源码到 .local/jq-automation/ab/；生成 scenario.json
返回码: 0=成功  2=配置/Git 错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `ab_config` | Path | 是 | — | A/B 实验配置 JSON 路径 |
| `--force-reset-pending` | flag | 否 | false | 重置所有 variant 为 pending |

### ab run

```text
签名: python -m scripts.jq_automation ab run <ab_config.json> [flags]
前置: 已执行 ab expand；manifest 中有该实验的 pending/failed variants
副作用: 串行上传、编译、回测、抓取每个 variant；回写 manifest
返回码: 0=全部完成  1=有 variant 失败  2=配置错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `ab_config` | Path | 是 | — | A/B 实验配置 JSON 路径 |
| `--yes` | flag | 是(安全) | false | 跳过交互确认 |
| `--backtest-timeout` | int | 否 | 180 | 每个 variant 等待超时(秒) |
| `--result-source` | enum | 否 | auto | `auto` / `research` / `detail` |

### ab report

```text
签名: python -m scripts.jq_automation ab report <config_or_manifest> --experiment <id> [--allow-partial]
前置: 清单中存在该 experiment_id；至少 baseline 已完成（--allow-partial 可跳过此要求）
副作用: 生成 report/ab-<experiment_id>-comparison.md 和 -summary.json
返回码: 0=成功  1=baseline 未完成(无 --allow-partial 时)  2=配置错误
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `ab_config_or_manifest` | Path | 是 | — | A/B 配置或 manifest JSON 路径 |
| `--experiment` | str | 是 | — | 实验 ID |
| `--allow-partial` | flag | 否 | false | baseline 未完成时仍生成部分报告 |

---

## Configuration Schemas

### scenario.json

**文件路径约定：** `strategies/<strategy>/test_batches/<batch_id>/scenarios/<scenario_id>/scenario.json`

**Schema 字段：**

| 字段 | 类型 | 必填 | 默认 | 约束 | 说明 |
|------|------|------|------|------|------|
| `strategy_file` | Path | 是 | — | 文件存在，通过 py_compile | 本地策略文件绝对路径 |
| `scenario_id` | str | 是 | — | 非空 | 场景 ID，通常等于目录名 |
| `start_date` | str | 是 | — | `YYYY-MM-DD`，∈ 有效日期 | 回测起始日 |
| `end_date` | str | 是 | — | `YYYY-MM-DD`，≥ start_date | 回测结束日 |
| `capital` | int\|float\|str | 是 | — | > 0，支持 `"100,000"` 格式 | 初始资金 |
| `strategy` | str | 否 | 从 strategy_file 路径推断 | — | 策略目录名 |
| `batch_id` | str | 否 | — | — | 关联的 batch，用于 manifest 回写 |
| `strategy_name` | str | 否 | strategy_file stem | — | 聚宽策略列表中的名称 |
| `edit_url` | str | 否 | — | — | 聚宽编辑器 URL，绕过列表查找 |
| `frequency` | str | 否 | `"1d"` | `1d`/`1m`/`tick`/`5m`/`15m`/`30m`/`60m` | 回测频率 |
| `py_version` | str | 否 | `"Python3"` | `Python3`/`Python2` | 聚宽 Python 版本 |
| `estimated_minutes` | float | 否 | 0.0 | ≥ 0 | 预计云端耗时，用于 quota guardrail |
| `run_id` | str | 否 | 自动生成 | — | 指定产物目录名 |
| `result_source` | enum | 否 | `"auto"` | `auto`/`research`/`detail` | 数据来源策略（见数据提取 pipeline 节） |
| `params_base` | dict | 否 | `{}` | — | batch 场景的基础参数覆盖 |
| `params_diff` | dict | 否 | `{}` | 见参数覆盖节约束 | 单次 run 的参数覆盖 |
| `sweep` | object | 否 | — | 见参数扫描节 | 在 batch 中展开为多个参数组合 |

**最小示例：**

```json
{
  "strategy_file": "d:/My Project/Quant Trading/strategies/etf_factor_rotation/etf_factor_rotation.py",
  "strategy": "etf_factor_rotation",
  "scenario_id": "s01-smoke",
  "start_date": "2026-03-01",
  "end_date": "2026-03-31",
  "capital": 100000,
  "frequency": "1d",
  "py_version": "Python3",
  "estimated_minutes": 5,
  "batch_id": "20260507-smoke",
  "result_source": "auto"
}
```

### manifest.json

**文件路径约定：** `strategies/<strategy>/test_batches/<batch_id>/manifest.json`

**Schema 字段：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `batch_id` | str | 是 | 批次 ID |
| `strategy` | str | 是 | 策略目录名 |
| `scenarios` | dict[str, object] | 是 | scenario_id → 状态对象 |
| `scenarios.<id>.status` | enum | 否 | `pending`/`in_progress`/`completed`/`failed`/`cancelled` |
| `scenarios.<id>.runs[]` | array | 否 | 展开后的 run 列表 |
| `scenarios.<id>.runs[].label` | str | 是 | run 标签（sweep 展开时自动生成） |
| `scenarios.<id>.runs[].params_diff` | dict | 否 | 该 run 的参数覆盖 |
| `scenarios.<id>.runs[].status` | enum | 是 | run 级状态 |
| `scenarios.<id>.runs[].run_id` | str | 否 | 成功后写入的产物目录名 |
| `scenarios.<id>.runs[].backtest_id` | str | 否 | 聚宽回测 ID |
| `scenarios.<id>.runs[].backtest_url` | str | 否 | 聚宽回测详情页 URL |
| `scenarios.<id>.runs[].uploaded_code_sha256` | str | 否 | A/B 实验写入的上传代码哈希 |

**最小示例：**

```json
{
  "batch_id": "20260507-smoke",
  "strategy": "etf_factor_rotation",
  "scenarios": {
    "s01-smoke": { "status": "pending" }
  }
}
```

---

## Data Extraction Pipeline

### result_source 决策树

```
IF 命令行传了 --result-source → 使用命令行值
ELSE IF scenario.json 有 result_source → 使用配置值
ELSE → "auto"
```

```
result_source 选择:
├── auto (默认)
│   └── 研究环境 get_backtest() → 失败则详情页 API → 失败则 DOM fallback
├── research
│   └── 仅研究环境 get_backtest()，失败即报错（用于验证研究环境能力）
└── detail
    └── 仅详情页 API bundle → 失败则 DOM fallback（旧行为）
```

### 三阶段提取流程

`run` / `fetch` / `batch` / `ab run` 中的回测数据抓取按以下流程执行：

**阶段 1 — 详情页辅助数据收集（仅 auto/research 模式）**

在进入研究环境之前，先从回测详情页抓取研究环境不提供的数据：
- `runtime` — 实际 CPU 耗时（`needSeconds`），用于 quota 核算
- `source` — 回测时使用的策略源码
- `profile_text` — 性能 profiling 文本
- `logs_partial` / `logs_count` — 平台日志元数据（条数、是否截断）

此步骤失败不阻塞后续流程，`supplemental_detail` 标记 `detail_api_used: false`。

**阶段 2 — 研究环境 get_backtest()（auto/research 模式）**

1. 导航到 `https://www.joinquant.com/research`
2. 等待研究环境 iframe 加载完成
3. 通过 Jupyter REST API 发现 API base URL（探测 `kernelspecs` 端点）
4. 创建 `python3` kernel
5. 通过 WebSocket 在 kernel 中执行导出脚本：
   - 调用 `get_backtest(backtest_id)` 获取回测结果对象
   - 依次调用 `.get_results()` / `.get_positions()` / `.get_orders()` / `.get_records()` / `.get_risk()` / `.get_period_risks()` / `.get_balances()`
   - 使用研究环境 `write_file()` 将结果写为 JSON
6. 通过 `ResearchFileClient` 读取导出的 JSON 文件
7. `normalize_research_bundle()` 规范化为 schema v3

**阶段 3 — 详情页 API/DOM fallback（auto/detail 模式）**

当研究环境不可用（auto 模式）或显式指定 detail 模式时：
1. 在回测详情页注入 `extract.js`，调用页面内部 XHR 只读接口
2. 抓取 stats / transactions / positions / result_rows / risk_tabs / logs / profile / source / runtime
3. 若 API bundle 失败，fallback 到 DOM tab 文本抓取（完整性较差）

### Schema v2 vs v3

| 属性 | v2 (详情页 API bundle) | v3 (研究环境 get_backtest) |
|------|------------------------|---------------------------|
| `metadata.schema_version` | 2 或不存在 | 3 |
| `metadata.extraction_method` | `joinquant_detail_readonly_api` | `joinquant_research_get_backtest` |
| 收益数据 | `result_rows[]` | `results[]` |
| 交易数据 | `transactions.rows[]` | `orders[]` |
| 持仓数据 | `positions.rows[]` | `positions[]` |
| record 记录 | 不完整（仅图表字段） | `records[]`（完整） |
| 每日市值 | 无 | `balances[]` |
| 风险指标 | `risk_tabs`（每指标一个 tab） | `risk`（汇总 dict）+ `period_risks`（分期 dict） |
| 平台日志 | `logs.rows[]`（≤~1000 条） | 不提供（`supplemental_detail.logs_partial`） |
| 源码 | `source` | 不提供（`supplemental_detail.source`） |
| 运行时 | `runtime.data.needSeconds` | 不提供（`supplemental_detail.runtime`） |
| profile | `profile_text` | 不提供（`supplemental_detail.profile_text`） |

### bundle 分派逻辑

`save_backtest_data.py` 的 `save_api_data()` 入口根据以下规则分派到对应处理器：

```
IF metadata.schema_version == 3           → save_research_bundle_data()
ELSE IF metadata.schema_version == 2
   OR "risk_tabs" in api_data             → save_api_bundle_data()
ELSE                                       → 旧版 API 单接口格式处理
```

### JQ_AUTO_FORCE_RESEARCH_FAILURE

设置此环境变量为任意值后，研究环境抓取将立即抛出 `ResearchFetchError`，强制走 fallback 链路。用于本地测试 auto fallback 和 detail 模式。

```powershell
$env:JQ_AUTO_FORCE_RESEARCH_FAILURE = "1"
```

---

## Artifact Schema

### 产物目录树

```text
strategies/<strategy>/backtest_runs/<run_id>/
├── api_export.json          # 原始 bundle（schema v2 或 v3）
├── dom_tabs_persisted.json  # DOM fallback 数据（仅 fallback 时存在）
├── metadata.json            # 运行元数据
├── summary_metrics.json     # 核心绩效指标
├── all_data.json            # tabs/report 索引
├── tabs_raw/
│   ├── daily_returns.md     # 每日收益（必有）
│   ├── transactioninfo.md   # 交易明细（必有）
│   ├── positioninfo.md      # 持仓与收益（必有）
│   ├── logs.md              # 策略日志（必有）
│   ├── profile.md           # 性能 profile（必有）
│   ├── records.md           # Record 记录（仅 v3）
│   ├── balances.md          # 每日账户市值（仅 v3）
│   ├── risk.md              # 风险指标汇总（仅 v3）
│   ├── period_risks.md      # 分期风险（仅 v3）
│   └── *.md                 # v2 风险指标分文件（算法收益/波动率/alpha/beta/sharpe等）
└── report/
    ├── backtest_report.md   # 回测数据汇总
    ├── strategy-analysis.md # 策略分析（后续流程补齐）
    └── performance-analysis.md # 性能分析（后续流程补齐）
```

### api_export.json

存在条件：研究环境抓取成功 或 详情页 API bundle 抓取成功。
不存在条件：走了 DOM fallback（此时有 `dom_tabs_persisted.json`）。

**v3 顶层字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `metadata` | dict | schema_version=3, extraction_method, backtest_id, 区间, 资金 等 |
| `results` | list[dict] | get_results() 返回的每日收益 |
| `positions` | list[dict] | get_positions() 返回的持仓记录 |
| `orders` | list[dict] | get_orders() 返回的订单/交易记录 |
| `records` | list[dict] | get_records() 返回的 record 记录 |
| `risk` | dict | get_risk() 返回的风险指标汇总 |
| `period_risks` | dict | get_period_risks() 返回的分期风险 |
| `balances` | list[dict] | get_balances() 返回的每日账户市值 |
| `supplemental_detail` | dict | 详情页补充数据（runtime/source/profile/logs） |
| `counts` | dict | 各数组元素计数 |
| `partial` | dict | 各数据源是否截断 |

### metadata.json

**公共字段（所有提取方式均写入）：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `strategy_name` | str | 聚宽策略名 |
| `start_date_effective` | str | 回测起始日 |
| `end_date_effective` | str | 回测结束日 |
| `capital` | int\|float | 初始资金 |
| `backtest_id` | str | 聚宽回测 ID |
| `backtest_url` | str | 回测详情页 URL |
| `frequency` | str | 回测频率 |
| `py_version` | str | Python 版本 |
| `extraction_method` | str | 实际使用的提取方式 |
| `primary_extraction_method` | str | 主提取方式（研究环境或详情页 API） |

**研究环境 fallback 时额外字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `attempted_primary_extraction_method` | str | 尝试的主提取方式（固定为 `joinquant_research_get_backtest`） |
| `fallback_extraction_method` | str | 回退后实际使用的方式 |
| `research_export_path` | str | 研究环境目标导出路径 |
| `research_downloaded` | bool | 研究环境数据是否下载成功 |
| `research_fetch_failed` | bool | 研究环境抓取是否失败 |
| `research_fetch_error` | str | 研究环境失败原因 |
| `detail_api_used` | bool | 是否使用了详情页 API |
| `internal_backtest_id` | str | 聚宽内部 backtestId（可能与 backtest_id 不同） |
| `id_mismatch` | bool | 内部 ID 与 URL ID 不一致时设置 |

### summary_metrics.json

| 字段 | 来源(v2) | 来源(v3) | 格式 |
|------|----------|----------|------|
| `策略收益` | stats.algorithm_return | risk.algorithm_return | `"12.34%"` |
| `策略年化收益` | stats.annual_algo_return | risk.annual_algo_return | `"15.67%"` |
| `基准收益` | stats.benchmark_return | risk.benchmark_return | `"8.90%"` |
| `超额收益` | stats.excess_return | risk.excess_return | `"3.44%"` |
| `最大回撤` | stats.max_drawdown | risk.max_drawdown | `"-5.12%"` |
| `阿尔法` | risk_tabs.alpha | risk.alpha | `"0.045"` |
| `贝塔` | risk_tabs.beta | risk.beta | `"0.850"` |
| `夏普比率` | risk_tabs.sharpe | risk.sharpe | `"1.234"` |
| `索提诺比率` | risk_tabs.sortino | risk.sortino | `"1.567"` |
| `信息比率` | risk_tabs.information | risk.information | `"0.890"` |
| `策略波动率` | risk_tabs.algo_volatility | risk.algorithm_volatility | `"0.150"` |
| `基准波动率` | risk_tabs.benchmark_volatility | risk.benchmark_volatility | `"0.120"` |

---

## State Machines

### Run 状态

```
pending ──→ in_progress ──→ completed  (终态)
                │
                └──→ failed ──→ pending  (batch 重选时)
                │
                └──→ cancelled (终态)
```

- batch 执行时，`status=failed` 的 run 会被重新选中执行
- `status=completed` 的 run 不会被重新执行
- scenario 顶层 status = f(runs[].status): 有 failed → failed; 有 in_progress → in_progress; 全 completed → completed

### Manifest 展开状态

```
scenario.status=pending, 无 runs[]
  │
  └── batch 首次执行 ──→ 读取 scenario.json, expand sweep
                          │
                          └──→ 写入 runs[] （每个组合一个 run entry, status=pending）
                          └──→ 继续执行各 pending run

scenario.status=pending, 有 runs[]
  │
  └── batch 执行 ──→ 选取 runs[].status != completed 的条目执行
```

### Quota Ledger 条目状态

```
started ──→ completed  (终态, 计入消耗)
  │
  └──→ failed  (不计入消耗，除非已有 actual_minutes)
  │
  └──→ cancelled  (终态, 如有 actual_minutes 则计入消耗)
```

---

## Parameter Override (params_diff)

`params_diff` 改写策略源码 `set_parameter()` 函数内的单行 `g.<name> = <value>` 赋值。改写后的临时代码上传到聚宽，不改动原始策略文件。

**支持的值类型：** `int`, `float`, `bool`, `str`, `null`, 及上述标量组成的 `list`

**约束：**
- 目标参数必须在 `set_parameter()` 中存在
- 同一参数不能在 `set_parameter()` 中赋值多次
- 目标赋值必须是单行（不支持跨行表达式）
- 如果同名 `g.<name>` 只在其他函数中出现，拒绝改写

**示例：**

```json
{ "params_diff": { "TopK": 3, "TargetVol": 0.10, "fq_mode": null } }
```

---

## Parameter Sweep

参数扫描用 `scenario.json` 的 `sweep` 字段声明，通过 `batch` 命令执行。`run` 命令要求一个 scenario 只能展开成一个 run。

### grid sweep

笛卡尔积展开，适合小规模网格扫描：

```json
{
  "sweep": {
    "strategy": "grid",
    "dimensions": {
      "TopK": [2, 3],
      "TargetVol": [0.10, 0.12],
      "RSRS_M": [600, 800]
    }
  }
}
```

展开 2×2×2=8 个 run，label 格式：`TopK=2_TargetVol=0.1_RSRS_M=600`

### list sweep

手动挑选组合，适合从扫描结果中提炼候选：

```json
{
  "sweep": {
    "strategy": "list",
    "combinations": [
      { "label": "low-vol", "params": { "TopK": 2, "TargetVol": 0.08 } },
      { "label": "balanced", "params": { "TopK": 3, "TargetVol": 0.12 } }
    ]
  }
}
```

### 执行流程

1. batch 首次执行时展开 sweep，写入 manifest
2. 后续重跑只执行 pending/failed 的组合
3. 完成后人工比较各 run 的 `summary_metrics.json` 和 `report/`，选择候选
4. 扫描出的最优组合建议放入 A/B 测试做二次确认

---

## AB Test System

A/B 测试比较多个"最终上传代码快照"。配置路径：`strategies/<strategy>/test_batches/<batch_id>/abtests/<experiment_id>.json`

### 配置结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `experiment_id` | str | 是 | 实验唯一 ID |
| `strategy` | str | 是 | 策略目录名 |
| `batch_id` | str | 是 | 关联 batch |
| `baseline` | str | 是 | 基准 variant label，用于 delta 对比 |
| `controls` | list[str] | 否 | 额外对照组 label |
| `base` | object | 是 | 所有 variant 的默认配置（区间、资金、频率等） |
| `base.code_source` | object | 是 | 默认代码来源 `{type:"git", ref, path}` |
| `variants` | list[object] | 是 | 候选列表 |
| `variants[].label` | str | 是 | 候选标签，必须唯一 |
| `variants[].role` | enum | 否 | `control` / `variant` |
| `variants[].code_source` | object | 否 | 覆盖 base.code_source |
| `variants[].params_mode` | enum | 是 | `params_diff`（改写 set_parameter）/ `baked_in_git`（不改写） |
| `variants[].params_diff` | dict | 否 | params_mode=params_diff 时的参数覆盖 |
| `variants[].scan_source` | object | 否 | `{batch_id, scenario_id, run_label}` 来源追溯 |
| `metrics` | list[object] | 是 | 对比指标 `{key, direction: maximize|minimize}` |

### 三步流程

```
ab expand → ab run → ab report
```

- **expand**：冻结 commit SHA，物化源码，生成 scenario.json，写入 manifest
- **run**：在同一浏览器 session 中串行执行 pending/failed variants（避免编辑器状态互相覆盖）。每个 variant：上传 → 编译 → 回测 → 抓取 → 回写 manifest
- **report**：生成 `report/ab-<experiment_id>-comparison.md` 和 `-summary.json`

### manifest 写回字段

每个 variant 完成后在 manifest 中写入：

| 字段 | 说明 |
|------|------|
| `run_id` | 本地产物目录名 |
| `backtest_id` | 聚宽回测 ID |
| `backtest_url` | 回测详情页 URL |
| `uploaded_code_sha256` | 上传代码的 SHA256（绑定候选→代码→回测） |
| `status` | completed / failed |

### 安全约束

- `ab expand` 冻结 commit SHA 后再执行，`ab run` 使用冻结的 commit 而非重新解析 branch
- 配置 hash 改变时，已有 completed run 的实验拒绝覆盖（需新建 experiment_id）
- 串行执行不并发启动多个回测

---

## Quota Management

### 数据源优先级

1. **聚宽页面实时数据**（优先）：从编辑器页面 DOM 解析 `runTimeInfo`，获取今日已用分钟和免费额度上限
2. **本地 quota ledger**（fallback）：`docs/joinquant-data/quota_ledger/<YYYYMMDD>.json`

### 账本结构

```json
{
  "budget_minutes": 60,
  "runs": [
    {
      "scenario_id": "s01-smoke",
      "run_id": "20260507-0343-btabc123",
      "estimated_minutes": 5,
      "actual_minutes": 4.83,
      "status": "completed",
      "started_at": "2026-05-07T03:43:00",
      "updated_at": "2026-05-07T03:48:00"
    }
  ]
}
```

### 消耗计算

```
IF run.actual_minutes 存在 → 使用 actual_minutes
ELSE IF run.status NOT IN (failed, cancelled) → 使用 estimated_minutes
ELSE → 不计入（failed 无实际耗时不计数，cancelled 有实际耗时时计数）
```

`actual_minutes` 来源于：
- v2 bundle: `runtime.data.needSeconds / 60`
- v3 bundle: `supplemental_detail.runtime.data.needSeconds / 60`

### guardrail

执行前检查：
- 从聚宽页面读到实际剩余分钟 → 若 `estimated_minutes > actual_remaining` 则拒绝
- 页面读取失败 → fallback 本地 ledger 计算 `remaining_minutes()`

---

## Path Aliases

工具落盘通过 `path_aliases.json` 中的 alias 解析，不硬编码路径。脚本中新增结果目录引用应使用 `scripts.path_tools.aliases.resolve_path()` 或 `ensure_dir()`。

| alias | 用途 |
|-------|------|
| `backtest_run` | `strategies/<strategy>/backtest_runs/<run_id>` |
| `backtest_report_dir` | 单次 run 的 `report/` |
| `backtest_tabs_dir` | 单次 run 的 `tabs_raw/` |
| `test_batch` | `strategies/<strategy>/test_batches/<batch_id>` |
| `test_batch_scenarios` | batch 下的 `scenarios/` |
| `test_batch_abtests` | batch 下的 `abtests/` |
| `test_batch_report_dir` | batch 下的 `report/` |
| `test_scenario` | `test_batch_scenarios/<scenario_id>` |
| `joinquant_quota_ledger` | `docs/joinquant-data/quota_ledger/` |

---

## Error Index

| 异常类型 | 模块 | 原因 | 修复方向 |
|----------|------|------|----------|
| `ConfigError` | config.py | scenario.json 缺少必填字段、日期格式错误、频率不支持、result_source 值非法 | 检查配置文件，对照 schema 修复 |
| `LocalCheckError` | local.py | py_compile 失败、params_diff 目标不在 set_parameter/多行赋值/非参数位置 | 修复策略代码或调整 params_diff |
| `CompileFailed` | browser.py | 聚宽云端编译失败（有 Traceback） | 查看命令输出中的编译错误，优先本地 compile-check |
| `AutomationError` | browser.py | 浏览器操作超时、元素未找到、页面状态异常 | 检查 --slow-mo 调试；确认聚宽页面结构未变；首次不使用 --headless |
| `ResearchFetchError` | research.py | 研究环境不可用：iframe 未加载、Jupyter API 不响应、kernel 执行失败、导出文件无法读取 | 检查 backtest_id 有效性；确认研究页可访问；设 `JQ_AUTO_FORCE_RESEARCH_FAILURE` 测试 fallback；auto 模式会自动回退 |
| `ManifestError` | manifest.py | manifest.json 格式错误或缺少必填字段 | 对照 manifest schema 修复 |
| `QuotaError` | quota.py | 云端额度不足 | 检查聚宽页面实时用量或本地 ledger；调小 estimated_minutes；等待次日重置 |
| `ArtifactError` | artifacts.py | save_backtest_data.py 未找到或产物落盘失败 | 确认文件存在；检查磁盘空间 |
| `ABConfigError` | abtest.py | A/B 配置格式错误或缺少必填字段 | 对照 A/B 配置 schema 修复 |
| `ABExpandError` | abtest.py | Git ref 无法解析或路径不在 commit 中 | 确认 ref 可被 `git rev-parse` 解析；确认文件路径存在于该 commit |
| `ABReportError` | abtest.py | baseline 未完成、指标缺失 | 检查 manifest 中 baseline run 状态；使用 --allow-partial 查看部分结果 |
| `GitVersionError` | git_versioning.py | git show/rev-parse 失败 | 确认 Git 仓库状态正常；确认 ref 有效 |

---

## Troubleshooting (Decision Trees)

### 找不到聚宽策略编辑页

```
IF 首次运行 AND NOT --headless → 确认已手动登录聚宽
IF 策略列表按名称匹配失败 → 手动打开编辑页，URL 写入 scenario.json 的 edit_url 或传 --edit-url
```

### 云端编译失败

```
1. 运行 compile-check 排除本地语法问题
2. 查看命令输出中的 JoinQuant compile error / Traceback
3. IF 页面按钮/文案变化 → 检查 browser.py 和 snippets/compile.js
```

### 数据抓取不完整

```
IF 不存在 api_export.json AND 存在 dom_tabs_persisted.json
  → 所有提取方式均失败，仅拿到 DOM fallback 数据
ELSE IF api_export.json.metadata.schema_version == 3
  → 研究环境抓取成功，数据完整度最高
  → 检查 metadata.json 的 primary_extraction_method 确认
ELSE IF api_export.json.metadata.primary_extraction_method 以 "joinquant_research" 开头
   BUT research_downloaded == false
  → 研究环境失败，走了 detail fallback
  → 检查 research_fetch_error 了解研究环境失败原因
ELSE
  → 使用了 detail 模式或旧版 API bundle
  → 检查 partial 字段了解哪些数据截断
```

### 研究环境抓取失败

```
IF $env:JQ_AUTO_FORCE_RESEARCH_FAILURE 已设置 → 取消该环境变量
IF result_source == "research" → 失败即终止，改用 auto 或 detail
IF 错误信息包含 "iframe was not found" → 研究页加载超时，重试或检查网络
IF 错误信息包含 "kernel" → Jupyter kernel 启动失败，聚宽研究环境可能维护中
IF 错误信息包含 "write_file" → 研究环境文件写入权限问题

诊断方法：
  检查 metadata.json 的 research_fetch_error 字段
  IF auto 模式 → 工具已自动回退 detail，产物仍然可用（平台日志不完整）
```

### params_diff 报错

```
IF "outside set_parameter" → 目标参数未在 set_parameter() 中定义
IF "multi-line assignment" → 目标赋值跨多行，改为单行
IF "not found" → 参数名拼写错误
```

### 额度不足

```
IF 可以读到聚宽页面实时数据 → 以页面显示为准
IF 页面读取失败 → 检查 docs/joinquant-data/quota_ledger/<YYYYMMDD>.json
→ 调小 estimated_minutes 前先确认实际回测耗时
→ 等待次日免费额度重置
```

---

## Environment Setup

```powershell
# Python 虚拟环境
.\.venv\Scripts\python.exe -m playwright install chromium

# 首次使用：非 headless 登录聚宽
.\.venv\Scripts\python.exe -m scripts.jq_automation upload <strategy_file> --strategy-name <name>
# → 在弹出的 Chrome 中手动登录聚宽，后续自动复用 .local/chrome-jq/ 的 cookies
```

`.local/` 已被 `.gitignore` 忽略。

## Verification

改动工具代码后：

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\jq-auto.py scripts\jq_automation\__init__.py scripts\jq_automation\__main__.py scripts\jq_automation\config.py scripts\jq_automation\local.py scripts\jq_automation\manifest.py scripts\jq_automation\artifacts.py scripts\jq_automation\quota.py scripts\jq_automation\paths.py scripts\jq_automation\browser.py scripts\jq_automation\cli.py scripts\jq_automation\abtest.py scripts\jq_automation\git_versioning.py scripts\jq_automation\metrics.py scripts\jq_automation\research.py
.\.venv\Scripts\python.exe -m pytest scripts\jq_automation\tests -q
.\.venv\Scripts\python.exe -m scripts.path_tools.refactor check
```

## Module Index

```text
scripts/jq_automation/
  __main__.py              # python -m scripts.jq_automation 入口
  cli.py                   # CLI 定义、命令编排、_fetch_backtest_data() 三阶段管线
  browser.py               # Playwright + 聚宽页面操作、fetch_detail_supplemental()
  research.py              # 研究环境 get_backtest() 抓取、schema v3 归一化、Jupyter kernel 脚本生成
  config.py                # scenario.json / YAML 解析、sweep 展开、result_source 校验
  local.py                 # py_compile、上传文件生成、params_diff 改写
  artifacts.py             # API/DOM/research 产物落盘入口
  manifest.py              # batch manifest 与 A/B manifest 更新
  quota.py                 # 每日云端用时账本
  abtest.py                # A/B 配置、expand、run、report
  git_versioning.py        # Git ref 冻结与源码物化
  metrics.py               # A/B 指标抽取与归一化
  snippets/*.js            # 注入聚宽页面的浏览器脚本
  scripts/
    strip_comments.py      # 上传前去注释
    save_backtest_data.py  # 回测数据转 Markdown/JSON（支持 v1/v2/v3 schema）
  tests/                   # 本地单元测试
```

## 临时产物

工具自动删除 `apply_params_overrides()` 产生的 `__sweep_tmp.py` 临时文件。以下产物被 `.gitignore` 忽略，确认不需要后可手动清理：

- `.local/chrome-jq/` — Chrome profile（复用登录态）
- `.local/jq-automation/` — A/B 物化源码
- `*__upload.py` — 去注释上传文件
