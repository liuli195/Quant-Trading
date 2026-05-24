# 飞书交易通知工具使用说明

本工具用于聚宽模拟交易通知。仓库模板只保留占位配置，真实 webhook 和 secret 只能写入聚宽私有上传版或本地未跟踪文件。

## 文件

- 模板：[FeishuRelayTools.py](../../scripts/joinquant_tools/FeishuRelayTools.py) <!-- pathref: scripts/joinquant_tools/FeishuRelayTools.py -->
- 方案：[2026-05-20-feishu-relay-tools-design.md](../superpowers/specs/2026-05-20-feishu-relay-tools-design.md) <!-- pathref: docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md -->

## 私有上传版

1. 复制上方模板为本地未跟踪私有副本：`FeishuRelayTools.private.py` 或 `FeishuRelayTools.local.py`。
2. 只在本地私有副本里填入 `WEBHOOK_URL` 和 `WEBHOOK_SECRET`，禁止把填了密钥的内容提交回仓库里的跟踪模板。
3. 按需设置 `SECURITY_KEYWORD`、`BUFFER_WAIT_TIME`、`SEND_JITTER_SECONDS`。
4. 上传到聚宽研究环境或策略文件目录时，建议保存为 `FeishuRelayTools.py`。
5. 在策略开头写 `import FeishuRelayTools`，确保导入发生在策略下单函数被调用前。

## 聚宽人工冒烟

1. 用最小策略触发一笔 `order_target_value`。
2. 查看日志中包装数量是否大于 0。
3. 确认飞书收到一条合并消息，标题包含策略名。
4. 确认 outbox 写入了 `pending` 和 `acked`。
5. 临时填入错误 webhook，再触发一笔订单，确认只留下 `pending` 且策略不报错。
6. 恢复 webhook 后重新启动工具，确认补发消息标题包含 `[补发]` 和 `batch_id`。

## 安全边界

- 不提交真实 webhook。
- 不提交真实 secret。
- 不在日志打印完整 webhook 或 secret。
- 本地私有副本文件名必须使用 `.gitignore` 已覆盖的 `FeishuRelayTools.private.py` 或 `FeishuRelayTools.local.py`。
