---
name: joinquant-backtest
description: |
  将本地策略上传到聚宽（JoinQuant）并执行回测，产出策略分析与性能报告。
  触发条件：用户要求“回测 / 上传策略 / 聚宽测试 / backtest / performance”。
  支持参数：策略路径、回测起止日期、初始资金、是否执行性能分析。
---

# JoinQuant 回测技能规范

## 目标

- 在聚宽网页端完成完整流程：上传代码 -> 编译校验 -> 正式回测 -> 指标提取 -> 输出报告。
- 优先保证稳定性与可重复执行，其次追求速度。

## 输入参数

| 参数 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `strategy_file` | 是 | 无 | Python 策略文件路径；若用户仅给策略名，优先尝试 `strategies/<name>/<name>.py`。 |
| `start_date` | 否 | `2023-01-01` | 回测开始日期，格式 `YYYY-MM-DD`。 |
| `end_date` | 否 | 最近一个开盘日 | 回测结束日期，格式 `YYYY-MM-DD`。 |
| `capital` | 否 | `500000` | 初始资金；若用户未指定，使用 50 万。 |
| `need_performance` | 否 | `false` | 是否额外执行性能分析。 |

## 执行流程

### 1) 读取并预检查策略

- 读取 `strategy_file` 内容，确认文件存在且可读。
- 若 `need_performance=true`，确认策略中包含 `enable_profile()`；缺失则先补齐再继续。
- 校验参数：`start_date <= end_date`。若不满足，直接报错并要求用户确认，不自动交换日期。
- 记录：
  - `strategy_name`（文件名去 `.py`）
  - `strategy_dir`（策略所在目录）

### 2) 生成上传版本（去注释）

- 执行：
  - `python scripts/strip_comments.py <src_file> <dst_file>`
- 建议输出到：
  - `<strategy_dir>/<strategy_name>__upload.py`
- 读取去注释后的代码到内存，作为网页粘贴内容。

### 3) 检查回测列表策略并进入编辑页

- `navigate_page` 到：`https://www.joinquant.com/algorithm/index/list`
- 若跳到登录页：
  - 提示用户手动登录
  - 登录完成后再次导航到列表页
- 以 `strategy_name` 作为聚宽策略名（默认与本地文件名一致）。
- 在回测列表检索是否存在同名策略：
  - 若存在：进入该策略的编辑页（优先选最近更新的一条）。
  - 若不存在：点击“新建策略”，创建后立即将策略名设置为 `strategy_name`，再进入编辑页。
- 进入编辑页后，确认 URL 为 `/algorithm/index/edit` 再继续后续步骤。

### 4) 写入 Ace 编辑器代码

- 使用 `evaluate_script` 写入 Ace，并同步隐藏 `textarea#code`：

```javascript
const editor = ace.edit("ide-container");
editor.setValue(code);
editor.clearSelection();
document.getElementById("code").value = code;
```

### 5) 编译校验（快速冒烟）

- 点击 `编译运行`。
- 编译时间范围设置为 **1 周**（仅做语法和最小可运行性检查）。
- **等待完成（两阶段）**：
  - 阶段 A（启动确认，最多 10 秒）：轮询直到 `.cancel-build` 出现，确认编译确实开始。
  - 阶段 B（完成确认，最多 30 秒）：当“曾出现过 `.cancel-build`”且当前 `.cancel-build` 消失时判定编译完成；若出现 `ERROR/Traceback` 则判定失败。
  - 轮询脚本参考：
    ```javascript
    () => {
      const hasCancel = !!document.querySelector(".cancel-build");
      const bodyText = document.body?.innerText || "";
      const hasError = bodyText.includes("ERROR") || bodyText.includes("Traceback");
      return JSON.stringify({ hasCancel, hasError });
    }
    ```
- **注意**：不可用 `wait_for(["策略收益", ...])` — 该文本是页面静态标签，页面加载时就存在，会导致假阳性。
- 若失败：
  - 查看 `#daily-errors-tab` 的错误日志
  - 回写并修复本地策略
  - 从步骤 2 重新执行

### 6) 设置正式回测参数

- 用 `evaluate_script` 设置日期和资金，并触发事件：
- 日期规则（必须执行）：
  - 若用户未指定 `end_date`，默认取最近一个开盘日（交易日）。
  - 若用户给定日期是非交易日（周末/节假日），回退到该日期之前最近一个开盘日。
  - 交易日归一化优先级：`聚宽交易日历/API` > `页面日期组件可选值` > `按日向前回退（最多 15 天）`。
  - 设置完成后，回读 `#startTime/#endTime` 的最终值并记录到日志，作为实际生效日期。

```javascript
function setInputValue(id, value, needInputEvent = false) {
  const el = document.getElementById(id);
  if (!el) throw new Error(`Missing element: #${id}`);
  el.value = String(value);
  el.dispatchEvent(new Event("change", { bubbles: true }));
  if (needInputEvent) el.dispatchEvent(new Event("input", { bubbles: true }));
}

