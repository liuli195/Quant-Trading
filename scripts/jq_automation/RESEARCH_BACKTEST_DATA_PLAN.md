# jq_automation 研究环境回测结果主数据源改造计划

## 背景

当前 `jq_automation` 在回测详情页注入 `snippets/extract.js`，通过聚宽详情页内部 XHR 接口抓取 `stats`、收益曲线、交易、持仓、风险指标、日志、源码、运行耗时和 profile。这个方案已经覆盖多数回测产物，但有两个结构性问题：

- 详情页接口是网页内部契约，分页参数、内部 `backtestId` 和字段结构可能随页面调整变化。
- `/algorithm/backtest/log` 实测存在服务端上限：每页 100 条，长回测到 `offset=1000` 后返回空数组并标记 `max=true`，因此平台日志只能保存部分。

聚宽官方研究环境提供 `get_backtest(backtest_id)`，可读取回测结果类数据：收益、持仓、订单、`record()`、风险、分期风险和每日市值。该接口不提供平台日志，也不替代回测运行期的行情、撮合和上下文数据。

## 目标

- 将“回测完成后的结果数据”主数据源迁移到研究环境 `get_backtest()`。
- 保持现有本地产物契约：`api_export.json`、`metadata.json`、`summary_metrics.json`、`all_data.json`、`tabs_raw/*.md` 和 `report/backtest_report.md`。
- 保留详情页接口作为补充源和 fallback，用于 `runtime/source/profile/平台日志 partial 状态`。
- 支持 `--result-source auto|research|detail`：
  - `auto`：优先研究环境，失败后回退详情页 API/DOM。
  - `research`：研究环境失败即失败。
  - `detail`：沿用旧详情页链路。

## 非目标

- 不改变策略运行期的数据获取方式。`get_price`、`history`、`get_current_data`、`context` 和订单撮合仍由聚宽回测引擎负责。
- 不试图从 `get_backtest()` 获取平台日志；完整业务日志另走策略侧 `write_file()` JSONL 方案。
- 不删除现有详情页 API 抓取代码，至少保留一个版本周期作为兜底。

## 当前实现对比

| 维度 | 详情页内部 API | 研究环境 `get_backtest()` |
| --- | --- | --- |
| 契约稳定性 | 私有网页接口，易随页面变化 | 官方研究环境 API |
| 收益曲线 | 支持，需分页 | 支持 `get_results()` |
| 持仓 | 支持，当前按 `dateOffset` 分段 | 支持 `get_positions()` |
| 交易/订单 | 支持，当前按 `offset/dateOffset` 分段 | 支持 `get_orders()` |
| record | 详情页 result 只覆盖部分图表字段 | 支持 `get_records()` |
| 风险指标 | 支持 `risk` 接口 | 支持 `get_risk()` / `get_period_risks()` |
| 每日账户市值 | 当前未作为主输出 | 支持 `get_balances()` |
| 平台日志 | 最多约 1000 条 | 不支持 |
| profile/source/runtime | 支持 | 不支持，继续由详情页补充 |

## 目标架构

```text
run/fetch/batch/ab run
  |
  |-- result_source=detail --> 现有 fetchExistingBacktestBundle() / DOM fallback
  |
  |-- result_source=auto|research
        |
        |-- 先在详情页读取 supplemental_detail
        |     runtime / source / profile_text / logs_partial
        |
        |-- 进入 JoinQuant Research
        |     通过 Jupyter API 启动 python3 kernel
        |     执行 get_backtest(backtest_id) 导出脚本
        |     write_file("jq_auto_exports/research_backtest_<id>.json", json)
        |
        |-- 读取研究文件内容
        |-- 规范化为 schema v3 bundle
        |-- 保存到现有 backtest_runs 目录
```

`auto` 模式下，研究环境任一步失败都会记录错误并回退到旧链路；`research` 模式直接失败，便于验收研究环境能力。

## 接口设计

### CLI

