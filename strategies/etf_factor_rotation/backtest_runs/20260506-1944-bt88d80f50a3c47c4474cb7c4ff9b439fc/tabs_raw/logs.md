# 策略日志

- INFO：199  |  WARNING：56  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2026-02-02 09:30:00 - INFO  - history end_date=2026-01-30 00:00:00, context.previous_date=2026-01-30
2026-02-02 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=1, 510050.XSHG=1, 510300.XSHG=1, 159915.XSHE=1
2026-02-02 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.9167, 513100.XSHG=0.2500, 518880.XSHG=0.9167, 510050.XSHG=0.3333, 510300.XSHG=0.4167, 159915.XSHE=0.6667
2026-02-02 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1, 510050.XSHG=0, 510300.XSHG=0, 159915.XSHE=1
2026-02-02 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.3020, 513100.XSHG=0.0000, 518880.XSHG=0.3192, 510050.XSHG=0.0000, 510300.XSHG=0.0000, 159915.XSHE=0.3788
2026-02-02 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=0.2976, 513100.XSHG=0.2425, 518880.XSHG=1.0000, 510050.XSHG=0.9411, 510300.XSHG=1.0000, 159915.XSHE=0.2612
2026-02-02 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=0.9546, 513100.XSHG=1.0000, 518880.XSHG=0.3000, 510050.XSHG=1.0000, 510300.XSHG=1.0000, 159915.XSHE=1.0000
2026-02-02 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2026-02-02 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0858, 513100.XSHG=0.0000, 518880.XSHG=0.0958, 510050.XSHG=0.0000, 510300.XSHG=0.0000, 159915.XSHE=0.0990
2026-02-02 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 5100: Order(security=159819.XSHE mode=OrderTargetValue: _value=8578.28571055788 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-02-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067848 security=159819.XSHE mode=OrderTargetValue: _value=8578.28571055788 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 5100)
2026-02-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778067848 security=159819.XSHE mode=OrderTargetValue: _value=8578.28571055788 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 5100) trade price: 1.666, amount:5100, commission: 0.8496600000000001
2026-02-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067848 security=159819.XSHE mode=OrderTargetValue: _value=8578.28571055788 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=2026-02-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 5100)
2026-02-02 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.0858 current_weight=0.0000 target_value=8578.29
2026-02-02 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 900: Order(security=518880.XSHG mode=OrderTargetValue: _value=9576.461249861792 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-02-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067849 security=518880.XSHG mode=OrderTargetValue: _value=9576.461249861792 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 900)
2026-02-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778067849 security=518880.XSHG mode=OrderTargetValue: _value=9576.461249861792 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 900) trade price: 9.908, amount:900, commission: 0.89172
2026-02-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067849 security=518880.XSHG mode=OrderTargetValue: _value=9576.461249861792 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=2026-02-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 900)
2026-02-02 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.0958 current_weight=0.0000 target_value=9576.46
2026-02-02 09:30:00 - WARNING - Security(code=510050.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - WARNING - Security(code=510300.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - WARNING - Security(code=159915.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-02-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 2900: Order(security=159915.XSHE mode=OrderTargetValue: _value=9895.690850919815 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-02-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067850 security=159915.XSHE mode=OrderTargetValue: _value=9895.690850919815 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 2900)
2026-02-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778067850 security=159915.XSHE mode=OrderTargetValue: _value=9895.690850919815 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 2900) trade price: 3.338, amount:2900, commission: 0.9680200000000001
2026-02-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067850 security=159915.XSHE mode=OrderTargetValue: _value=9895.690850919815 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-02-02 09:30:00 cancel_time=None finish_time=2026-02-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 2900)
2026-02-02 09:30:00 - INFO  - order sent: 159915.XSHE target_weight=0.0990 current_weight=0.0000 target_value=9895.69

... （剩余 225 行未展开） ...

2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067866 security=159819.XSHE mode=OrderTargetValue: _value=13246.11774810467 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 3900)
2026-04-27 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.1348 current_weight=0.2047 target_value=13246.12
2026-04-27 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 9300: Order(security=513100.XSHG mode=OrderTargetValue: _value=18028.644495132055 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-04-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067867 security=513100.XSHG mode=OrderTargetValue: _value=18028.644495132055 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 9300)
2026-04-27 09:30:00 - INFO  - order StockOrder(entrust_id=1778067867 security=513100.XSHG mode=OrderTargetValue: _value=18028.644495132055 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 9300) trade price: 1.93, amount:9300, commission: 1.7949000000000002
2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067867 security=513100.XSHG mode=OrderTargetValue: _value=18028.644495132055 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 9300)
2026-04-27 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.1835 current_weight=0.0000 target_value=18028.64
2026-04-27 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - WARNING - Security(code=510050.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - WARNING - Security(code=510300.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778067868 security=159915.XSHE mode=OrderTargetValue: _value=13268.711167092997 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 2100)
2026-04-27 09:30:00 - INFO  - order StockOrder(entrust_id=1778067868 security=159915.XSHE mode=OrderTargetValue: _value=13268.711167092997 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 2100) trade price: 3.68, amount:2100, commission: 0.7728
2026-04-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778067868 security=159915.XSHE mode=OrderTargetValue: _value=13268.711167092997 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-04-27 09:30:00 cancel_time=None finish_time=2026-04-27 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 2100)
2026-04-27 09:30:00 - INFO  - order sent: 159915.XSHE target_weight=0.1350 current_weight=0.2172 target_value=13268.71
```
