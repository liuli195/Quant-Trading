---
name: joinquant-backtest
description: |
  将策略代码上传到聚宽平台并运行回测。
  触发条件：用户要求运行回测、上传策略到聚宽、测试某个策略。
  支持用户指定策略文件路径、回测起止日期、初始资金。
---

# 聚宽策略回测

## 1. 读取策略

- 读取用户指定的策略文件（默认 `strategies/` 目录下）
- 如用户指定性能分析，则插入 `enable_profile()` 相关代码

## 2. 去除注释

- 运行 `python scripts/strip_comments.py <src_file> <dst_file>`
- 将去除注释后的代码读取到内存，准备上传

## 3. 打开聚宽编辑页面

- 使用 `navigate_page` 打开 `https://www.joinquant.com/algorithm/index/edit`
- **注意**：若未登录，页面会自动重定向到登录页 `https://www.joinquant.com/user/login/index`
- 登录页出现时 → 提示用户在 Chrome 中手动登录，登录完成后继续
- 登录后重新 `navigate_page` 到编辑页

## 4. 粘贴代码到 Ace 编辑器

聚宽使用 **Ace 编辑器**（非 CodeMirror），容器 id 为 `ide-container`。

- 使用 `evaluate_script` 执行：

  ```javascript
  const editor = ace.edit("ide-container");
  editor.setValue(code);
  editor.clearSelection();
  document.getElementById('code').value = code;
  ```

- `code` 为去除注释后的策略代码字符串
- 同步更新隐藏 textarea `#code` 用于表单提交

## 5. 编译检查

- **点击 "编译运行"** 按钮（uid 中匹配 `StaticText "编译运行"`）

   ***注意*** 编译时间最多选择一周，编译主要用来测试代码正确性，不追求回测完整数据。

- 使用 `wait_for` 等待编译结果，`text` 参数为**数组**格式：

  ```
  ["因子得分", "策略收益", "ERROR", "错误", "Traceback"]
  ```

- 编译通过 → 继续第 6 步
- 编译失败 → 读取错误信息，修复本地文件 → 回到第 2 步循环

## 6. 正式回测

编译通过后，设置回测参数并运行：

- **回测日期**：通过日期选择器或直接修改只读输入框的值
  - 开始日期 textbox：readonly，value 如 "2025-10-01"
  - 结束日期 textbox：readonly，value 如 "2026-04-01"
- **初始资金**：修改资金 textbox（非 readonly），默认 100000
  - 用户未指定时默认 **50 万**
- **回测周期默认值**：用户未指定时默认近一周
- 点击 "**运行回测**" 按钮（`StaticText " 运行回测"`），等待回测完成

## 7. 等待回测结果

- 使用 `wait_for` 等待回测完成标志：

  ```
  ["策略收益", "年化收益", "Alpha", "Sharpe"]
  ```

- 回测完成后用 `take_snapshot` 获取完整结果页面

## 8. 提取指标并分析

核心指标：

- 策略收益 / 年化收益
- 基准收益
- Alpha、Beta
- Sharpe、Sortino
- 最大回撤及区间
- 胜率、盈亏比
- 超额收益、信息比率

结果以**表格**呈现 + 简要分析 + 优化建议。
分析结果更新入 `strategies/{策略文件名}_Analysis.md`

## 9. 性能分析（用户指定时执行）

- 提取性能分析报告
- 表格呈现 + 简要分析 + 优化建议
- 结果更新入 `strategies/{策略文件名}_performance.md`

## 注意事项

- `wait_for` 的 `text` 参数必须是**数组**格式，不能是字符串
- Ace 编辑器全局对象为 `ace`，通过 `ace.edit("ide-container")` 获取实例
- 登录状态可能过期，每次操作前检查页面 URL 是否被重定向到登录页
