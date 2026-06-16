# 飞书 Relay 工具

## Why
实现聚宽模拟交易到飞书通知的中继工具，打通策略信号→飞书通知链路。通知通道使用飞书自定义群机器人 webhook，工具采用 RelayTools.py 风格导入即自动包装聚宽下单函数。

## What Changes
- 飞书 webhook relay 实现，支持签名、关键词、错峰和频控响应处理
- 交易信号格式化与推送，按静默窗口合并订单
- Outbox 补偿机制：pending/acked 记录 + 启动补发
- atexit 退出兜底

## Impact
工具保持单文件上传形态，运行时只依赖 Python 标准库、requests 和聚宽内置函数。通知错误不得影响策略交易。仓库不保存真实 webhook 或飞书签名密钥。

---
source: docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md
