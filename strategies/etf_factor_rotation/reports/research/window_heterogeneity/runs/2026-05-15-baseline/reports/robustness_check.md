# 时间窗异质性稳健性检查

- 留出集非负记录数：8/21

## 留出集

| factor | family | etf | etf_label | discovery_best_window | discovery_best_band | discovery_benefit | holdout_benefit | holdout_nonnegative |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| crowd_amount | crowding | 159819.XSHE | AI_ETF | 40 | mid | 0.007620411893973265 | 0.0433440434256382 | True |
| crowd_amount | crowding | 513100.XSHG | NASDAQ_ETF | 20 | short | 0.011194332263545624 | 0.005628097542875954 | True |
| crowd_amount | crowding | 518880.XSHG | GOLD_ETF | 40 | mid | 0.001665250322201455 |  | False |
| crowd_deviation | crowding | 159819.XSHE | AI_ETF | 10 | short | 0.003874004609349783 | -0.01153846382356545 | False |
| crowd_deviation | crowding | 513100.XSHG | NASDAQ_ETF | 40 | mid | -0.0036414573990433425 | -0.010404189223117215 | False |
| crowd_deviation | crowding | 518880.XSHG | GOLD_ETF | 20 | short | 0.004702283630825865 | -0.010528502393075127 | False |
| crowd_ret_mid | crowding | 159819.XSHE | AI_ETF | 120 | long | 0.004923353084199736 | 0.008896502342076661 | True |
| crowd_ret_mid | crowding | 513100.XSHG | NASDAQ_ETF | 30 | short | -0.004264063190523044 | -0.0015193169174702154 | False |
| crowd_ret_mid | crowding | 518880.XSHG | GOLD_ETF | 30 | short | 0.003718160879016986 | -0.014215690859380212 | False |
| crowd_ret_short | crowding | 159819.XSHE | AI_ETF | 120 | long | 0.004923353084199736 | 0.008896502342076661 | True |
| crowd_ret_short | crowding | 513100.XSHG | NASDAQ_ETF | 30 | short | -0.004264063190523044 | -0.0015193169174702154 | False |
| crowd_ret_short | crowding | 518880.XSHG | GOLD_ETF | 30 | short | 0.003718160879016986 | -0.014215690859380212 | False |
| crowd_volatility | crowding | 159819.XSHE | AI_ETF | 40 | mid | 0.008806930205794159 | 0.028464645360574782 | True |
| crowd_volatility | crowding | 513100.XSHG | NASDAQ_ETF | 20 | short | 0.020810690834083753 | -0.003657455977430168 | False |
| crowd_volatility | crowding | 518880.XSHG | GOLD_ETF | 40 | mid | 0.0026040956030434 | 0.023713601843198723 | True |
| momentum_return | momentum | 159819.XSHE | AI_ETF | 30 | short | 0.002809284416837272 | -0.01341986113770791 | False |
| momentum_return | momentum | 513100.XSHG | NASDAQ_ETF | 80 | mid | 0.01586262305143793 | -0.002386773997840336 | False |
| momentum_return | momentum | 518880.XSHG | GOLD_ETF | 160 | long | 0.0023972245061654133 | -0.019535615640163873 | False |
| trend_gate | trend | 159819.XSHE | AI_ETF | 20 | short | 0.002816940486078937 | 0.012849842355175225 | True |
| trend_gate | trend | 513100.XSHG | NASDAQ_ETF | 80 | mid | 0.010880657252106535 | 0.005518568945236361 | True |
| trend_gate | trend | 518880.XSHG | GOLD_ETF | 100 | long | 0.0012299640399744652 | -0.002982884369064534 | False |

## 分段最佳档位

| factor | etf | best_band | count |
| --- | --- | --- | --- |
| crowd_amount | 159819.XSHE | mid | 3 |
| crowd_amount | 513100.XSHG | mid | 2 |
| crowd_amount | 513100.XSHG | short | 1 |
| crowd_amount | 518880.XSHG | mid | 1 |
| crowd_amount | 518880.XSHG | short | 2 |
| crowd_deviation | 159819.XSHE | mid | 1 |
| crowd_deviation | 159819.XSHE | short | 2 |
| crowd_deviation | 513100.XSHG | mid | 1 |
| crowd_deviation | 513100.XSHG | short | 2 |
| crowd_deviation | 518880.XSHG | mid | 1 |
| crowd_deviation | 518880.XSHG | short | 2 |
| crowd_ret_mid | 159819.XSHE | long | 1 |
| crowd_ret_mid | 159819.XSHE | mid | 2 |
| crowd_ret_mid | 513100.XSHG | mid | 3 |
| crowd_ret_mid | 518880.XSHG | mid | 1 |
| crowd_ret_mid | 518880.XSHG | short | 2 |
| crowd_ret_short | 159819.XSHE | long | 1 |
| crowd_ret_short | 159819.XSHE | mid | 2 |
| crowd_ret_short | 513100.XSHG | mid | 3 |
| crowd_ret_short | 518880.XSHG | mid | 1 |
| crowd_ret_short | 518880.XSHG | short | 2 |
| crowd_volatility | 159819.XSHE | mid | 2 |
| crowd_volatility | 159819.XSHE | short | 1 |
| crowd_volatility | 513100.XSHG | mid | 1 |
| crowd_volatility | 513100.XSHG | short | 2 |
| crowd_volatility | 518880.XSHG | mid | 3 |
| momentum_return | 159819.XSHE | long | 1 |
| momentum_return | 159819.XSHE | short | 2 |
| momentum_return | 513100.XSHG | short | 3 |
| momentum_return | 518880.XSHG | long | 1 |
| momentum_return | 518880.XSHG | mid | 1 |
| momentum_return | 518880.XSHG | short | 1 |
| trend_gate | 159819.XSHE | short | 3 |
| trend_gate | 513100.XSHG | mid | 1 |
| trend_gate | 513100.XSHG | short | 2 |
| trend_gate | 518880.XSHG | mid | 1 |
| trend_gate | 518880.XSHG | short | 2 |
