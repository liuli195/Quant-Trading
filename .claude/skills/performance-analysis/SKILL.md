---
name: performance-analysis
description: |
  读取聚宽回测的性能分析报告，呈现函数耗时、调用次数等数据并给出优化建议。
  触发条件：用户要求性能分析、分析策略瓶颈、优化策略性能。
---

# 聚宽性能分析

## 前置条件
- 策略代码**绝对第一行**必须是 `enable_profile()`（前面不能有注释、空行）
- 只在完整回测（「运行回测」）后有数据，「编译运行」不会生成

## 流程

### 1. 确认已在回测详情页
- URL 包含 `/algorithm/backtest/detail`

### 2. 点击「性能分析」标签
- 点击左侧 `profile-tab`
- 等待 1-2 秒渲染

### 3. 提取性能数据
- 用 `chrome_javascript` 搜索 `document.body.innerText` 中 `Timer unit:` 之后的内容
- 每段以 `Total time:` 开头，展示函数级性能数据

### 4. 分析呈现
- 按总耗时降序排列函数
- 用缩进展示函数内部的瓶颈行（含 `% Time` 占比）
- 给出 2-3 条针对性的优化建议
