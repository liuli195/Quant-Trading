# DOM 约定与等待规则

本文档记录 JoinQuant 页面交互中需要稳定遵守的 DOM 约定、等待规则与反模式。

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
- API 不可用时，作为交易、持仓等大表的降级方案，并按 [output-contract.md](output-contract.md) <!-- pathref: joinquant_skill/reference/output-contract.md --> 标记数据完整度

## 内部数据 API

回测详情页通过以下 XHR 接口获取数据，可通过 `evaluate_script` 直接调用：

### API 端点

| 端点 | 用途 | 分页方式 |
|------|------|------|
| `POST /algorithm/backtest/transactionInfo?backtestId=<id>&ajax=1` | 全部交易详情 | `offset` + `dateOffset` |
| `POST /algorithm/backtest/positionInfo?backtestId=<id>&ajax=1` | 每日持仓与收益 | `offset` + `dateOffset` |
| `POST /algorithm/backtest/result?backtestId=<id>&offset=0&userRecordOffset=0&ajax=1` | 每日收益曲线 | `offset`（每页 804 天） |
| `POST /algorithm/backtest/stats?backtestId=<id>&ajax=1` | 风险指标汇总 | 无分页（单次返回全部） |

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

### 调用方式

使用 `evaluate_script` 执行 `fetchAllBacktestData()`（定义在 [../snippets/extract.js](../snippets/extract.js) <!-- pathref: joinquant_skill/snippets/extract.js -->），返回完整结构化 JSON。

### 首次页面加载与内部 ID 获取

进入回测详情页后，内部 `__backtestId` 由页面 JS 在初始化时设置。确认页面完全加载（等待 `回测完成` 文本出现）后即可调用。
