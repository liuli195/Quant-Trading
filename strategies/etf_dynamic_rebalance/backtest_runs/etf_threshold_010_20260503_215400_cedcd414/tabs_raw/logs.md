# 策略日志

- INFO: 97  |  WARNING: 3  |  ERROR: 0
- 触发调仓日: 2  |  跳过调仓日: 11

```
日志输出错误日志

2023-01-03 09:30:00 - INFO  - 年化波动率: G=0.0943, A=0.2600, N=0.2642

2023-01-03 09:30:00 - INFO  - 因子得分: s_G=0.784, s_A=-0.086, s_N=0.510

2023-01-03 09:30:00 - INFO  - 纯风险平价: G=0.581, A=0.211, N=0.208

2023-01-03 09:30:00 - INFO  - 因子调整后: G=0.617, A=0.177, N=0.206

2023-01-03 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0

2023-01-03 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0

2023-01-03 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0

2023-01-03 09:30:00 - INFO  - 当前权重: G=0.000, A=0.000, N=0.000

2023-01-03 09:30:00 - INFO  - 初始建仓：偏离度 1.0000，执行调仓

2023-01-03 09:30:00 - INFO  - 最终权重: G=0.600, A=0.185, N=0.215

2023-01-03 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 75300: Order(security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)

2023-01-03 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777816417 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 75300)

2023-01-03 09:30:00 - INFO  - order StockOrder(entrust_id=1777816417 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 75300) trade price: 3.983, amount:75300, commission: 29.991990000000005

2023-01-03 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777816417 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=2023-01-03 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 75300)


... (171 more lines) ...

2023-01-19 09:30:00 - INFO  - 因子得分: s_G=0.128, s_A=0.784, s_N=0.231

2023-01-19 09:30:00 - INFO  - 纯风险平价: G=0.558, A=0.215, N=0.227

2023-01-19 09:30:00 - INFO  - 因子调整后: G=0.533, A=0.244, N=0.223

2023-01-19 09:30:00 - INFO  - 当前权重: G=0.593, A=0.195, N=0.212

2023-01-19 09:30:00 - INFO  - 偏离度 0.1208 > 阈值 0.10，触发调仓

2023-01-19 09:30:00 - INFO  - 最终权重: G=0.533, A=0.244, N=0.223

2023-01-19 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777816420 security=518880.XSHG mode=OrderTargetValue: _value=274049.6137826231 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2023-01-19 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 7600)

2023-01-19 09:30:00 - INFO  - order StockOrder(entrust_id=1777816420 security=518880.XSHG mode=OrderTargetValue: _value=274049.6137826231 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2023-01-19 09:30:00 cancel_time=None finish_time=None comment= error=平仓数量必须是 100 的整数倍，调整为 7600) trade price: 4.051, amount:7600, commission: 3.0787600000000004
```
