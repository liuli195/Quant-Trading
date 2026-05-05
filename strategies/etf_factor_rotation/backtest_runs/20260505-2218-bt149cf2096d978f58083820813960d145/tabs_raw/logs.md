# 策略日志

- INFO：241  |  WARNING：71  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2025-11-03 09:30:00 - INFO  - history end_date=2025-10-31 00:00:00, context.previous_date=2025-10-31
2025-11-03 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=1
2025-11-03 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.8667, 513100.XSHG=0.6333, 518880.XSHG=0.5000
2025-11-03 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=0
2025-11-03 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.2579, 513100.XSHG=0.7421, 518880.XSHG=0.0000
2025-11-03 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=0.4311, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2025-11-03 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.9033, 513100.XSHG=0.4464, 518880.XSHG=0.6413
2025-11-03 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.6558
2025-11-03 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0659, 513100.XSHG=0.2172, 518880.XSHG=0.0000
2025-11-03 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-11-03 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-11-03 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 10900: Order(security=513100.XSHG mode=OrderTargetValue: _value=21723.5467829756 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2025-11-03 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777990711 security=513100.XSHG mode=OrderTargetValue: _value=21723.5467829756 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-11-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 10900)
2025-11-03 09:30:00 - INFO  - order StockOrder(entrust_id=1777990711 security=513100.XSHG mode=OrderTargetValue: _value=21723.5467829756 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-11-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 10900) trade price: 1.984, amount:10900, commission: 2.16256
2025-11-03 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777990711 security=513100.XSHG mode=OrderTargetValue: _value=21723.5467829756 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-11-03 09:30:00 cancel_time=None finish_time=2025-11-03 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 10900)
2025-11-03 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.2172 current_weight=0.0000 target_value=21723.55
2025-11-03 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-11-10 09:30:00 - INFO  - history end_date=2025-11-07 00:00:00, context.previous_date=2025-11-07
2025-11-10 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=1
2025-11-10 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.8667, 513100.XSHG=0.6333, 518880.XSHG=0.5000
2025-11-10 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=0
2025-11-10 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.2576, 513100.XSHG=0.7424, 518880.XSHG=0.0000
2025-11-10 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2025-11-10 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.8815, 513100.XSHG=0.8373, 518880.XSHG=0.8268
2025-11-10 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.3067
2025-11-10 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0696, 513100.XSHG=0.1907, 518880.XSHG=0.0000
2025-11-10 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-11-10 09:30:00 - INFO  - order StockOrder(entrust_id=1777990712 security=513100.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2025-11-10 09:30:00 cancel_time=None finish_time=None comment= error=) trade price: 1.946, amount:10900, commission: 2.12114
2025-11-10 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777990712 security=513100.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2025-11-10 09:30:00 cancel_time=None finish_time=2025-11-10 09:30:00 comment= error=)
2025-11-10 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.0000 current_weight=0.2130 target_value=0.00

... （剩余 282 行未展开） ...

2026-04-20 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-20 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-20 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - INFO  - history end_date=2026-04-24 00:00:00, context.previous_date=2026-04-24
2026-04-27 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=1
2026-04-27 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=1.0000, 513100.XSHG=0.5000, 518880.XSHG=0.5000
2026-04-27 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=0
2026-04-27 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.4218, 513100.XSHG=0.5782, 518880.XSHG=0.0000
2026-04-27 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=0.8878, 518880.XSHG=0.0000
2026-04-27 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.7845, 513100.XSHG=0.8775, 518880.XSHG=1.0000
2026-04-27 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.2353
2026-04-27 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0779, 513100.XSHG=0.1060, 518880.XSHG=0.0000
2026-04-27 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
```