setInputValue("startTime", "YYYY-MM-DD");
setInputValue("endTime", "YYYY-MM-DD");
setInputValue("daily_backtest_capital_base_box", "500000", true);
```

- 日期输入通常是 `readonly`，直接改 `.value` 后派发事件即可。

### 7) 启动正式回测

- 点击运行按钮（优先点击子节点）：

```javascript
const btn = document.getElementById("full-backtest-button");
(btn?.children?.[0] || btn)?.click();
```

- 预期跳转到：
  - `/algorithm/backtest/detail?backtestId=...`

### 8) 等待回测完成

- 用 `wait_for(["回测完成"])` 等待（`text` 必须是数组）。
- **注意**：只匹配 `"回测完成"`，这是唯一只在回测完成后才出现的文本。不可混入 `"策略收益"`、`"Alpha"` 等——它们是页面静态标签，会导致假阳性误判。
- 超时阈值：180 秒。若超时，记录当前 URL + 状态文本，提示用户决策。

### 8.5) 全量提取回测数据（关键步骤）

回测完成后，**必须用 `evaluate_script` 逐标签提取全部数据**，不依赖快照（会截断）。

#### A. 收益概述（主指标面板）

```javascript
() => {
  const container = document.getElementById("tab-summaryinfo");
  if (!container) return JSON.stringify({ error: "missing #tab-summaryinfo" });
  const data = {};
  container.querySelectorAll(".top-level-stat").forEach(div => {
    const label = div.querySelector(".stat-label")?.innerText?.trim();
    const value = div.querySelector(".stat-value")?.innerText?.trim();
    if (label && value) data[label] = value;
  });
  return JSON.stringify(data);
}
```

至少包含：策略收益、策略年化收益、超额收益、基准收益、阿尔法、贝塔、夏普比率、胜率、盈亏比、最大回撤、索提诺比率、日均超额收益、超额收益最大回撤、超额收益夏普比率、日胜率、盈利次数、亏损次数、信息比率、策略波动率、基准波动率、最大回撤区间。

#### B. 交易详情（逐笔成交统计）

- 点击 `#tab-transactioninfo` 链接或对应的 a 标签。
- 用 `evaluate_script` 提取交易表头行（含总成交笔数、总佣金等汇总信息）作为摘要。
- 提取方式：
  ```javascript
  () => {
    const container = document.getElementById("tab-transactioninfo");
    if (!container) return JSON.stringify({ error: "missing #tab-transactioninfo" });
    const rows = Array.from(container.querySelectorAll("tr"))
      .map(r => r.innerText.replace(/\s+/g, " ").trim())
      .filter(Boolean);
    const buyCount = rows.filter(r => /(^|\s)买(\s|$)/.test(r)).length;
    const sellCount = rows.filter(r => /(^|\s)卖(\s|$)/.test(r)).length;
    return JSON.stringify({ totalTrades: buyCount + sellCount, buyCount, sellCount });
  }
  ```

#### C. 每日持仓&收益（持仓权重变化）

- 点击 `#tab-positioninfo`。
- 提取持仓汇总（持仓天数、平均仓位等）。

#### D. 日志输出（调仓日志与警告）

- 点击 `#tab-logs`。
- 提取关键信息：警告次数、错误次数、典型日志摘要（前 200 字符）。

#### E. 各指标图表标签（时间序列底层数据）

对以下每个标签，点击后提取底层数据表（图表下方通常有 HTML 表格）：

| 标签 ID | 指标 | 提取内容 |
| --- | --- | --- |
| `#tab-algorithm_period_return` | 策略收益 | 月度/滚动收益表 |
| `#tab-benchmark_period_return` | 基准收益 | 同上 |
| `#tab-alpha` | 阿尔法 | 滚动 Alpha 表 |
| `#tab-beta` | 贝塔 | 滚动 Beta 表 |
| `#tab-sharpe` | 夏普比率 | 滚动 Sharpe 表 |
| `#tab-sortino` | 索提诺比率 | 滚动 Sortino 表 |
| `#tab-information` | 信息比率 | 滚动 IR 表 |
| `#tab-algo_volatility` | 策略波动率 | 滚动波动率表 |
| `#tab-benchmark_volatility` | 基准波动率 | 同上 |
| `#tab-max_drawdown` | 最大回撤 | 月度回撤明细表（含 1/3/6/12 月滚动） |

- 提取时对每个标签：
  1. 点击标签链接
  2. 等待 1-2 秒（DOM 渲染）
  3. 用 `evaluate_script` 提取该标签容器内的 `innerText`（前 2000 字符用于报告，完整数据用于本地存档）
- 若标签 ID 失效（页面改版），按标签中文名做文本匹配点击（如“阿尔法”“贝塔”“最大回撤”）后再提取。
- 若某标签数据为空或无表格（纯图表），记录为 `"无底层数据表"` 跳过。

### 8.6) 回测数据完整保存到本地（必须执行，分两阶段）

- 每次回测都要生成独立归档目录，不覆盖历史结果：
  - `run_id = <strategy_name>_<YYYYMMDD_HHMMSS>_<backtestId>`
  - `backtestId` 从详情页 URL 参数读取；若未取到，使用 `noid`
  - 归档路径：`<strategy_dir>/backtest_runs/<run_id>/`
