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
| `start_date` | 否 | `2021-01-01` | 回测开始日期，格式 `YYYY-MM-DD`。 |
| `end_date` | 否 | 最近一个开盘日 | 回测结束日期，格式 `YYYY-MM-DD`。 |
| `capital` | 否 | `500000` | 初始资金；若用户未指定，使用 50 万。 |
| `need_performance` | 否 | `false` | 是否额外执行性能分析。 |

## 执行流程

### 1) 读取并预检查策略

- 读取 `strategy_file` 内容，确认文件存在且可读。
- 若 `need_performance=true`，确认策略中包含 `enable_profile()`；缺失则先补齐再继续。
- 记录：
  - `strategy_name`（文件名去 `.py`）
  - `strategy_dir`（策略所在目录）

### 2) 生成上传版本（去注释）

- 执行：
  - `python scripts/strip_comments.py <src_file> <dst_file>`
- 建议输出到：
  - `<strategy_dir>/<strategy_name>__upload.py`
- 读取去注释后的代码到内存，作为网页粘贴内容。

### 3) 打开聚宽编辑页并处理登录

- `navigate_page` 到：`https://www.joinquant.com/algorithm/index/edit`
- 若跳到登录页：
  - 提示用户手动登录
  - 登录完成后再次导航到编辑页

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
- 使用 `wait_for` 等待任一结果（`text` 必须是数组）：
  - `["策略收益", "ERROR", "错误", "Traceback"]`
- 若失败：
  - 查看错误日志
  - 回写并修复本地策略
  - 从步骤 2 重新执行

### 6) 设置正式回测参数

- 用 `evaluate_script` 设置日期和资金，并触发事件：
- 日期规则：
  - 若用户未指定 `end_date`，默认取最近一个开盘日（交易日）。
  - 若用户给定日期是非交易日（周末/节假日），回退到该日期之前最近一个开盘日。

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

### 8) 等待回测完成并提取指标

- `wait_for` 目标文本（数组）：
  - `["回测完成", "收益概述", "策略收益", "年化收益", "Alpha", "Sharpe"]`
- 完成后优先用 `evaluate_script` + `document.body.innerText` 正则提取指标（比全量快照稳定）。
- 至少提取：
  - 策略收益、年化收益、基准收益、超额收益
  - Alpha、Beta、Sharpe、Sortino
  - 最大回撤（含区间）
  - 胜率、盈亏比、日胜率、信息比率、策略波动率、基准波动率

### 9) 可选：性能分析（仅 `need_performance=true`）

- 点击详情页 `性能分析` 标签。
- `wait_for` 文本：
  - `["函数名", "调用次数", "总耗时", "性能分析"]`
- 提取：
  - 函数名、总耗时、占比、调用次数、主要瓶颈行
- 产出优化建议：
  - 预期收益（节省耗时）
  - 实施难度（低/中/高）

## 输出规范

- 策略分析报告：
  - `<strategy_dir>/<strategy_name>_Analysis.md`
  - 内容：指标表格 + 风格评估 + 优势/劣势 + 适用场景 + 优化建议

- 性能分析报告（可选）：
  - `<strategy_dir>/<strategy_name>_performance.md`
  - 内容：函数耗时表 + 瓶颈定位 + 优化方案

## 失败处理与重试策略

- 页面元素缺失：刷新页面并重试一次；仍失败则抓取页面文本并上报。
- 登录态失效：提示用户重新登录后，从步骤 3 继续。
- 回测超时（长时间无状态变化）：记录当前 URL、关键文本、截图，再让用户决定继续等待或终止。

## 注意事项

- `wait_for` 的 `text` 必须是数组，不要传字符串。
- 尽量用 `evaluate_script` 直接操作 DOM，少依赖快照 uid（页面重绘后 uid 可能变化）。
- 编译结果在编辑页，正式回测结果在详情页，二者 URL 不同，勿混淆。
- 若快照过大，先在页面内提取关键字段，再做小范围文本检索。
- Ace 编辑器实例固定通过 `ace.edit("ide-container")` 获取。
