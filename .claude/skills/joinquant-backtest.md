---
name: joinquant-backtest
description: |
  将策略代码上传到聚宽平台并运行回测。
  触发条件：用户要求运行回测、上传策略到聚宽、测试某个策略。
  支持用户指定策略文件路径、回测起止日期、初始资金。
---

# 聚宽策略回测

## 流程

### 1. 读取策略文件
- 用户可能指定策略文件路径，也可能只说策略名（需用 Glob 搜索）
- 用 Read 读取文件内容，确认代码完整

### 2. 打开策略编辑页面
- `chrome_get_windows_and_tabs` 查看当前标签页
- 如果已有聚宽策略编辑页打开，直接复用；否则 `chrome_navigate` 导航到编辑器

### 3. 上传代码
- `chrome_read_page` 读取页面元素，获取最新 ref
- `chrome_javascript` 检测编辑器类型（Ace / CodeMirror）
- `chrome_javascript` 通过编辑器 API 将策略代码写入编辑器（Ace 用 `ace.edit().setValue()`）

### 4. 编译运行（检查错误）
- `chrome_read_page` 获取最新 ref
- `chrome_click_element` 点击「编译运行」按钮
- 等待 5-8 秒让编译完成
- `chrome_javascript` 读取「日志」和「错误」标签页的输出
- **如果日志中有错误**：根据错误信息修改策略代码，回到步骤 3 重新上传
- **如果日志无错误**：继续下一步

### 5. 设置回测参数
- `chrome_read_page` 获取最新 ref（重要：ref 在页面更新后会失效）
- `chrome_fill_or_select` 设置起始日期（startTime）
- `chrome_fill_or_select` 设置结束日期（endTime）
- 如有需要可修改初始资金（daily_backtest_capital_base_box）

### 6. 运行完整回测
- `chrome_click_element` 点击「运行回测」按钮
- `chrome_computer` wait 15-30 秒等待回测完成
- 回测完成后页面会自动跳转到回测详情页

### 7. 提取结果
- `chrome_javascript` 从 `document.body.innerText` 提取关键指标
- 至少输出以下核心指标：
  - 策略收益 / 策略年化收益
  - 基准收益
  - Alpha、Beta
  - Sharpe、Sortino
  - 最大回撤及区间
  - 胜率、盈亏比
  - 超额收益、信息比率
- 以表格形式呈现结果，并给出简要分析

## 注意事项
- 每次页面更新后 ref 会失效，操作前务必重新 `chrome_read_page`
- 聚宽编辑器使用 Ace Editor，需要用 `ace.edit()` API 而非直接操作 DOM
- 「编译运行」只是语法/运行时快速检查，「运行回测」才是完整回测
- 日志中的 WARNING（如 Position 不存在）通常不影响回测，可忽略；ERROR 需要修复
- 结束日期通常设为「昨天」