```powershell
.\.venv\Scripts\python.exe -m scripts.jq_automation fetch <backtestId> --strategy <strategy> --result-source auto
.\.venv\Scripts\python.exe -m scripts.jq_automation run <scenario.json> --yes --result-source research
.\.venv\Scripts\python.exe -m scripts.jq_automation batch <manifest.json> --yes --result-source detail
.\.venv\Scripts\python.exe -m scripts.jq_automation ab run <ab_config.json> --yes --result-source auto
```

### scenario.json

```json
{
  "result_source": "auto"
}
```

未配置时默认 `auto`。命令行参数优先级高于 `scenario.json`。

## Bundle Schema v3

```json
{
  "metadata": {
    "schema_version": 3,
    "extraction_method": "joinquant_research_get_backtest",
    "primary_extraction_method": "joinquant_research_get_backtest",
    "research_export_path": "jq_auto_exports/research_backtest_<id>.json",
    "research_downloaded": true,
    "detail_api_used": true
  },
  "results": [],
  "positions": [],
  "orders": [],
  "records": [],
  "risk": {},
  "period_risks": {},
  "balances": [],
  "supplemental_detail": {
    "runtime": {},
    "source": {},
    "profile_text": "",
    "logs_partial": true,
    "logs_count": 1000
  },
  "counts": {},
  "partial": {}
}
```

## 落盘兼容策略

- `api_export.json` 保存 schema v3 原始 bundle。
- `save_backtest_data.py` 根据 `metadata.schema_version == 3` 走研究环境转换器。
- 继续生成：
  - `tabs_raw/daily_returns.md`
  - `tabs_raw/transactioninfo.md`
  - `tabs_raw/positioninfo.md`
  - `tabs_raw/logs.md`
  - `tabs_raw/profile.md`
  - `report/backtest_report.md`
- 新增可用输出：
  - `tabs_raw/records.md`
  - `tabs_raw/balances.md`
  - `tabs_raw/risk.md`
  - `tabs_raw/period_risks.md`
- `metadata.json` 增加：
  - `primary_extraction_method`
  - `fallback_extraction_method`
  - `research_export_path`
  - `research_downloaded`
  - `detail_api_used`

## Rollout 顺序

1. 引入 `research.py`、schema v3 转换器和 `--result-source`，默认 `auto`，保留旧链路 fallback。
2. 对一个短回测执行 `fetch --result-source research`，确认研究环境能启动 kernel、写文件并读取。
3. 对长回测执行 `fetch --result-source auto`，确认主数据来自研究环境，详情页只补充 runtime/profile/logs_partial。
4. 在稳定后更新 README，把研究环境链路描述为主路径。
5. 后续另开任务实现策略侧完整业务日志 JSONL。

## 测试计划

- 单元测试：
  - 验证 `result_source` 配置解析。
  - 验证研究脚本生成包含 `get_backtest()` 与全部目标方法。
  - 验证 DataFrame、datetime、Decimal、NaN 的 JSON 序列化辅助函数。
  - 验证 schema v3 到 `tabs_raw/*.md`、`metadata.json`、`summary_metrics.json`、`all_data.json` 的转换。
  - 验证 `auto` fallback、`research` fail-fast、`detail` 保持旧行为。
- 本地检查：
  - `.\.venv\Scripts\python.exe -m py_compile scripts\jq-auto.py scripts\jq_automation\*.py`
  - `.\.venv\Scripts\python.exe -m pytest scripts\jq_automation\tests -q`
  - `python -m scripts.path_tools.refactor check`
- 云端验收：
  - 已完成短回测：`fetch --result-source research`。
  - 长回测：`fetch --result-source auto`。
  - 模拟研究环境不可用：确认自动回退详情页并在命令行输出失败原因。

## 风险与限制

- 聚宽研究页如果不暴露标准 Jupyter API，`research` 模式会失败；`auto` 会回退详情页。
- 研究环境 kernel 启动可能慢于详情页 XHR，需要较长等待窗口。
- `get_backtest()` 的字段名可能与详情页表格不同，转换层应保持宽松解析，不将字段名绑定得过死。
- 平台日志仍不可通过研究环境获取完整版本；完整业务日志需要策略主动写文件。
