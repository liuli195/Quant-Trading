# 策略日志

- INFO: 95  |  WARNING: 3  |  ERROR: 2
- 触发调仓日: 3  |  跳过调仓日: 6

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

2023-01-03 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777816135 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 75300)

2023-01-03 09:30:00 - INFO  - order StockOrder(entrust_id=1777816135 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 75300) trade price: 3.983, amount:75300, commission: 29.991990000000005

2023-01-03 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777816135 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=2023-01-03 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 75300)


... (175 more lines) ...

2023-01-12 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777816143 security=513100.XSHG mode=OrderTargetValue: _value=111189.83055391863 style=MarketOrderStyle: _limit_price=0.0 side=long action=close margin=False entrust_time=2023-01-12 09:30:00 cancel_time=None finish_time=2023-01-12 09:30:00 comment= error=平仓数量必须是 100 的整数倍，调整为 4300)

2023-01-12 09:30:00 - INFO  - 调仓 纳指100ETF(513100.XSHG): 目标市值 111190, 目标权重 21.9%

2023-01-13 09:30:00 - INFO  - 年化波动率: G=0.0961, A=0.2351, N=0.2391

2023-01-13 09:30:00 - INFO  - 因子得分: s_G=0.538, s_A=0.057, s_N=0.712

2023-01-13 09:30:00 - INFO  - 纯风险平价: G=0.552, A=0.226, N=0.222

2023-01-13 09:30:00 - INFO  - 因子调整后: G=0.563, A=0.201, N=0.236

2023-01-13 09:30:00 - INFO  - 当前权重: G=0.558, A=0.197, N=0.219

2023-01-13 09:30:00 - INFO  - 偏离度 0.0261 <= 阈值 0.05，跳过本次调仓
```
