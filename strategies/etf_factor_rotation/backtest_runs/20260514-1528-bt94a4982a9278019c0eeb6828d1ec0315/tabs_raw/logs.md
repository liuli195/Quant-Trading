# 策略日志

- INFO：896  |  WARNING：104  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2021-01-04 09:30:00 - INFO  - history end_date=2020-12-31 00:00:00, context.previous_date=2020-12-31
2021-01-04 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-04 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-04 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.7805, 黄金ETF(518880.XSHG)=1.2632
2021-01-04 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2021-01-04 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.4685
2021-01-04 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.3657, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 41800: Order(security=513100.XSHG mode=OrderTargetValue: _value=36571.25833492368 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-04 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778743680 security=513100.XSHG mode=OrderTargetValue: _value=36571.25833492368 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 41800)
2021-01-04 09:30:00 - INFO  - order StockOrder(entrust_id=1778743680 security=513100.XSHG mode=OrderTargetValue: _value=36571.25833492368 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 41800) trade price: 0.873, amount:41800, commission: 3.6491400000000005
2021-01-04 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778743680 security=513100.XSHG mode=OrderTargetValue: _value=36571.25833492368 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=2021-01-04 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 41800)
2021-01-04 09:30:00 - INFO  - order sent: 纳指ETF(513100.XSHG) security=513100.XSHG target_weight=0.3657 current_weight=0.0000 target_value=36571.26
2021-01-04 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-11 09:30:00 - INFO  - history end_date=2021-01-08 00:00:00, context.previous_date=2021-01-08
2021-01-11 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=1, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-11 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.4000, 纳指ETF(513100.XSHG)=0.8500, 黄金ETF(518880.XSHG)=0.0000
2021-01-11 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=1, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-11 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.5229, 纳指ETF(513100.XSHG)=0.4771, 黄金ETF(518880.XSHG)=0.0000
2021-01-11 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0564, 黄金ETF(518880.XSHG)=0.7659
2021-01-11 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2021-01-11 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.4694
2021-01-11 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.2455, 纳指ETF(513100.XSHG)=0.2366, 黄金ETF(518880.XSHG)=0.0000
2021-01-11 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-11 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 25000: Order(security=159819.XSHE mode=OrderTargetValue: _value=24494.500778625283 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-11 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778743681 security=159819.XSHE mode=OrderTargetValue: _value=24494.500778625283 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-11 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 25000)
2021-01-11 09:30:00 - INFO  - order StockOrder(entrust_id=1778743681 security=159819.XSHE mode=OrderTargetValue: _value=24494.500778625283 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-11 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 25000) trade price: 0.979, amount:25000, commission: 2.4475000000000002

... （剩余 976 行未展开） ...

2022-03-28 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=1
2022-03-28 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0871, 黄金ETF(518880.XSHG)=0.9129
2022-03-28 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.7910, 黄金ETF(518880.XSHG)=1.3000
2022-03-28 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.7452, 黄金ETF(518880.XSHG)=0.8762
2022-03-28 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.4330
2022-03-28 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0222, 黄金ETF(518880.XSHG)=0.4502
2022-03-28 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-03-28 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-03-28 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778743754 security=518880.XSHG mode=OrderTargetValue: _value=44897.88943075237 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2022-03-28 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 2000)
2022-03-28 09:30:00 - INFO  - order StockOrder(entrust_id=1778743754 security=518880.XSHG mode=OrderTargetValue: _value=44897.88943075237 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2022-03-28 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 2000) trade price: 3.906, amount:2000, commission: 0.7812
2022-03-28 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778743754 security=518880.XSHG mode=OrderTargetValue: _value=44897.88943075237 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2022-03-28 09:30:00 cancel_time=None finish_time=2022-03-28 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 2000)
2022-03-28 09:30:00 - INFO  - order sent: 黄金ETF(518880.XSHG) security=518880.XSHG target_weight=0.4502 current_weight=0.5287 target_value=44897.89
2022-04-06 09:30:00 - INFO  - history end_date=2022-04-01 00:00:00, context.previous_date=2022-04-01
2022-04-06 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=1
2022-04-06 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.6000, 黄金ETF(518880.XSHG)=0.9000
```

> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。
