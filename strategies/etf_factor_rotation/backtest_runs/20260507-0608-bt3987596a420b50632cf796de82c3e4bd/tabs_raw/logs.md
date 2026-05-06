# 策略日志

- INFO：887  |  WARNING：101  |  ERROR：12
- 触发调仓：0  |  跳过调仓：0

```text
2021-01-04 09:30:00 - INFO  - history end_date=2020-12-31 00:00:00, context.previous_date=2020-12-31
2021-01-04 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-04 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=0
2021-01-04 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.7805, 黄金ETF(518880.XSHG)=1.2632
2021-01-04 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2021-01-04 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.5857
2021-01-04 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.4571, 黄金ETF(518880.XSHG)=0.0000
2021-01-04 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 52300: Order(security=513100.XSHG mode=OrderTargetValue: _value=45714.07291865461 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-04 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778105303 security=513100.XSHG mode=OrderTargetValue: _value=45714.07291865461 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 52300)
2021-01-04 09:30:00 - INFO  - order StockOrder(entrust_id=1778105303 security=513100.XSHG mode=OrderTargetValue: _value=45714.07291865461 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 52300) trade price: 0.873, amount:52300, commission: 4.565790000000001
2021-01-04 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778105303 security=513100.XSHG mode=OrderTargetValue: _value=45714.07291865461 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=2021-01-04 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 52300)
2021-01-04 09:30:00 - INFO  - order sent: 纳指ETF(513100.XSHG) security=513100.XSHG target_weight=0.4571 current_weight=0.0000 target_value=45714.07
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
2021-01-11 09:30:00 - INFO  - order StockOrder(entrust_id=1778105304 security=513100.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2021-01-11 09:30:00 cancel_time=None finish_time=None comment= error=) trade price: 0.868, amount:52300, commission: 4.53964
2021-01-11 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778105304 security=513100.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2021-01-11 09:30:00 cancel_time=None finish_time=2021-01-11 09:30:00 comment= error=)
2021-01-11 09:30:00 - INFO  - order sent: 纳指ETF(513100.XSHG) security=513100.XSHG target_weight=0.0000 current_weight=0.4552 target_value=0.00

... （剩余 997 行未展开） ...

2022-04-25 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.5705
2022-04-25 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.6092
2022-04-25 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-04-25 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-05-05 09:30:00 - INFO  - history end_date=2022-04-29 00:00:00, context.previous_date=2022-04-29
2022-05-05 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=1
2022-05-05 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=1.0000
2022-05-05 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=0, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=1
2022-05-05 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=1.0000
2022-05-05 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.8652, 黄金ETF(518880.XSHG)=1.1604
2022-05-05 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2022-05-05 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.5191
2022-05-05 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.0000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.6023
2022-05-05 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2022-05-05 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
```

> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。
