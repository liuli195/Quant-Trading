# 浏览器侧契约与等待规则

本文档记录 JoinQuant 浏览器侧工作流中需要稳定遵守的页面 URL、DOM 约定、等待规则、内部数据 API 与提取路径。

## 页面与 URL

| 场景 | 目标 URL / 特征 | 用途 |
| --- | --- | --- |
| 策略列表页 | `https://www.joinquant.com/algorithm/index/list` | 搜索同名策略、决定复用或新建 |
| 策略编辑页 | URL 包含 `/algorithm/index/edit` | 写入代码、编译、设置回测参数 |
| 回测详情页 | URL 包含 `/algorithm/backtest/detail?backtestId=` | 等待正式回测完成并提取数据 |

## 关键选择器

| 场景 | 选择器 / API | 说明 |
| --- | --- | --- |
| Ace 编辑器 | `ace.edit("ide-container")` | 获取策略代码编辑器实例 |
| 隐藏代码框 | `#code` | 与 Ace 内容同步 |
| 编译取消按钮 | `.cancel-build` | 仅在编译进行中出现 |
| 编译错误标签 | `#daily-errors-tab` | 读取编译失败日志 |
| 开始日期 | `#startTime` | 回测开始日期输入 |
| 结束日期 | `#endTime` | 回测结束日期输入 |
| 初始资金 | `#daily_backtest_capital_base_box` | 回测资金输入 |
| 正式回测按钮 | `#full-backtest-button` | 启动正式回测 |
| 收益概述容器 | `#tab-summaryinfo` | 提取顶部指标面板 |
| 性能分析标签 | `#tab-profile` | 查看 profile 输出 |

## 回测结果标签

| 逻辑名称 | 标签 href | 容器 id |
| --- | --- | --- |
| `transactioninfo` | `#tab-transactioninfo` | `tab-transactioninfo` |
| `positioninfo` | `#tab-positioninfo` | `tab-positioninfo` |
| `logs` | `#tab-logs` | `tab-logs` |
| `profile` | `#tab-profile` | `tab-profile` |
| `algorithm_period_return` | `#tab-algorithm_period_return` | `tab-algorithm_period_return` |
| `benchmark_period_return` | `#tab-benchmark_period_return` | `tab-benchmark_period_return` |
| `alpha` | `#tab-alpha` | `tab-alpha` |
| `beta` | `#tab-beta` | `tab-beta` |
| `sharpe` | `#tab-sharpe` | `tab-sharpe` |
| `sortino` | `#tab-sortino` | `tab-sortino` |
| `information` | `#tab-information` | `tab-information` |
| `algo_volatility` | `#tab-algo_volatility` | `tab-algo_volatility` |
| `benchmark_volatility` | `#tab-benchmark_volatility` | `tab-benchmark_volatility` |
| `max_drawdown` | `#tab-max_drawdown` | `tab-max_drawdown` |

## 等待规则

### 正式回测完成

- 只能使用 `wait_for(["回测完成"])`
- `text` 必须是数组
- 建议超时 180 秒

### 编译完成

- 不能用页面静态标题判断编译结束
- 正确判定条件：
  1. `.cancel-build` 曾出现过
  2. 当前 `.cancel-build` 已消失
  3. 页面未出现 `ERROR` 或 `Traceback`

### 性能分析就绪

- `#tab-profile` 存在
- 文本命中 `Total time` 或 `总耗时`
- 表格 `tr` 数量大于 1

## 反模式

以下文本在页面加载后就常驻 DOM 中，不能作为等待目标：

- `策略收益`
- `Alpha`
- `Sharpe`
- `收益概述`
- `年化收益`

这些文本如果用于 `wait_for`，会导致立即假阳性返回。

## 事件派发规则

日期和资金字段修改后，需要显式派发事件：

- `change`
- 视字段情况补发 `input`

日期输入通常是 `readonly`，可以直接赋值 `.value` 后补发事件。

## 虚拟滚动限制

以下标签使用虚拟滚动，DOM `innerText` 只能抓到当前可见部分：

- `transactioninfo`
- `positioninfo`
- `logs`

`transactioninfo` 和 `positioninfo` 优先改用内部 API 全量提取；`logs` 仍可能只能得到部分内容。

传统的 DOM 提取方式（`getTabText`）有两种用途：

- API 成功时，用于补抽 `logs`、`profile` 和静态指标标签
- API 不可用时，作为交易、持仓等大表的降级方案，并按 [output-contract.md](output-contract.md) <!-- pathref: agents_joinquant_skill/reference/output-contract.md --> 标记数据完整度

## 内部数据 API

回测详情页通过以下 XHR 接口获取数据，可通过 `evaluate_script` 直接调用：

### API 端点

