# 输出目录与产物约定

## 目录结构

回测结果根目录必须通过路径别名 `backtest_run(strategy=<strategy>, run_id=<run_id>)` 解析得到。当前物理结构为：

```text
strategies/<strategy>/backtest_runs/<run_id>/
├── api_export.json
├── metadata.json
├── summary_metrics.json
├── all_data.json
├── report/
│   └── backtest_report.md
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

目录语义由仓库根目录 `path_aliases.json` 管理，脚本和流程应优先使用 `scripts.path_tools.aliases` 解析：

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
  "extraction_method": "api",
  "backtest_id": "",
  "backtest_url": "",
  "generated_at": ""
}
```

### `api_export.json`

保存浏览器端数据提取原文。已有回测详情页优先由 API bundle 主路径生成；具体内部 API、提取函数和字段契约见 [browser-contracts.md](browser-contracts.md) <!-- pathref: agents_joinquant_skill/reference/browser-contracts.md -->。

禁止用会消耗积分的页面”导出”入口生成该文件。

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

### `report/backtest_report.md`

由 `save_backtest_data.py` 根据已落盘数据生成，职责是汇总本次回测的核心指标、数据覆盖和提取方式。

策略分析与性能分析报告不在本技能产物范围内，基于已下载的 `api_export.json` 单独运行生成，模板参见 [templates](../templates) <!-- pathref: agents_joinquant_skill/templates/ -->。

## Markdown 产物约定

`tabs_raw/*.md` 全部使用中文标题和说明，转换规则如下：

- 新版 API bundle 主路径必须生成 `transactioninfo.md`、`positioninfo.md`、`daily_returns.md`、10 个风险标签页、`logs.md`、`profile.md`
- 旧版 API 主路径至少生成 `transactioninfo.md`、`positioninfo.md`、`daily_returns.md`
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
| `logs.md` | 部分 | 免费只读接口或 DOM 降级都可能截断 |
| 指标表格（alpha, beta 等） | **100%** | 新版 API bundle 通过 `/algorithm/backtest/risk` 一次性获取 10 个标签页 |

API 方式获取时，`metadata.json` 中应标记：
```json
{
  "extraction_method": "api 或 joinquant_detail_readonly_api"
}
```

DOM 降级方式获取时，在 `all_data.json` 对应标签上标记：
```json
{
  "tabs": {
    "transactioninfo": {
      "partial": true
    }
  }
}
```

## 完成校验

正常完成后，应至少看到：

- `metadata.json`、`summary_metrics.json`、`all_data.json`
- `report/backtest_report.md`
- API 主路径：`tabs_raw/transactioninfo.md`、`tabs_raw/positioninfo.md`、`tabs_raw/daily_returns.md`
- DOM 降级或补充路径：执行过 `collectBacktestTabTexts()` 的标签应出现在 `tabs_raw/` 与 `all_data.json`

若页面没有性能分析数据，允许 `profile.md` 为空内容，但文件仍建议保留。策略分析与性能分析报告基于落盘数据单独运行。
