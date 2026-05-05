# 策略日志

- INFO：406  |  WARNING：30  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2024-01-02 09:30:00 - INFO  - history end_date=2023-12-29 00:00:00, context.previous_date=2023-12-29
2024-01-02 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2024-01-02 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=1.0000, 518880.XSHG=0.5000
2024-01-02 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2024-01-02 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3749, 518880.XSHG=0.6251
2024-01-02 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.7930
2024-01-02 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=0.9226, 518880.XSHG=0.9954
2024-01-02 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2024-01-02 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3459, 518880.XSHG=0.4934
2024-01-02 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2024-01-02 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2024-01-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 28500: Order(security=513100.XSHG mode=OrderTargetValue: _value=34591.01126401752 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2024-01-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777983784 security=513100.XSHG mode=OrderTargetValue: _value=34591.01126401752 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2024-01-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 28500)
2024-01-02 09:30:00 - INFO  - order StockOrder(entrust_id=1777983784 security=513100.XSHG mode=OrderTargetValue: _value=34591.01126401752 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2024-01-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 28500) trade price: 1.21, amount:28500, commission: 3.4485
2024-01-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777983784 security=513100.XSHG mode=OrderTargetValue: _value=34591.01126401752 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2024-01-02 09:30:00 cancel_time=None finish_time=2024-01-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 28500)
2024-01-02 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.3459 current_weight=0.0000 target_value=34591.01
2024-01-02 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2024-01-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 10600: Order(security=518880.XSHG mode=OrderTargetValue: _value=49336.86921058822 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2024-01-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777983785 security=518880.XSHG mode=OrderTargetValue: _value=49336.86921058822 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2024-01-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 10600)
2024-01-02 09:30:00 - INFO  - order StockOrder(entrust_id=1777983785 security=518880.XSHG mode=OrderTargetValue: _value=49336.86921058822 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2024-01-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 10600) trade price: 4.643, amount:10600, commission: 4.92158
2024-01-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777983785 security=518880.XSHG mode=OrderTargetValue: _value=49336.86921058822 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2024-01-02 09:30:00 cancel_time=None finish_time=2024-01-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 10600)
2024-01-02 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.4934 current_weight=0.0000 target_value=49336.87
2024-01-08 09:30:00 - INFO  - history end_date=2024-01-05 00:00:00, context.previous_date=2024-01-05
2024-01-08 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2024-01-08 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=0.8500, 518880.XSHG=0.6500
2024-01-08 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2024-01-08 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3577, 518880.XSHG=0.6423
2024-01-08 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2024-01-08 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2024-01-08 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000

... （剩余 406 行未展开） ...

2024-06-17 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.4395 current_weight=0.3475 target_value=46944.24
2024-06-24 09:30:00 - INFO  - history end_date=2024-06-21 00:00:00, context.previous_date=2024-06-21
2024-06-24 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=1, 513100.XSHG=1, 518880.XSHG=1
2024-06-24 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.4000, 513100.XSHG=1.0000, 518880.XSHG=0.6000
2024-06-24 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2024-06-24 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.5374, 518880.XSHG=0.4626
2024-06-24 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2024-06-24 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=0.8730, 518880.XSHG=0.7888
2024-06-24 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2024-06-24 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0000, 513100.XSHG=0.4692, 518880.XSHG=0.3649
2024-06-24 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2024-06-24 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777983825 security=518880.XSHG mode=OrderTargetValue: _value=39023.71198259815 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2024-06-24 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 1400)
2024-06-24 09:30:00 - INFO  - order StockOrder(entrust_id=1777983825 security=518880.XSHG mode=OrderTargetValue: _value=39023.71198259815 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2024-06-24 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 1400) trade price: 5.3, amount:1400, commission: 0.742
2024-06-24 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777983825 security=518880.XSHG mode=OrderTargetValue: _value=39023.71198259815 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2024-06-24 09:30:00 cancel_time=None finish_time=2024-06-24 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 1400)
2024-06-24 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.3649 current_weight=0.4361 target_value=39023.71
```
