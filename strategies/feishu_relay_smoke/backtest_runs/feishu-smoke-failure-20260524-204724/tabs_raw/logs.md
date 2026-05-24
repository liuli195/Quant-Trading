# 策略日志

- INFO：16  |  WARNING：0  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2025-01-02 00:00:00 - INFO  - [FeishuRelayTools] 已包装 user_code.order
2025-01-02 00:00:00 - INFO  - [FeishuRelayTools] 已包装 user_code.order_value
2025-01-02 00:00:00 - INFO  - [FeishuRelayTools] 已包装 user_code.order_target
2025-01-02 00:00:00 - INFO  - [FeishuRelayTools] 已包装 user_code.order_target_value
2025-01-02 00:00:00 - INFO  - [FeishuRelayTools] 初始化完成，策略“飞书通知冒烟-20260524-204724”已包装 4 个下单函数。
2025-01-02 00:00:00 - INFO  - FEISHU_SMOKE_INIT mode=failure strategy=飞书通知冒烟-20260524-204724 outbox=feishu_relay_outbox/飞书通知冒烟-20260524-204724.jsonl wrapped=4
2025-01-02 09:35:00 - INFO  - 开仓数量必须是100的整数倍，调整为 2400: Order(security=510300.XSHG mode=OrderTargetValue: _value=10000.0 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2025-01-02 09:35:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1779627860 security=510300.XSHG mode=OrderTargetValue: _value=10000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-01-02 09:35:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 2400)
2025-01-02 09:35:00 - INFO  - order StockOrder(entrust_id=1779627860 security=510300.XSHG mode=OrderTargetValue: _value=10000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-01-02 09:35:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 2400) trade price: 4.015, amount:2400, commission: 5.0
2025-01-02 09:35:00 - INFO  - 订单已委托：StockOrder(entrust_id=1779627860 security=510300.XSHG mode=OrderTargetValue: _value=10000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-01-02 09:35:00 cancel_time=None finish_time=2025-01-02 09:35:00 comment= error=开仓数量必须是 100 的整数倍，调整为 2400)
2025-01-02 09:35:00 - INFO  - FEISHU_SMOKE_ORDER_RESULT OK security=510300.XSHG
2025-01-02 14:55:00 - INFO  - FEISHU_SMOKE_OUTBOX mode=failure events_pending=4 events_acked=4 unacked=0 sample=
2025-01-02 14:55:00 - INFO  - FEISHU_SMOKE_WRAPPED_COUNT 4
2025-01-03 14:55:00 - INFO  - FEISHU_SMOKE_OUTBOX mode=failure events_pending=4 events_acked=4 unacked=0 sample=
2025-01-03 14:55:00 - INFO  - FEISHU_SMOKE_WRAPPED_COUNT 4
2025-01-03 23:59:59.001000 - INFO  - [FeishuRelayTools] 飞书发送失败: http=200 code=19001 msg=param invalid: incoming webhook access token invalid
```