- 落盘阶段：
  - 阶段 1（步骤 8.5 后立即执行）：先保存非性能数据（指标、交易、持仓、日志、各标签原始数据）。
  - 阶段 2（步骤 9 后执行）：补写 `profile_raw.txt`，并最终生成/覆盖 `all_data.json` 汇总索引。
- 保存原则：
  - **完整保存**：8.5 中每个标签提取的数据都要落盘，不能只保留摘要。
  - **结构化优先**：能解析为 JSON/表格的，优先存 JSON；同时保留原始文本。
  - **UTF-8 编码**：所有文本文件统一 UTF-8。
- 最低落盘清单（全部必需）：
  - `metadata.json`：策略名、策略文件路径、聚宽策略名、`backtestId`、回测 URL、请求参数（`start_date/end_date/capital`）、实际生效日期、执行时间戳、`need_performance`、状态。
  - `summary_metrics.json`：8.5.A 主指标结构化结果。
  - `transaction_summary.json`：8.5.B 交易统计结果。
  - `position_summary.txt`：8.5.C 原始文本/摘要。
  - `logs_summary.txt`：8.5.D 原始文本/摘要。
  - `tabs_raw/<tab_id>.txt`：8.5.E 每个指标标签的完整 `innerText`（不截断）。
  - `tabs_parsed/<tab_id>.json`：可结构化解析的标签数据（若不可解析，写入 `{ \"status\": \"unparsed\" }`）。
  - `profile_raw.txt`：性能分析原始文本；若未执行性能分析，阶段 2 写入 `SKIPPED` 与原因。
  - `all_data.json`：汇总索引文件（引用上述各文件路径 + 关键字段快照）。
- 落盘完成后校验：
  - 目录存在且文件数 >= 8。
  - `metadata.json`、`summary_metrics.json`、`all_data.json` 必须存在。
  - 任一必需文件缺失则视为失败，重新保存一次；仍失败需明确报错并停止后续报告生成。

### 9) 可选：性能分析（仅 `need_performance=true` 或代码含 `enable_profile()`）

- 点击 `#tab-profile`。
- 用 `evaluate_script` 轮询性能区动态内容（最多 180 秒，间隔 3 秒）：
  - `#tab-profile` 存在且 `innerText` 命中 `Total time` 或 `总耗时`
  - 且表格行数 `tr` 大于 1（避免只命中静态标题）
- 用 `evaluate_script` 提取 `#tab-profile` 的完整文本。
- 解析提取：
  - 每个函数的：函数名、总耗时、占比、调用次数、主要瓶颈行号及代码
- 产出优化建议：
  - 预期收益（节省耗时）
  - 实施难度（低/中/高）

## 输出规范

- 策略分析报告：
  - `<strategy_dir>/Analysis_<strategy_name>.md`
  - 内容：指标表格 + 风格评估 + 优势/劣势 + 适用场景 + 优化建议

- 性能分析报告（可选）：
  - `<strategy_dir>/performance_<strategy_name>.md`
  - 内容：函数耗时表 + 瓶颈定位 + 优化方案

- 完整回测数据归档（必须）：
  - `<strategy_dir>/backtest_runs/<run_id>/`
  - 内容：全量原始数据 + 结构化数据 + 元数据索引（可复盘）

## 失败处理与重试策略

- 页面元素缺失：刷新页面并重试一次；仍失败则抓取页面文本并上报。
- 登录态失效：提示用户重新登录后，从步骤 3 继续。
- 回测超时（长时间无状态变化）：记录当前 URL、关键文本，再让用户决定继续等待或终止。
- 本地落盘失败：重试一次目录创建与文件写入；仍失败则中止并返回缺失文件清单。

## 注意事项

- `wait_for` 的 `text` 必须是数组，不要传字符串。
- **wait_for 反模式（重要）**：不可用页面静态标签作为等待目标。聚宽页面在加载时即渲染所有 tab 名称和区域标题（如 "策略收益"、"Alpha"、"Sharpe"、"收益概述"、"年化收益"）。这些文本始终存在于 DOM 中，会导致 `wait_for` 立即假阳性返回。**仅用只在回测完成后才出现的动态文本**，如 `"回测完成"`（状态区动态插入）。
- **编译等待反模式**：不可用 `["策略收益", ...]` 检测编译完成。编译页面中 "策略收益" 是静态图表标题。正确做法是轮询 `".cancel-build"` 按钮的消失（编译中才存在）。
- 尽量用 `evaluate_script` 直接操作 DOM，少依赖快照 uid（页面重绘后 uid 可能变化）。
- 编译结果在编辑页，正式回测结果在详情页，二者 URL 不同，勿混淆。
- **指标提取建议**：优先用 `evaluate_script` + `querySelectorAll('.top-level-stat')` 提取结构化指标，比正则匹配 `innerText` 更可靠。
- 若快照过大，先在页面内提取关键字段，再做小范围文本检索。
- Ace 编辑器实例固定通过 `ace.edit("ide-container")` 获取。
