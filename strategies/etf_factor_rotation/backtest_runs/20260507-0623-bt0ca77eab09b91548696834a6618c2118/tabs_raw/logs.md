# 策略日志

- INFO：890  |  WARNING：110  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2021-01-04 09:30:00 - INFO  - history end_date=2020-12-31 00:00:00, context.previous_date=2020-12-31
2021-01-04 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-04 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-04 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.7805, 黄金ETF(518880.XSHG)=1.2632
2021-01-04 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2021-01-04 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.3514
2021-01-04 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.2743, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 31400: Order(security=513100.XSHG mode=OrderTargetValue: _value=27428.44375119276 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-04 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778106214 security=513100.XSHG mode=OrderTargetValue: _value=27428.44375119276 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 31400)
2021-01-04 09:30:00 - INFO  - order StockOrder(entrust_id=1778106214 security=513100.XSHG mode=OrderTargetValue: _value=27428.44375119276 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 31400) trade price: 0.873, amount:31400, commission: 2.74122
2021-01-04 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778106214 security=513100.XSHG mode=OrderTargetValue: _value=27428.44375119276 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=2021-01-04 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 31400)
2021-01-04 09:30:00 - INFO  - order sent: 纳指ETF(513100.XSHG) security=513100.XSHG target_weight=0.2743 current_weight=0.0000 target_value=27428.44
2021-01-04 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-11 09:30:00 - INFO  - history end_date=2021-01-08 00:00:00, context.previous_date=2021-01-08
2021-01-11 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=0
2021-01-11 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-11 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=0
2021-01-11 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-11 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0564, 黄金ETF(518880.XSHG)=0.7659
2021-01-11 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2021-01-11 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2021-01-11 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-11 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-11 09:30:00 - INFO  - order StockOrder(entrust_id=1778106215 security=513100.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2021-01-11 09:30:00 cancel_time=None finish_time=None comment= error=) trade price: 0.868, amount:31400, commission: 2.7255200000000004
2021-01-11 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778106215 security=513100.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2021-01-11 09:30:00 cancel_time=None finish_time=2021-01-11 09:30:00 comment= error=)
2021-01-11 09:30:00 - INFO  - order sent: 纳指ETF(513100.XSHG) security=513100.XSHG target_weight=0.0000 current_weight=0.2730 target_value=0.00

... （剩余 970 行未展开） ...

2022-05-05 09:30:00 - INFO  - order StockOrder(entrust_id=1778106274 security=518880.XSHG mode=OrderTargetValue: _value=35861.65617205088 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2022-05-05 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 800) trade price: 3.926, amount:800, commission: 0.31408
2022-05-05 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778106274 security=518880.XSHG mode=OrderTargetValue: _value=35861.65617205088 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2022-05-05 09:30:00 cancel_time=None finish_time=2022-05-05 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 800)
2022-05-05 09:30:00 - INFO  - order sent: 黄金ETF(518880.XSHG) security=518880.XSHG target_weight=0.3614 current_weight=0.3956 target_value=35861.66
2022-05-09 09:30:00 - INFO  - history end_date=2022-05-06 00:00:00, context.previous_date=2022-05-06
2022-05-09 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=1
2022-05-09 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=1.0000
2022-05-09 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=1
2022-05-09 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=1.0000
2022-05-09 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.8256, 黄金ETF(518880.XSHG)=0.9485
2022-05-09 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2022-05-09 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.3929
2022-05-09 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.3727
2022-05-09 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-05-09 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-05-16 09:30:00 - INFO  - history end_date=2022-05-13 00:00:00, context.previous_date=2022-05-13
```

> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。
