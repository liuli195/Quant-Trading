# 输出目录与产物约定

## 目录结构

回测结果统一保存到：

```text
<strategy_dir>/backtest_runs/<run_id>/
├── metadata.json
├── summary_metrics.json
├── all_data.json
├── report/
│   ├── backtest_report.md
│   ├── strategy-analysis.md
│   └── performance-analysis.md
└── tabs_raw/
    ├── daily_returns.md
    ├── transactioninfo.md
    ├── positioninfo.md
    ├── algorithm_period_return.md
    ├── benchmark_period_return.md
    ├── alpha.md
    ├── beta.md
    ├── sharpe.md
    ├── sortino.md
    ├── information.md
    ├── algo_volatility.md
    ├── benchmark_volatility.md
    ├── max_drawdown.md
    ├── logs.md
    └── profile.md
```

目录语义由仓库根目录 `path_aliases.json` 管理：

- `backtest_run`：单次回测根目录。
- `backtest_report_dir`：`report/` 报告目录。
- `backtest_tabs_dir`：`tabs_raw/` 标签原始 Markdown 目录。

如果未来物理目录结构调整，优先修改目录别名配置；产物职责和文件名保持本约定。

## 文件职责

### `metadata.json`

用于记录本次回测的上下文与可追溯信息，建议至少包含：

```json
{
  "strategy_name": "",
  "strategy_file": "",
  "strategy_dir": "",
  "start_date_requested": "",
  "start_date_effective": "",
  "end_date_requested": "",
  "end_date_effective": "",
  "capital": 500000,
  "need_performance": false,
  "need_analysis": true,
  "extraction_method": "api",
  "backtest_id": "",
  "backtest_url": "",
  "generated_at": ""
}
```

### `summary_metrics.json`

保存从 `#tab-summaryinfo` 提取的收益概述面板。建议结构为：

```json
{
  "年化收益": "",
  "最大回撤": "",
  "夏普比率": "",
  "Alpha": "",
  "Beta": ""
}
```

键名以页面真实展示为准，不强制固定。

### `all_data.json`

用于记录本次抽取的索引信息，而不是重复保存整份原始文本。建议至少包含：

```json
{
  "persisted_json": "",
  "generated_at": "",
  "tabs": {
    "alpha": {
      "path": "tabs_raw/alpha.md",
      "partial": false,
      "raw_text_length": 0
    }
  }
}
```

## Markdown 产物约定

`tabs_raw/*.md` 全部使用中文标题和说明，转换规则如下：

- API 主路径至少生成 `transactioninfo.md`、`positioninfo.md`、`daily_returns.md`
- 指标表：转换为 Markdown 表格
- `transactioninfo.md`：输出月度汇总 + 逐笔明细
- `positioninfo.md`：按日期分组，每天一张表
- `logs.md`：输出摘要统计 + 首尾摘录
- `profile.md`：按函数拆分性能分析块

## 数据完整度说明

| 文件 | 完整度 | 说明 |
|------|:--:|------|
| `transactioninfo.md` | **100%** | 通过内部 API 获取全部交易记录 |
| `positioninfo.md` | **100%** | 通过内部 API 获取全部持仓日 |
| `daily_returns.md` | **100%** | 通过内部 API 获取每日收益曲线 |
| `logs.md` | 部分 | 仍受虚拟滚动限制 |
| 指标表格（alpha, beta 等） | **100%** | 静态 DOM，无虚拟滚动，按需补抽 |

API 方式获取时，`metadata.json` 中应标记：
```json
{
  "extraction_method": "api"
}
```

DOM 降级方式获取时，`all_data.json` 中标记：
```json
{
  "partial": true
}
```

## 报告文件

报告文件位于单次回测目录内：

- `backtest_runs/<run_id>/report/strategy-analysis.md`
- `backtest_runs/<run_id>/report/performance-analysis.md`
- `backtest_runs/<run_id>/report/backtest_report.md`

报告模板见：

- [../templates/analysis-report.md](../templates/analysis-report.md)
- [../templates/performance-report.md](../templates/performance-report.md)

## 完成校验

正常完成后，应至少看到：

- `report/` 下 3 个报告文件（`backtest_report.md`、`strategy-analysis.md`、`performance-analysis.md`）
- `metadata.json`、`summary_metrics.json`、`all_data.json`
- API 主路径：`tabs_raw/transactioninfo.md`、`tabs_raw/positioninfo.md`、`tabs_raw/daily_returns.md`
- DOM 降级或补充路径：执行过 `collectBacktestTabTexts()` 的标签应出现在 `tabs_raw/` 与 `all_data.json`

若 `need_performance=false` 且页面没有性能分析数据，允许 `profile.md` 为空内容，但文件仍建议保留。
