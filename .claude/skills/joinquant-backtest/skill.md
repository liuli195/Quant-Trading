---
name: joinquant-backtest
description: |
  将策略代码上传到聚宽平台并运行回测。
  触发条件：用户要求运行回测、上传策略到聚宽、测试某个策略。
  支持用户指定策略文件路径、回测起止日期、初始资金。
---

# 聚宽策略回测

## 1. 读取策略

- 读取用户指定的策略文件（默认 `strategies/` 目录）
- 如用户指定性能分析，确认文件顶部已有 `enable_profile()`

## 2. 去除注释

- 运行 `python scripts/strip_comments.py <src_file> <dst_file>`
- 读取去注释后的代码到内存

## 3. 打开聚宽编辑页面

- `navigate_page` 到 `https://www.joinquant.com/algorithm/index/edit`
- 若跳转到登录页 → 提示用户手动登录 → 重新导航到编辑页

## 4. 粘贴代码

聚宽使用 Ace 编辑器，容器 id `ide-container`。用 `evaluate_script` 写入并同步隐藏 textarea：

```javascript
const editor = ace.edit("ide-container");
editor.setValue(code);
editor.clearSelection();
document.getElementById('code').value = code;
```

## 5. 编译检查

- 通过快照找到 `StaticText "编译运行"` 的 uid，`click` 点击
- 编译日期范围设为 **1 周**（快速验证代码正确性，约 3~5 秒）
- `wait_for` 等待结果，text 数组：`["策略收益", "ERROR", "错误", "Traceback"]`
- 编译失败 → 查看日志/错误标签页 → 修复本地文件 → 回到步骤 2

## 6. 正式回测

编译通过后，通过 JS 设置参数并运行：

### 6.1 设置参数

```javascript
document.getElementById('startTime').value = 'YYYY-MM-DD';
document.getElementById('endTime').value = 'YYYY-MM-DD';
document.getElementById('daily_backtest_capital_base_box').value = '500000';
// 对每个 input 派发 Event('change', {bubbles: true})，资金额外派发 Event('input', ...)
```

- 日期字段 readonly，直接改 `.value` 即可
- 资金默认 100000，用户未指定时设为 500000

### 6.2 运行

"运行回测"按钮为 `<A id="full-backtest-button">`，点击其子 DIV 最可靠：

```javascript
const btn = document.getElementById('full-backtest-button');
btn.children[0].click();
```

点击后页面跳转到 `/algorithm/backtest/detail?backtestId=...`，状态变为"回测完成"即完成。

## 7. 等待结果

`wait_for` text 数组：`["回测完成", "收益概述", "策略收益", "年化收益", "Alpha", "Sharpe"]`

完成后用 `evaluate_script` 从 `document.body.innerText` 正则提取指标（比解析快照更可靠）。

## 8. 策略分析

提取指标（在详情页"收益概述"面板）：策略收益/年化收益、基准/超额收益、Alpha、Beta、Sharpe、Sortino、最大回撤及区间、胜率、盈亏比、日胜率、信息比率、策略/基准波动率。

输出：指标表格 + 策略评价（风格、优势、劣势、场景）+ 优化建议 → `strategies/{文件名}_Analysis.md`

## 9. 性能分析（用户指定时执行）

- 在详情页点击"性能分析"标签
- `wait_for` text：`["函数名", "调用次数", "总耗时", "性能分析"]`
- 输出：函数耗时表（总耗时、占比、调用次数、瓶颈行）+ 优化方案（预期节省 + 难度）→ `strategies/{文件名}_performance.md`

## 注意事项

- `wait_for` 的 `text` 必须是**数组**
- 优先用 `evaluate_script` 操作 DOM，避免依赖快照 uid（页面重绘后 uid 失效）
- 快照过大时先 `evaluate_script` 提取关键数据，再用 Grep 小范围搜索
- 编译结果在编辑页，正式回测结果在详情页（URL 不同），指标提取时需区分
- Ace 编辑器全局对象为 `ace`，实例通过 `ace.edit("ide-container")` 获取
