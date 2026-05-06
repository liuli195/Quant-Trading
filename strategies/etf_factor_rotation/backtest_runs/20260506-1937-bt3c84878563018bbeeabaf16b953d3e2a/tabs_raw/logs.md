# 策略日志

- INFO：165  |  WARNING：25  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2026-02-02 09:30:00 - INFO  - history end_date=2026-01-30 00:00:00, context.previous_date=2026-01-30
2026-02-02 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=1
2026-02-02 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.8333, 513100.XSHG=0.3333, 518880.XSHG=0.8333
2026-02-02 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-02-02 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.4861, 513100.XSHG=0.0000, 518880.XSHG=0.5139
2026-02-02 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=0.2269, 513100.XSHG=0.1482, 518880.XSHG=1.0000
2026-02-02 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.8166, 513100.XSHG=1.0000, 518880.XSHG=0.3000
2026-02-02 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2026-02-02 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0901, 513100.XSHG=0.0000, 518880.XSHG=0.1542
2026-02-02 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 5400: Order(security=159819.XSHE mode=OrderTargetValue: _value=9007.191461418253 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-02-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067462 security=159819.XSHE mode=OrderTargetValue: _value=9007.191461418253 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 5400)
2026-02-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778067462 security=159819.XSHE mode=OrderTargetValue: _value=9007.191461418253 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 5400) trade price: 1.666, amount:5400, commission: 0.89964
2026-02-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067462 security=159819.XSHE mode=OrderTargetValue: _value=9007.191461418253 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=2026-02-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 5400)
2026-02-02 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.0901 current_weight=0.0000 target_value=9007.19
2026-02-02 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 1500: Order(security=518880.XSHG mode=OrderTargetValue: _value=15416.146193764833 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-02-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067463 security=518880.XSHG mode=OrderTargetValue: _value=15416.146193764833 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 1500)
2026-02-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778067463 security=518880.XSHG mode=OrderTargetValue: _value=15416.146193764833 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 1500) trade price: 9.908, amount:1500, commission: 1.4862
2026-02-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067463 security=518880.XSHG mode=OrderTargetValue: _value=15416.146193764833 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=2026-02-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 1500)
2026-02-02 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.1542 current_weight=0.0000 target_value=15416.15
2026-02-09 09:30:00 - INFO  - history end_date=2026-02-06 00:00:00, context.previous_date=2026-02-06
2026-02-09 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-02-09 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.5000, 513100.XSHG=0.0000, 518880.XSHG=1.0000
2026-02-09 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-02-09 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.5632, 513100.XSHG=0.0000, 518880.XSHG=0.4368
2026-02-09 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=0.6054, 513100.XSHG=0.2984, 518880.XSHG=1.0000
2026-02-09 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.6806
2026-02-09 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.7483

... （剩余 160 行未展开） ...

2026-04-27 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=0.8084, 518880.XSHG=0.0000
2026-04-27 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.6690, 513100.XSHG=0.8402, 518880.XSHG=1.0000
2026-04-27 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.6550
2026-04-27 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.1848, 513100.XSHG=0.2572, 518880.XSHG=0.0000
2026-04-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067473 security=159819.XSHE mode=OrderTargetValue: _value=18428.381751664616 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 10200)
2026-04-27 09:30:00 - INFO  - order StockOrder(entrust_id=1778067473 security=159819.XSHE mode=OrderTargetValue: _value=18428.381751664616 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 10200) trade price: 1.749, amount:10200, commission: 1.7839800000000003
2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067473 security=159819.XSHE mode=OrderTargetValue: _value=18428.381751664616 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 10200)
2026-04-27 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.1848 current_weight=0.3649 target_value=18428.38
2026-04-27 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 13200: Order(security=513100.XSHG mode=OrderTargetValue: _value=25643.224391873075 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-04-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067474 security=513100.XSHG mode=OrderTargetValue: _value=25643.224391873075 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 13200)
2026-04-27 09:30:00 - INFO  - order StockOrder(entrust_id=1778067474 security=513100.XSHG mode=OrderTargetValue: _value=25643.224391873075 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 13200) trade price: 1.93, amount:13200, commission: 2.5476
2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067474 security=513100.XSHG mode=OrderTargetValue: _value=25643.224391873075 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 13200)
2026-04-27 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.2572 current_weight=0.0000 target_value=25643.22
2026-04-27 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
```
