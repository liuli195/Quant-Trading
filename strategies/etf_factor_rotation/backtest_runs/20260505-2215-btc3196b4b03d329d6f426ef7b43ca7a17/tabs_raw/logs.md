# 策略日志

- INFO：855  |  WARNING：94  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2025-04-01 09:30:00 - INFO  - history end_date=2025-03-31 00:00:00, context.previous_date=2025-03-31
2025-04-01 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2025-04-01 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.7500, 513100.XSHG=0.0000, 518880.XSHG=0.7500
2025-04-01 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2025-04-01 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.2586, 513100.XSHG=0.0000, 518880.XSHG=0.7414
2025-04-01 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=0.0000, 518880.XSHG=1.0000
2025-04-01 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.5111
2025-04-01 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2025-04-01 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.2586, 513100.XSHG=0.0000, 518880.XSHG=0.3789
2025-04-01 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-04-01 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 26900: Order(security=159819.XSHE mode=OrderTargetValue: _value=25858.9198311977 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2025-04-01 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777990527 security=159819.XSHE mode=OrderTargetValue: _value=25858.9198311977 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-04-01 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 26900)
2025-04-01 09:30:00 - INFO  - order StockOrder(entrust_id=1777990527 security=159819.XSHE mode=OrderTargetValue: _value=25858.9198311977 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-04-01 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 26900) trade price: 0.959, amount:26900, commission: 2.57971
2025-04-01 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777990527 security=159819.XSHE mode=OrderTargetValue: _value=25858.9198311977 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-04-01 09:30:00 cancel_time=None finish_time=2025-04-01 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 26900)
2025-04-01 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.2586 current_weight=0.0000 target_value=25858.92
2025-04-01 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-04-01 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2025-04-01 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 5300: Order(security=518880.XSHG mode=OrderTargetValue: _value=37891.41444851416 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2025-04-01 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777990528 security=518880.XSHG mode=OrderTargetValue: _value=37891.41444851416 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-04-01 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 5300)
2025-04-01 09:30:00 - INFO  - order StockOrder(entrust_id=1777990528 security=518880.XSHG mode=OrderTargetValue: _value=37891.41444851416 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-04-01 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 5300) trade price: 7.065, amount:5300, commission: 3.74445
2025-04-01 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777990528 security=518880.XSHG mode=OrderTargetValue: _value=37891.41444851416 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2025-04-01 09:30:00 cancel_time=None finish_time=2025-04-01 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 5300)
2025-04-01 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.3789 current_weight=0.0000 target_value=37891.41
2025-04-07 09:30:00 - INFO  - history end_date=2025-04-03 00:00:00, context.previous_date=2025-04-03
2025-04-07 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=0, 518880.XSHG=1
2025-04-07 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=0.0000, 518880.XSHG=1.0000
2025-04-07 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=0, 518880.XSHG=1
2025-04-07 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.0000, 518880.XSHG=1.0000
2025-04-07 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=0.0000, 518880.XSHG=1.0000
2025-04-07 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.4642
2025-04-07 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000

... （剩余 925 行未展开） ...

2026-04-27 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=0.8878, 518880.XSHG=0.0000
2026-04-27 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.7845, 513100.XSHG=0.8775, 518880.XSHG=1.0000
2026-04-27 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.5648
2026-04-27 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.1869, 513100.XSHG=0.2544, 518880.XSHG=0.0000
2026-04-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777990607 security=159819.XSHE mode=OrderTargetValue: _value=22723.197090730577 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 12300)
2026-04-27 09:30:00 - INFO  - order StockOrder(entrust_id=1777990607 security=159819.XSHE mode=OrderTargetValue: _value=22723.197090730577 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 12300) trade price: 1.749, amount:12300, commission: 2.1512700000000002
2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777990607 security=159819.XSHE mode=OrderTargetValue: _value=22723.197090730577 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 12300)
2026-04-27 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.1869 current_weight=0.3640 target_value=22723.20
2026-04-27 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 16000: Order(security=513100.XSHG mode=OrderTargetValue: _value=30927.434734620132 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-04-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777990608 security=513100.XSHG mode=OrderTargetValue: _value=30927.434734620132 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 16000)
2026-04-27 09:30:00 - INFO  - order StockOrder(entrust_id=1777990608 security=513100.XSHG mode=OrderTargetValue: _value=30927.434734620132 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 16000) trade price: 1.93, amount:16000, commission: 3.088
2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777990608 security=513100.XSHG mode=OrderTargetValue: _value=30927.434734620132 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 16000)
2026-04-27 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.2544 current_weight=0.0000 target_value=30927.43
2026-04-27 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
```