| 端点 | 用途 | 分页方式 |
|------|------|------|
| `POST /algorithm/backtest/transactionInfo?backtestId=<id>&ajax=1` | 全部交易详情 | `offset` + `dateOffset` |
| `POST /algorithm/backtest/positionInfo?backtestId=<id>&ajax=1` | 每日持仓与收益 | `offset` + `dateOffset` |
| `POST /algorithm/backtest/result?backtestId=<id>&offset=0&userRecordOffset=0&ajax=1` | 每日收益曲线 | `offset`（每页 804 天） |
| `POST /algorithm/backtest/stats?backtestId=<id>&ajax=1` | 风险指标汇总 | 无分页（单次返回全部） |
| `GET/POST /algorithm/backtest/risk?backtestId=<id>&ajax=1` | 10 个风险/收益标签页 | 无分页（单次返回全部） |
| `GET/POST /algorithm/backtest/log?backtestId=<id>&offset=<n>&ajax=1` | 日志 | `offset`，免费接口可能 `max=true` 截断 |
| `GET/POST /algorithm/backtest/profile?backtestId=<id>&ajax=1` | 性能分析文本 | 无分页 |

### 内部 backtestId

API 使用的 `backtestId` 与 URL 中的不同。页面将内部 ID 暴露为全局变量：

```javascript
window.backtestId  // 例: “1ac02f6037915805b14b1f4541ff85e5”
```

### 分页机制

`transactionInfo` 和 `positionInfo` 每页返回 200 条记录。分页参数：

- `offset`：整数，累计已获取的记录数
- `dateOffset`：上一页最后一条记录的日期（格式 `YYYY-MM-DD`）

链式调用直到响应中 `data.max === true`。

### 认证

同源 `fetch()` 自动携带登录 Cookie，无需额外 token。

### 首次页面加载与内部 ID 获取

进入回测详情页后，内部 `backtestId` 由页面 JS 在初始化时设置。确认页面完全加载（等待 `回测完成` 文本出现）后即可调用数据提取函数。

## 数据提取入口

以下函数定义在 [../snippets/extract.js](../snippets/extract.js) <!-- pathref: agents_joinquant_skill/snippets/extract.js -->。流程文档只引用路径名称，具体调用约定以本节为准。

### API bundle 主路径

适用场景：

- 当前页面是已有回测详情页。
- 用户明确要求抓取已有详情页数据。
- 新跑回测完成后，详情页已稳定加载且可访问只读 XHR 接口。

调用约定：

```javascript
window.__jqBacktestBundle = await fetchExistingBacktestBundle({
  strategy: "<strategy>",
  strategyName: "<页面策略名>",
  startDate: "<YYYY-MM-DD>",
  endDate: "<YYYY-MM-DD>",
  capital: 500000,
  frequency: "每天",
  pyVersion: "Python3"
});
JSON.stringify(window.__jqBacktestBundle);
```

也可以在已执行过 `fetchExistingBacktestBundle()` 后调用：

```javascript
dumpExistingBacktestBundle();
```

该路径只调用详情页自身使用的同源 JSON 接口，禁止点击或调用会消耗积分的页面“导出”入口。

### 新跑回测 API 路径

旧版新跑回测流程可继续使用 `fetchAllBacktestData()`。该函数必须把结果写入 `window.__fetchedData`，保证后续 dump 可用。

调用约定：

```javascript
window.__fetchedData = await fetchAllBacktestData();
dumpFetchedBacktestData();
```

该路径至少应返回交易详情、每日持仓与每日收益；缺少日志、profile 或静态指标标签时，可再走 DOM 补抽。

### DOM 降级路径

当内部 API 不可用、字段异常或页面结构变化导致 API bundle 失败时，使用：

```javascript
await collectBacktestTabTexts();
dumpCollectedBacktestTabs();
```

DOM 降级受虚拟滚动限制，`transactioninfo`、`positioninfo`、`logs` 可能只是当前可见部分，必须按 [output-contract.md](output-contract.md) <!-- pathref: agents_joinquant_skill/reference/output-contract.md --> 标记完整度。

### 收益概述与性能状态

- `extractSummaryMetrics()`：从 `#tab-summaryinfo` 提取收益概述面板。
- `isProfileReady()`：判断 `#tab-profile` 是否已出现可用 profile 文本或表格。

## API bundle 字段契约

`fetchExistingBacktestBundle()` 返回值至少包含：

- `metadata`：回测上下文、日期、资金、URL、提取方式与 `export_used=false`
- `stats`：收益概述与风险指标汇总
- `result`：收益曲线接口原始响应
- `result_rows`：规范化后的每日收益行
- `transactions.rows`：全部交易详情
- `positions.rows`：每日持仓与收益
- `logs.rows`：日志行，免费接口可能部分截断
- `error_logs.rows`：错误日志行，可为空
- `profile_text`：性能分析原始文本
- `source`：策略源码接口响应
- `risk_tabs`：从 `algorithm_period_return` 到 `max_drawdown` 的 10 个风险/收益标签页
- `counts`：各类记录数
- `partial`：按数据类别记录是否部分截断

落盘脚本会把该 bundle 原文保存为 `api_export.json`，并转换为 `tabs_raw/*.md`、`metadata.json`、`summary_metrics.json`、`all_data.json` 与 `report/backtest_report.md`。
