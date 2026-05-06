# 策略日志

- INFO：858  |  WARNING：142  |  ERROR：0
- 触发调仓：0  |  跳过调仓：0

```text
2018-01-02 09:30:00 - INFO  - history end_date=2017-12-29 00:00:00, context.previous_date=2017-12-29
2018-01-02 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=0
2018-01-02 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=1.0000, 518880.XSHG=0.0000
2018-01-02 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=0
2018-01-02 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=1.0000, 518880.XSHG=0.0000
2018-01-02 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2018-01-02 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=1.0000
2018-01-02 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2018-01-02 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0000, 513100.XSHG=1.0000, 518880.XSHG=0.0000
2018-01-02 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2018-01-02 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2018-01-02 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 135100: Order(security=513100.XSHG mode=OrderTargetValue: _value=60000.0 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2018-01-02 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778066514 security=513100.XSHG mode=OrderTargetValue: _value=60000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2018-01-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 135100)
2018-01-02 09:30:00 - INFO  - order StockOrder(entrust_id=1778066514 security=513100.XSHG mode=OrderTargetValue: _value=60000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2018-01-02 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 135100) trade price: 0.444, amount:135100, commission: 5.99844
2018-01-02 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778066514 security=513100.XSHG mode=OrderTargetValue: _value=60000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2018-01-02 09:30:00 cancel_time=None finish_time=2018-01-02 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 135100)
2018-01-02 09:30:00 - INFO  - order sent: 513100.XSHG target_weight=0.6000 current_weight=0.0000 target_value=60000.00
2018-01-02 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2018-01-08 09:30:00 - INFO  - history end_date=2018-01-05 00:00:00, context.previous_date=2018-01-05
2018-01-08 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2018-01-08 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=1.0000, 518880.XSHG=0.5000
2018-01-08 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2018-01-08 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3393, 518880.XSHG=0.6607
2018-01-08 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.9071
2018-01-08 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.9892
2018-01-08 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2018-01-08 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3393, 518880.XSHG=0.5928
2018-01-08 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2018-01-08 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778066515 security=513100.XSHG mode=OrderTargetValue: _value=34296.3230339151 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2018-01-08 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 59200)
2018-01-08 09:30:00 - INFO  - order StockOrder(entrust_id=1778066515 security=513100.XSHG mode=OrderTargetValue: _value=34296.3230339151 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2018-01-08 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 59200) trade price: 0.452, amount:59200, commission: 2.6758400000000004
2018-01-08 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778066515 security=513100.XSHG mode=OrderTargetValue: _value=34296.3230339151 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2018-01-08 09:30:00 cancel_time=None finish_time=2018-01-08 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 59200)

... （剩余 976 行未展开） ...

2019-05-20 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778066561 security=518880.XSHG mode=OrderTargetValue: _value=50878.14030053958 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2019-05-20 09:30:00 cancel_time=None finish_time=2019-05-20 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 3800)
2019-05-20 09:30:00 - INFO  - order sent: 518880.XSHG target_weight=0.4911 current_weight=0.5973 target_value=50878.14
2019-05-27 09:30:00 - INFO  - history end_date=2019-05-24 00:00:00, context.previous_date=2019-05-24
2019-05-27 09:30:00 - INFO  - [趋势门槛] TrendGate: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2019-05-27 09:30:00 - INFO  - [动量分数] MomentumScore: 159819.XSHE=0.0000, 513100.XSHG=0.9000, 518880.XSHG=0.6000
2019-05-27 09:30:00 - INFO  - [TopK入选] Selected: 159819.XSHE=0, 513100.XSHG=1, 518880.XSHG=1
2019-05-27 09:30:00 - INFO  - [风险平价权重] RPWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3494, 518880.XSHG=0.6506
2019-05-27 09:30:00 - INFO  - [RSRS修正乘数] RSRSMultiplier: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.7692
2019-05-27 09:30:00 - INFO  - [拥挤度惩罚] CrowdPenalty: 159819.XSHE=1.0000, 513100.XSHG=1.0000, 518880.XSHG=0.8253
2019-05-27 09:30:00 - INFO  - [组合波动率缩放] PortfolioVolScale=1.0000
2019-05-27 09:30:00 - INFO  - [最终权重] FinalWeight: 159819.XSHE=0.0000, 513100.XSHG=0.3494, 518880.XSHG=0.4130
2019-05-27 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2019-05-27 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778066562 security=518880.XSHG mode=OrderTargetValue: _value=42481.12003506267 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2019-05-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 3100)
2019-05-27 09:30:00 - INFO  - order StockOrder(entrust_id=1778066562 security=518880.XSHG mode=OrderTargetValue: _value=42481.12003506267 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2019-05-27 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 3100) trade price: 2.858, amount:3100, commission: 0.8859800000000001
2019-05-27 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778066562 security=518880.XSHG mode=OrderTargetValue: _value=42481.12003506267 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2019-05-27 09:30:00 cancel_time=None finish_time=2019-05-27 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 3100)
```

> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。
