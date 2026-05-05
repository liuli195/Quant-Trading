# 策略日志

- INFO：65  |  WARNING：11  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2026-03-02 09:30:00 - INFO  - history end_date=2026-02-27 00:00:00, context.previous_date=2026-02-27
2026-03-02 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-03-02 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.5000, 513100.XSHG=0.0000, 518880.XSHG=1.0000
2026-03-02 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-03-02 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.5701, 513100.XSHG=0.0000, 518880.XSHG=0.4299
2026-03-02 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.0000
2026-03-02 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.5645
2026-03-02 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=0.7361
2026-03-02 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.4196, 513100.XSHG=0.0000, 518880.XSHG=0.0000
2026-03-02 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-03-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 26400: Order(security=159819.XSHE mode=OrderTargetValue: _value=41964.38441849829 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2026-03-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778008525 security=159819.XSHE mode=OrderTargetValue: _value=41964.38441849829 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-03-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 26400)
2026-03-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778008525 security=159819.XSHE mode=OrderTargetValue: _value=41964.38441849829 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-03-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 26400) trade price: 1.584, amount:26400, commission: 4.18176
2026-03-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778008525 security=159819.XSHE mode=OrderTargetValue: _value=41964.38441849829 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2026-03-02 09:30:00 cancel_time=None finish_time=2026-03-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 26400)
2026-03-02 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.4196 current_weight=0.0000 target_value=41964.38
2026-03-02 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-03-02 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-03-09 09:30:00 - INFO  - history end_date=2026-03-06 00:00:00, context.previous_date=2026-03-06
2026-03-09 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-03-09 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.6000, 513100.XSHG=0.0000, 518880.XSHG=0.9000
2026-03-09 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=1, 513100.XSHG=0, 518880.XSHG=1
2026-03-09 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.5742, 513100.XSHG=0.0000, 518880.XSHG=0.4258
2026-03-09 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=0.6109, 513100.XSHG=0.0489, 518880.XSHG=0.0000
2026-03-09 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.9178
2026-03-09 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2026-03-09 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.3508, 513100.XSHG=0.0000, 518880.XSHG=0.0000
2026-03-09 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778008526 security=159819.XSHE mode=OrderTargetValue: _value=34516.89012893761 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-03-09 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 3700)
2026-03-09 09:30:00 - INFO  - order StockOrder(entrust_id=1778008526 security=159819.XSHE mode=OrderTargetValue: _value=34516.89012893761 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-03-09 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 3700) trade price: 1.523, amount:3700, commission: 0.56351
2026-03-09 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778008526 security=159819.XSHE mode=OrderTargetValue: _value=34516.89012893761 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-03-09 09:30:00 cancel_time=None finish_time=2026-03-09 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 3700)
2026-03-09 09:30:00 - INFO  - order sent: 159819.XSHE target_weight=0.3508 current_weight=0.4087 target_value=34516.89

... （剩余 46 行未展开） ...

2026-03-23 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-03-30 09:30:00 - INFO  - history end_date=2026-03-27 00:00:00, context.previous_date=2026-03-27
2026-03-30 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=0, 518880.XSHG=0
2026-03-30 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=0.0000, 518880.XSHG=0.0000
2026-03-30 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=0, 518880.XSHG=0
2026-03-30 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.0000, 518880.XSHG=0.0000
2026-03-30 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=0.0631, 513100.XSHG=0.0000, 518880.XSHG=0.0000
2026-03-30 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2026-03-30 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2026-03-30 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0000, 513100.XSHG=0.0000, 518880.XSHG=0.0000
2026-03-30 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-03-30 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2026-03-30 09:30:00 - INFO  - order StockOrder(entrust_id=1778008529 security=518880.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-03-30 09:30:00 cancel_time=None finish_time=None comment= error=) trade price: 9.496, amount:2800, commission: 2.6588800000000004
2026-03-30 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778008529 security=518880.XSHG mode=OrderTargetValue: _value=0.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2026-03-30 09:30:00 cancel_time=None finish_time=2026-03-30 09:30:00 comment= error=)
2026-03-30 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.0000 current_weight=0.2797 target_value=0.00
```
