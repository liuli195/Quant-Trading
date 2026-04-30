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
- Read 读取用户指定的策略文件

### 2. 打开策略编辑页
- `chrome_get_windows_and_tabs` 查看标签页，复用已有编辑页或导航到编辑器

### 3. 上传代码
- **同时写入两个位置**：`textarea#code`（表单提交字段）和 `ace.edit("ide-container")`（Ace 编辑器）
- 写入后触发 `change` 事件触发自动保存，确认 `#save-done-text` 为「已保存」
- 切勿用 `ace.edit("code-area-internal")` — 那只是父容器 DIV
- 若需性能分析，代码**绝对第一行**加 `enable_profile()`

### 4. 编译运行（检查错误）
- 日期设为**单日**（起止同一天），加速编译
- 点击「编译运行」，等待完成（单日超过 2 分钟可取消）
- 读取日志和错误输出，有 ERROR 则修复后回到步骤 3

### 5. 设置回测参数
- `chrome_read_page` 获取最新 ref
- 设置起始/结束日期为用户指定范围，必要时调整初始资金

### 6. 运行完整回测
- 点击「运行回测」，等待自动跳转到回测详情页

### 7. 提取结果
- `chrome_javascript` 提取核心指标：策略收益/年化收益、基准收益、Alpha、Beta、Sharpe、Sortino、最大回撤及区间、胜率、盈亏比、超额收益、信息比率
- 表格呈现 + 简要分析

### 8. 性能分析（用户指定时执行）
- 点击「性能分析」标签（`profile-tab`），提取并分析瓶颈
- 详见 [performance-analysis](../performance-analysis/SKILL.md)

## 注意事项
- ref 随页面更新失效，操作前重新 `chrome_read_page`
- `enable_profile()` 须在文件第一行，注释也不能在前面
- 结束日期默认为「昨天」
