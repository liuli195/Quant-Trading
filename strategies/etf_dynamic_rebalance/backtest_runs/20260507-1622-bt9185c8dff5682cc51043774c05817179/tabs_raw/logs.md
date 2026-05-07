# 策略日志

- INFO：989  |  WARNING：3  |  ERROR：8
- 触发调仓：22  |  跳过调仓：91

```text
2021-01-04 09:30:00 - INFO  - 年化波动率: G=0.1352, A=0.1980, N=0.2179
2021-01-04 09:30:00 - INFO  - 因子得分: s_G=0.612, s_A=-0.524, s_N=0.295
2021-01-04 09:30:00 - INFO  - 纯风险平价: G=0.434, A=0.296, N=0.269
2021-01-04 09:30:00 - INFO  - 因子调整后: G=0.486, A=0.236, N=0.277
2021-01-04 09:30:00 - WARNING - Security(code=518880.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - WARNING - Security(code=159819.XSHE) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - WARNING - Security(code=513100.XSHG) 在 positions 中不存在, 为了保持兼容, 我们返回空的 Position 对象, amount/price/avg_cost/acc_avg_cost 都是 0
2021-01-04 09:30:00 - INFO  - 当前权重: G=0.000, A=0.000, N=0.000
2021-01-04 09:30:00 - INFO  - 初始建仓：偏离度 1.0000，执行调仓
2021-01-04 09:30:00 - INFO  - 最终权重: G=0.486, A=0.236, N=0.277
2021-01-04 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 62300: Order(security=518880.XSHG mode=OrderTargetValue: _value=243049.6650309918 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-04 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778141036 security=518880.XSHG mode=OrderTargetValue: _value=243049.6650309918 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 62300)
2021-01-04 09:30:00 - INFO  - order StockOrder(entrust_id=1778141036 security=518880.XSHG mode=OrderTargetValue: _value=243049.6650309918 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 62300) trade price: 3.897, amount:62300, commission: 24.278309999999998
2021-01-04 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778141036 security=518880.XSHG mode=OrderTargetValue: _value=243049.6650309918 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=2021-01-04 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 62300)
2021-01-04 09:30:00 - INFO  - 调仓 黄金ETF(518880.XSHG): 目标市值 243050, 目标权重 48.6%
2021-01-04 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 125400: Order(security=159819.XSHE mode=OrderTargetValue: _value=118218.60692017061 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-04 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778141037 security=159819.XSHE mode=OrderTargetValue: _value=118218.60692017061 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 125400)
2021-01-04 09:30:00 - INFO  - order StockOrder(entrust_id=1778141037 security=159819.XSHE mode=OrderTargetValue: _value=118218.60692017061 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 125400) trade price: 0.942, amount:125400, commission: 11.812679999999999
2021-01-04 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778141037 security=159819.XSHE mode=OrderTargetValue: _value=118218.60692017061 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=2021-01-04 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 125400)
2021-01-04 09:30:00 - INFO  - 调仓 AI ETF(159819.XSHE): 目标市值 118219, 目标权重 23.6%
2021-01-04 09:30:00 - INFO  - 开仓数量必须是100的整数倍，调整为 31700: Order(security=513100.XSHG mode=OrderTargetValue: _value=138731.72804883757 style=MarketOrderStyle: _limit_price=0.0 side=long margin=False entrust_time=None finish_time=None)
2021-01-04 09:30:00 - INFO  - 下单检查标的数量：StockOrder(entrust_id=1778141038 security=513100.XSHG mode=OrderTargetValue: _value=138731.72804883757 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 31700)
2021-01-04 09:30:00 - INFO  - order StockOrder(entrust_id=1778141038 security=513100.XSHG mode=OrderTargetValue: _value=138731.72804883757 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=None comment= error=开仓数量必须是 100 的整数倍，调整为 31700) trade price: 4.369, amount:31700, commission: 13.84973
2021-01-04 09:30:00 - INFO  - 订单已委托：StockOrder(entrust_id=1778141038 security=513100.XSHG mode=OrderTargetValue: _value=138731.72804883757 style=MarketOrderStyle: _limit_price=0.0 side=long action=open margin=False entrust_time=2021-01-04 09:30:00 cancel_time=None finish_time=2021-01-04 09:30:00 comment= error=开仓数量必须是 100 的整数倍，调整为 31700)
2021-01-04 09:30:00 - INFO  - 调仓 纳指100ETF(513100.XSHG): 目标市值 138732, 目标权重 27.7%
2021-01-05 09:30:00 - INFO  - 年化波动率: G=0.1382, A=0.1915, N=0.2145
2021-01-05 09:30:00 - INFO  - 因子得分: s_G=0.991, s_A=-0.166, s_N=-0.418
2021-01-05 09:30:00 - INFO  - 纯风险平价: G=0.423, A=0.305, N=0.272
2021-01-05 09:30:00 - INFO  - 因子调整后: G=0.509, A=0.269, N=0.221
2021-01-05 09:30:00 - INFO  - 当前权重: G=0.488, A=0.240, N=0.271

... （剩余 1033 行未展开） ...

2021-06-21 09:30:00 - INFO  - 偏离度 0.0593 &lt;= 阈值 0.10，跳过本次调仓
2021-06-22 09:30:00 - INFO  - 年化波动率: G=0.1270, A=0.1944, N=0.1687
2021-06-22 09:30:00 - INFO  - 因子得分: s_G=-0.800, s_A=0.500, s_N=0.776
2021-06-22 09:30:00 - INFO  - 纯风险平价: G=0.416, A=0.272, N=0.313
2021-06-22 09:30:00 - INFO  - 因子调整后: G=0.312, A=0.308, N=0.380
2021-06-22 09:30:00 - INFO  - 当前权重: G=0.326, A=0.323, N=0.351
2021-06-22 09:30:00 - INFO  - 偏离度 0.0591 &lt;= 阈值 0.10，跳过本次调仓
2021-06-23 09:30:00 - INFO  - 年化波动率: G=0.1269, A=0.1943, N=0.1682
2021-06-23 09:30:00 - INFO  - 因子得分: s_G=-0.800, s_A=0.491, s_N=0.822
2021-06-23 09:30:00 - INFO  - 纯风险平价: G=0.415, A=0.271, N=0.313
2021-06-23 09:30:00 - INFO  - 因子调整后: G=0.310, A=0.306, N=0.384
2021-06-23 09:30:00 - INFO  - 当前权重: G=0.325, A=0.321, N=0.354
2021-06-23 09:30:00 - INFO  - 偏离度 0.0596 &lt;= 阈值 0.10，跳过本次调仓
2021-06-24 09:30:00 - INFO  - 年化波动率: G=0.1269, A=0.1933, N=0.1707
2021-06-24 09:30:00 - INFO  - 因子得分: s_G=-0.800, s_A=0.500, s_N=0.855
```

> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。
