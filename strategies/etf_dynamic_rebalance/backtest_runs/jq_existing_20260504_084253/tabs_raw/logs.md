# 策略日志

- INFO：985  |  WARNING：3  |  ERROR：12
- 触发调仓：22  |  跳过调仓：92

```text
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
2023-01-03 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777855375 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 75300)
2023-01-03 09:30:00 - INFO  - order StockOrder(entrust_id=1777855375 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 75300) trade price: 3.983, amount:75300, commission: 29.991990000000005
2023-01-03 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777855375 security=518880.XSHG mode=OrderTargetValue: _value=300000.0 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=2023-01-03 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 75300)
2023-01-03 09:30:00 - INFO  - 调仓 黄金ETF(518880.XSHG): 目标市值 300000, 目标权重 60.0%
2023-01-03 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 136900: Order(security=159819.XSHE mode=OrderTargetValue: _value=92729.5358929097 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2023-01-03 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777855376 security=159819.XSHE mode=OrderTargetValue: _value=92729.5358929097 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 136900)
2023-01-03 09:30:00 - INFO  - order StockOrder(entrust_id=1777855376 security=159819.XSHE mode=OrderTargetValue: _value=92729.5358929097 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 136900) trade price: 0.677, amount:136900, commission: 9.268130000000001
2023-01-03 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777855376 security=159819.XSHE mode=OrderTargetValue: _value=92729.5358929097 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=2023-01-03 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 136900)
2023-01-03 09:30:00 - INFO  - 调仓 AI ETF(159819.XSHE): 目标市值 92730, 目标权重 18.5%
2023-01-03 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 134500: Order(security=513100.XSHG mode=OrderTargetValue: _value=107270.46410675209 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2023-01-03 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1777855377 security=513100.XSHG mode=OrderTargetValue: _value=107270.46410675209 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 134500)
2023-01-03 09:30:00 - INFO  - order StockOrder(entrust_id=1777855377 security=513100.XSHG mode=OrderTargetValue: _value=107270.46410675209 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 134500) trade price: 0.797, amount:134500, commission: 10.71965
2023-01-03 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1777855377 security=513100.XSHG mode=OrderTargetValue: _value=107270.46410675209 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2023-01-03 09:30:00 cancel_time=None finish_time=2023-01-03 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 134500)
2023-01-03 09:30:00 - INFO  - 调仓 纳指100ETF(513100.XSHG): 目标市值 107270, 目标权重 21.5%
2023-01-04 09:30:00 - INFO  - 年化波动率: G=0.0934, A=0.2459, N=0.2597
2023-01-04 09:30:00 - INFO  - 因子得分: s_G=0.721, s_A=0.078, s_N=0.587
2023-01-04 09:30:00 - INFO  - 纯风险平价: G=0.575, A=0.218, N=0.207
2023-01-04 09:30:00 - INFO  - 因子调整后: G=0.600, A=0.192, N=0.209
2023-01-04 09:30:00 - INFO  - 当前权重: G=0.597, A=0.189, N=0.214

... （剩余 1018 行未展开） ...

2023-06-20 09:30:00 - INFO  - 调仓 纳指100ETF(513100.XSHG): 目标市值 258238, 目标权重 40.5%
2023-06-21 09:30:00 - INFO  - 年化波动率: G=0.1093, A=0.3725, N=0.1590
2023-06-21 09:30:00 - INFO  - 因子得分: s_G=-0.464, s_A=0.834, s_N=0.540
2023-06-21 09:30:00 - INFO  - 纯风险平价: G=0.505, A=0.148, N=0.347
2023-06-21 09:30:00 - INFO  - 因子调整后: G=0.425, A=0.181, N=0.394
2023-06-21 09:30:00 - INFO  - 当前权重: G=0.353, A=0.185, N=0.406
2023-06-21 09:30:00 - INFO  - 偏离度 0.0871 <= 阈值 0.10，跳过本次调仓
2023-06-26 09:30:00 - INFO  - 年化波动率: G=0.1088, A=0.3756, N=0.1556
2023-06-26 09:30:00 - INFO  - 因子得分: s_G=-0.625, s_A=0.590, s_N=0.536
2023-06-26 09:30:00 - INFO  - 纯风险平价: G=0.503, A=0.146, N=0.352
2023-06-26 09:30:00 - INFO  - 因子调整后: G=0.413, A=0.173, N=0.413
2023-06-26 09:30:00 - INFO  - 当前权重: G=0.358, A=0.177, N=0.408
2023-06-26 09:30:00 - INFO  - 偏离度 0.0636 <= 阈值 0.10，跳过本次调仓
2023-06-27 09:30:00 - INFO  - 年化波动率: G=0.1084, A=0.3888, N=0.1572
2023-06-27 09:30:00 - INFO  - 因子得分: s_G=-0.653, s_A=-0.037, s_N=0.383
```

> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。
