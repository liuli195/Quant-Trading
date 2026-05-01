# CLAUDE.md

## 项目概述

基于 Python 的 A 股/场内基金量化交易项目。所有策略开发、回测、模拟交易均在**聚宽 (JoinQuant)** 云平台运行，本地无法执行策略。

- 聚宽 API 文档：
  - 线上文档：<https://www.joinquant.com/help/api/help#name:api>
  - 离线文档（Markdown）：docs/joinquant-api.md（由 HTML 转换，查阅 API 时优先读取此文件）
- 策略回测：<https://www.joinquant.com/algorithm/index/list>
- 模拟交易：<https://www.joinquant.com/algorithm/trade/list>
- 策略文件：`strategies/` 目录

## 开发工作流

**本地编写 → 浏览器自动化上传 → 聚宽云端回测**

本地可用 Python 做静态检查，但不能运行策略。通过 mcp-chrome 操控 Chrome 完成上传和回测操作（需先在 Chrome 中手动登录聚宽）。

聚宽策略遵循固定生命周期：

- `initialize(context)` — 初始化参数、股票池、定时任务
- `handle_data(context, data)` — 按日/分钟调用的主逻辑，或自定义 `run_daily` 等定时函数

## 编码规范

- 每行代码均需详细中文注释（模块、函数、变量用途）
- 先过滤再查询 — 批量筛选缩小候选范围后，再对少量标的逐项操作，避免在全量数据上执行昂贵查询
- 缓存查询结果 — 同一数据只获取一次，存入局部变量复用，避免循环中反复调用 API
- 批量操作优于逐行循环 — 优先使用向量化或批量接口，减少逐条遍历
