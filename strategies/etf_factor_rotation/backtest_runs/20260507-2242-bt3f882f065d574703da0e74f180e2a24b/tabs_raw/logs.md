# 策略日志

- INFO：59  |  WARNING：9  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2026-04-01 09:30:00 - INFO  - history end_date=2026-03-31 00:00:00, context.previous_date=2026-03-31
2026-04-01 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0.40, 纳指ETF(513100.XSHG)=0.00, 黄金ETF(518880.XSHG)=1.00
2026-04-01 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.6000, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.9000
2026-04-01 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=1, 纳指ETF(513100.XSHG)=0, 黄金ETF(518880.XSHG)=1
2026-04-01 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.6038, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.3962
2026-04-01 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=0.7753, 纳指ETF(513100.XSHG)=0.1965, 黄金ETF(518880.XSHG)=0.0383
2026-04-01 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2026-04-01 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2026-04-01 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.1864, 纳指ETF(513100.XSHG)=0.0000, 黄金ETF(518880.XSHG)=0.0152
2026-04-01 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-01 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 12600: Order(security=159819.XSHE mode=OrderTargetValue: _value=18636.73201615183 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-04-01 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778164953 security=159819.XSHE mode=OrderTargetValue: _value=18636.73201615183 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-01 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 12600)
2026-04-01 09:30:00 - INFO  - order StockOrder(entrust_id=1778164953 security=159819.XSHE mode=OrderTargetValue: _value=18636.73201615183 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-01 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 12600) trade price: 1.472, amount:12600, commission: 1.8547200000000001
2026-04-01 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778164953 security=159819.XSHE mode=OrderTargetValue: _value=18636.73201615183 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-04-01 09:30:00 cancel_time=None finish_time=2026-04-01 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 12600)
2026-04-01 09:30:00 - INFO  - order sent: 人工智能ETF易方达(159819.XSHE) security=159819.XSHE target_weight=0.1864 current_weight=0.0000 target_value=18636.73
2026-04-01 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-01 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-07 09:30:00 - INFO  - history end_date=2026-04-03 00:00:00, context.previous_date=2026-04-03
2026-04-07 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=0.49, 纳指ETF(513100.XSHG)=0.27, 黄金ETF(518880.XSHG)=1.00
2026-04-07 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=0.5000, 纳指ETF(513100.XSHG)=0.6333, 黄金ETF(518880.XSHG)=0.8667
2026-04-07 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=1, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=1
2026-04-07 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.3118, 纳指ETF(513100.XSHG)=0.4785, 黄金ETF(518880.XSHG)=0.2097
2026-04-07 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.0540, 纳指ETF(513100.XSHG)=0.1646, 黄金ETF(518880.XSHG)=0.0000
2026-04-07 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=1.0000, 黄金ETF(518880.XSHG)=1.0000
2026-04-07 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2026-04-07 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.1610, 纳指ETF(513100.XSHG)=0.0212, 黄金ETF(518880.XSHG)=0.0000
2026-04-07 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-07 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-13 09:30:00 - INFO  - history end_date=2026-04-10 00:00:00, context.previous_date=2026-04-10
2026-04-13 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=1.00, 纳指ETF(513100.XSHG)=0.69, 黄金ETF(518880.XSHG)=1.00

... （剩余 38 行未展开） ...

2026-04-20 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.2663, 纳指ETF(513100.XSHG)=1.1685, 黄金ETF(518880.XSHG)=0.0000
2026-04-20 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=0.8040, 纳指ETF(513100.XSHG)=0.9138, 黄金ETF(518880.XSHG)=1.0000
2026-04-20 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.3664
2026-04-20 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.1217, 纳指ETF(513100.XSHG)=0.1727, 黄金ETF(518880.XSHG)=0.0000
2026-04-20 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-04-27 09:30:00 - INFO  - history end_date=2026-04-24 00:00:00, context.previous_date=2026-04-24
2026-04-27 09:30:00 - INFO  - [趋势门槛] TrendGate: 人工智能ETF易方达(159819.XSHE)=1.00, 纳指ETF(513100.XSHG)=1.00, 黄金ETF(518880.XSHG)=1.00
2026-04-27 09:30:00 - INFO  - [动量分数] MomentumScore: 人工智能ETF易方达(159819.XSHE)=1.0000, 纳指ETF(513100.XSHG)=0.5000, 黄金ETF(518880.XSHG)=0.5000
2026-04-27 09:30:00 - INFO  - [TopK入选] Selected: 人工智能ETF易方达(159819.XSHE)=1, 纳指ETF(513100.XSHG)=1, 黄金ETF(518880.XSHG)=1
2026-04-27 09:30:00 - INFO  - [风险平价权重] RPWeight: 人工智能ETF易方达(159819.XSHE)=0.3229, 纳指ETF(513100.XSHG)=0.4427, 黄金ETF(518880.XSHG)=0.2344
2026-04-27 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 人工智能ETF易方达(159819.XSHE)=1.3000, 纳指ETF(513100.XSHG)=0.9376, 黄金ETF(518880.XSHG)=0.0000
2026-04-27 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 人工智能ETF易方达(159819.XSHE)=0.7845, 纳指ETF(513100.XSHG)=0.8775, 黄金ETF(518880.XSHG)=1.0000
2026-04-27 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.4170
2026-04-27 09:30:00 - INFO  - [最终权重] FinalWeight: 人工智能ETF易方达(159819.XSHE)=0.1373, 纳指ETF(513100.XSHG)=0.1519, 黄金ETF(518880.XSHG)=0.0000
2026-04-27 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
```
