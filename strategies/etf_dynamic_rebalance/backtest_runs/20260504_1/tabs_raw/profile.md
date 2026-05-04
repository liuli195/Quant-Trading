性能分析
Timer unit: 1e-06 s

Total time: 0.002361 s
File: /tmp/strategy/user_code.py
Function: initialize at line 32

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
    32                                           def initialize(context):
    33         1         47.0     47.0      2.0      set_option('use_real_price', True)
    34         1         23.0     23.0      1.0      set_option("avoid_future_data", True)
    35         1        187.0    187.0      7.9      set_parameter(context)
    36         1          1.0      1.0      0.0      set_order_cost(
    37         1          1.0      1.0      0.0          OrderCost(
    38         1          1.0      1.0      0.0              open_tax=0,
    39         1          0.0      0.0      0.0              close_tax=0,
    40         1          1.0      1.0      0.0              open_commission=0.0001,
    41         1          1.0      1.0      0.0              close_commission=0.0001,
    42         1         14.0     14.0      0.6              min_commission=0
    43                                                   ),
    44         1         34.0     34.0      1.4          type='fund'
    45                                               )
    46         1         26.0     26.0      1.1      set_slippage(FixedSlippage(0.0), type='fund')
    47         1          1.0      1.0      0.0      run_daily(
    48         1          1.0      1.0      0.0          daily_check,
    49         1          0.0      0.0      0.0          time='open',
    50         1       2023.0   2023.0     85.7          reference_security='000300.XSHG'
    51                                               )

Total time: 0 s
File: /tmp/strategy/user_code.py
Function: set_parameter at line 52

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
    52                                           def set_parameter(context):
    53                                               g.etf_pool = [
    54                                                   '518880.XSHG',
    55                                                   '159819.XSHE',
    56                                                   '513100.XSHG',
    57                                               ]
    58                                               g.etf_names = ['黄金ETF', 'AI ETF', '纳指100ETF']
    59                                               g.volatility_window = 60
    60                                               g.annual_factor = 252
    61                                               g.gold_trend_w = 0.5
    62                                               g.gold_rs_w = 0.3
    63                                               g.gold_riskoff_w = 0.2
    64                                               g.ai_momentum_w = 0.45
    65                                               g.ai_trend_w = 0.25
    66                                               g.ai_volpenalty_w = 0.20
    67                                               g.ai_drawdown_w = 0.10
    68                                               g.nasdaq_momentum_w = 0.40
    69                                               g.nasdaq_trend_w = 0.20
    70                                               g.nasdaq_riskon_w = 0.20
    71                                               g.nasdaq_volpenalty_w = 0.20
    72                                               g.trend_ma_window = 20
    73                                               g.momentum_window_short = 20
    74                                               g.momentum_window_long = 60
    75                                               g.vol_window_short = 20
    76                                               g.vol_window_long = 60
    77                                               g.drawdown_window = 60
    78                                               g.k = 0.3
    79                                               g.weight_bounds = [
    80                                                   (0.10, 0.60),
    81                                                   (0.10, 0.50),
    82                                                   (0.10, 0.60),
    83                                               ]
    84                                               g.max_weight_change = 0.10
    85                                               g.rebalance_threshold = 0.10
    86                                               g.live_days = 100
    87                                               g.benchmark = '000300.XSHG'
    88                                               set_benchmark(g.benchmark)

Total time: 56.8355 s
File: /tmp/strategy/user_code.py
Function: daily_check at line 89

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
    89                                           def daily_check(context):
    90       804     574012.0    713.9      1.0      total_value = context.portfolio.total_value
    91       804       2365.0      2.9      0.0      prices_list = []
    92       804       1722.0      2.1      0.0      valid_etfs = []
    93      3216       8176.0      2.5      0.0      for etf in g.etf_pool:
    94      2412       5583.0      2.3      0.0          prices_raw = get_price(
    95      2412       4892.0      2.0      0.0              etf,
    96      2412       6565.0      2.7      0.0              count=g.live_days,
    97      2412     198489.0     82.3      0.3              end_date=context.previous_date,
    98      2412       5529.0      2.3      0.0              frequency='daily',
    99      2412       5286.0      2.2      0.0              fields=['close'],
   100      2412       4998.0      2.1      0.0              panel=False,
   101      2412    8029933.0   3329.2     14.1              fq=None
   102                                                   )
   103      2412      16457.0      6.8      0.0          if prices_raw is not None and len(prices_raw) > 0:
   104      2412     373904.0    155.0      0.7              prices_list.append(prices_raw['close'].values)
   105      2412       6823.0      2.8      0.0              valid_etfs.append(etf)
   106                                                   else:
   107                                                       prices_list.append(None)
   108       804       1855.0      2.3      0.0      if len(valid_etfs) < 3:
   109                                                   log.info("【警告】部分 ETF 无价格数据，跳过本次调仓")
   110                                                   return
   111       804       4576.0      5.7      0.0      valid_indices = [i for i, p in enumerate(prices_list) if p is not None]
   112       804       3426.0      4.3      0.0      valid_prices = [prices_list[i] for i in valid_indices]
   113       804       4622.0      5.7      0.0      min_len = min(len(p) for p in valid_prices)
   114       804       2253.0      2.8      0.0      close_prices = pd.DataFrame({
   115                                                   g.etf_pool[i]: valid_prices[j][-min_len:]
   116       804     519986.0    646.7      0.9          for j, i in enumerate(valid_indices)
   117                                               })
   118       804    1791034.0   2227.7      3.2      close_prices = close_prices.dropna()
   119       804       5170.0      6.4      0.0      if len(close_prices) < 61:
   120                                                   log.info("【警告】有效数据不足 61 日，跳过本次调仓")
   121                                                   return
   122       804      23651.0     29.4      0.0      prices_array = close_prices.values
   123       804      17321.0     21.5      0.0      log_returns = np.log(prices_array[1:] / prices_array[:-1])
   124       804       3269.0      4.1      0.0      vol_window = min(g.volatility_window, len(log_returns))
   125       804       2233.0      2.8      0.0      recent_returns = log_returns[-vol_window:]
   126       804      59078.0     73.5      0.1      daily_std = np.std(recent_returns, axis=0, ddof=1)
   127       804       8447.0     10.5      0.0      volatilities = daily_std * np.sqrt(g.annual_factor)
   128       804       2514.0      3.1      0.0      log.info("年化波动率: G=%.4f, A=%.4f, N=%.4f" % (
   129       804     217805.0    270.9      0.4          volatilities[0], volatilities[1], volatilities[2]
   130                                               ))
   131       804       3222.0      4.0      0.0      gold_prices = prices_array[:, 0]
   132       804       2103.0      2.6      0.0      ai_prices = prices_array[:, 1]
   133       804       1929.0      2.4      0.0      nasdaq_prices = prices_array[:, 2]
   134       804      65009.0     80.9      0.1      check_date = context.previous_date
   135       804       2805.0      3.5      0.0      gold_code, ai_code, nasdaq_code = g.etf_pool
   136       804       1968.0      2.4      0.0      s_G = compute_gold_factors(gold_prices, nasdaq_prices, check_date,
   137       804   13553211.0  16857.2     23.8                                  gold_code=gold_code, nasdaq_code=nasdaq_code)
   138       804   10863828.0  13512.2     19.1      s_A = compute_ai_factors(ai_prices, check_date, ai_code=ai_code)
   139       804       2183.0      2.7      0.0      s_N = compute_nasdaq_factors(nasdaq_prices, gold_prices, check_date,
   140       804   17433949.0  21684.0     30.7                                    nasdaq_code=nasdaq_code, gold_code=gold_code)
   141       804       8126.0     10.1      0.0      factor_scores = np.clip(np.array([s_G, s_A, s_N]), -1.0, 1.0)
   142       804       2706.0      3.4      0.0      log.info("因子得分: s_G=%.3f, s_A=%.3f, s_N=%.3f" % (
   143       804     281865.0    350.6      0.5          factor_scores[0], factor_scores[1], factor_scores[2]
   144                                               ))
   145       804       9858.0     12.3      0.0      inv_vol = 1.0 / (volatilities + 1e-10)
   146       804      18775.0     23.4      0.0      rp_weights = inv_vol / np.sum(inv_vol)
   147       804      32460.0     40.4      0.1      raw_weights = compute_target_weights(volatilities, factor_scores, g.k)
   148       804       1957.0      2.4      0.0      log.info("纯风险平价: G=%.3f, A=%.3f, N=%.3f" % (
   149       804     142612.0    177.4      0.3          rp_weights[0], rp_weights[1], rp_weights[2]
   150                                               ))
   151       804       2224.0      2.8      0.0      log.info("因子调整后: G=%.3f, A=%.3f, N=%.3f" % (
   152       804     158038.0    196.6      0.3          raw_weights[0], raw_weights[1], raw_weights[2]
   153                                               ))
   154       804       4430.0      5.5      0.0      current_weights = np.zeros(3)
   155      3216       8955.0      2.8      0.0      for i, etf in enumerate(g.etf_pool):
   156      2412     237032.0     98.3      0.4          pos = context.portfolio.positions[etf]
   157      2412      17025.0      7.1      0.0          if pos is not None and pos.total_amount > 0:
   158      2409      40090.0     16.6      0.1              current_weights[i] = pos.value / total_value
   159       804       2063.0      2.6      0.0      log.info("当前权重: G=%.3f, A=%.3f, N=%.3f" % (
   160       804     150673.0    187.4      0.3          current_weights[0], current_weights[1], current_weights[2]
   161                                               ))
   162       804      19893.0     24.7      0.0      deviation = np.sum(np.abs(raw_weights - current_weights))
   163       804       7395.0      9.2      0.0      has_positions = np.sum(current_weights) > 1e-10
   164       804       2625.0      3.3      0.0      if has_positions and deviation <= g.rebalance_threshold:
   165       641       1505.0      2.3      0.0          log.info("偏离度 %.4f <= 阈值 %.2f，跳过本次调仓" % (
   166       641     110640.0    172.6      0.2              deviation, g.rebalance_threshold
   167                                                   ))
   168       641       1508.0      2.4      0.0          return
   169       163        377.0      2.3      0.0      if has_positions:
   170       162        372.0      2.3      0.0          log.info("偏离度 %.4f > 阈值 %.2f，触发调仓" % (
   171       162      25962.0    160.3      0.0              deviation, g.rebalance_threshold
   172                                                   ))
   173                                               else:
   174         1        134.0    134.0      0.0          log.info("初始建仓：偏离度 %.4f，执行调仓" % deviation)
   175       163        445.0      2.7      0.0      final_weights = apply_weight_constraints(
   176       163        345.0      2.1      0.0          raw_weights,
   177       163        331.0      2.0      0.0          current_weights,
   178       163        422.0      2.6      0.0          g.weight_bounds,
   179       163     104374.0    640.3      0.2          g.max_weight_change
   180                                               )
   181       163        394.0      2.4      0.0      log.info("最终权重: G=%.3f, A=%.3f, N=%.3f" % (
   182       163      28498.0    174.8      0.1          final_weights[0], final_weights[1], final_weights[2]
   183                                               ))
   184       652       2096.0      3.2      0.0      for i, etf in enumerate(g.etf_pool):
   185       489       1631.0      3.3      0.0          target_value = total_value * final_weights[i]
   186       489    1448018.0   2961.2      2.5          order = order_target_value(etf, target_value)
   187       489       1510.0      3.1      0.0          if order is None:
   188        53        154.0      2.9      0.0              log.error("【调仓失败】%s(%s): 目标市值 %.0f 下单失败，请检查账户状态" % (
   189        53       6905.0    130.3      0.0                  g.etf_names[i], etf, target_value
   190                                                       ))
   191                                                   else:
   192       436       1234.0      2.8      0.0              log.info("调仓 %s(%s): 目标市值 %.0f, 目标权重 %.1f%%" % (
   193       436     107692.0    247.0      0.2                  g.etf_names[i], etf, target_value, final_weights[i] * 100
   194                                                       ))

Total time: 0.651845 s
File: /tmp/strategy/user_code.py
Function: zscore_clip at line 195

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   195                                           def zscore_clip(current_value, historical_values, floor=-1.0, ceiling=1.0):
   196      7236       8259.0      1.1      1.3      if len(historical_values) < 2:
   197                                                   return 0.0
   198      7236     202062.0     27.9     31.0      mu = np.mean(historical_values)
   199      7236     362959.0     50.2     55.7      sigma = np.std(historical_values, ddof=1)
   200      7236       9572.0      1.3      1.5      if sigma < 1e-10:
   201                                                   return 0.0
   202      7236       7434.0      1.0      1.1      z = (current_value - mu) / sigma
   203      7236      61559.0      8.5      9.4      return float(np.clip(z, floor, ceiling))

Total time: 13.5193 s
File: /tmp/strategy/user_code.py
Function: compute_gold_factors at line 204

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   204                                           def compute_gold_factors(gold_prices, nasdaq_prices, check_date,
   205                                                                     gold_code='518880.XSHG', nasdaq_code='513100.XSHG'):
   206       804       1192.0      1.5      0.0      min_len = g.trend_ma_window
   207       804       1125.0      1.4      0.0      if len(gold_prices) <= min_len:
   208                                                   return 0.0
   209       804    3743433.0   4656.0     27.7      bias_result = BIAS([gold_code], check_date=check_date, N1=20)
   210       804       2168.0      2.7      0.0      trend_current = bias_result[0].get(gold_code, 0.0) / 100.0
   211       804      29299.0     36.4      0.2      gold_ma20 = np.convolve(gold_prices, np.ones(min_len)/min_len, mode='valid')
   212       804       1403.0      1.7      0.0      gold_aligned = gold_prices[min_len-1:]
   213       804       3593.0      4.5      0.0      trend_vals = (gold_aligned - gold_ma20) / gold_ma20
   214       804      89675.0    111.5      0.7      trend_score = zscore_clip(trend_current, trend_vals)
   215       804       1367.0      1.7      0.0      if len(gold_prices) <= min_len or len(nasdaq_prices) <= min_len:
   216                                                   rs_score = 0.0
   217                                               else:
   218       804    3196736.0   3976.0     23.6          roc_g = ROC([gold_code], check_date=check_date, timeperiod=20)
   219       804    3165750.0   3937.5     23.4          roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
   220       804       3042.0      3.8      0.0          rs_current = (roc_g.get(gold_code, 0.0) - roc_n.get(nasdaq_code, 0.0)) / 100.0
   221       804       7783.0      9.7      0.1          gold_20d_ret = gold_prices[min_len:] / gold_prices[:-min_len] - 1.0
   222       804       3637.0      4.5      0.0          nasdaq_20d_ret = nasdaq_prices[min_len:] / nasdaq_prices[:-min_len] - 1.0
   223       804       1648.0      2.0      0.0          rs_vals = gold_20d_ret - nasdaq_20d_ret
   224       804      90808.0    112.9      0.7          rs_score = zscore_clip(rs_current, rs_vals)
   225       804       1112.0      1.4      0.0      if len(nasdaq_prices) > min_len:
   226       804    3152836.0   3921.4     23.3          roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
   227       804       3411.0      4.2      0.0          riskoff_score = 1.0 if roc_n.get(nasdaq_code, 0.0) < 0 else 0.0
   228                                               else:
   229                                                   riskoff_score = 0.0
   230                                               s_G = (g.gold_trend_w * trend_score
   231                                                      + g.gold_rs_w * rs_score
   232       804       2612.0      3.2      0.0             + g.gold_riskoff_w * riskoff_score)
   233       804      16665.0     20.7      0.1      return float(np.clip(s_G, -1.0, 1.0))

Total time: 10.7736 s
File: /tmp/strategy/user_code.py
Function: compute_ai_factors at line 234

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   234                                           def compute_ai_factors(ai_prices, check_date, ai_code='159819.XSHE'):
   235       804       2809.0      3.5      0.0      if len(ai_prices) < g.trend_ma_window + 1:
   236                                                   return 0.0
   237       804       9879.0     12.3      0.1      ai_log_returns = np.log(ai_prices[1:] / ai_prices[:-1])
   238       804       1487.0      1.8      0.0      mom_w = g.momentum_window_short
   239       804       1648.0      2.0      0.0      if len(ai_prices) > mom_w:
   240       804    3148549.0   3916.1     29.2          roc_result = ROC([ai_code], check_date=check_date, timeperiod=20)
   241       804       3290.0      4.1      0.0          roc20_current = roc_result.get(ai_code, 0.0) / 100.0
   242       804       8431.0     10.5      0.1          roc20_series = ai_prices[mom_w:] / ai_prices[:-mom_w] - 1.0
   243       804      90446.0    112.5      0.8          mom_score = zscore_clip(roc20_current, roc20_series)
   244                                               else:
   245                                                   mom_score = 0.0
   246       804       2501.0      3.1      0.0      min_len = g.trend_ma_window
   247       804    3636739.0   4523.3     33.8      bias_result = BIAS([ai_code], check_date=check_date, N1=20)
   248       804       2705.0      3.4      0.0      trend_current = bias_result[0].get(ai_code, 0.0) / 100.0
   249       804      28497.0     35.4      0.3      ai_ma20 = np.convolve(ai_prices, np.ones(min_len)/min_len, mode='valid')
   250       804       2017.0      2.5      0.0      ai_aligned = ai_prices[min_len-1:]
   251       804       4285.0      5.3      0.0      trend_vals = (ai_aligned - ai_ma20) / ai_ma20
   252       804      84855.0    105.5      0.8      trend_score = zscore_clip(trend_current, trend_vals)
   253       804       1991.0      2.5      0.0      short_w = g.vol_window_short
   254       804       1564.0      1.9      0.0      long_w = g.vol_window_long
   255       804       1737.0      2.2      0.0      if len(ai_log_returns) >= long_w:
   256       804       1465.0      1.8      0.0          short_vols = np.array([
   257       804       1717.0      2.1      0.0              np.std(ai_log_returns[i:i+short_w], ddof=1)
   258       804    2264978.0   2817.1     21.0              for i in range(len(ai_log_returns) - short_w + 1)
   259                                                   ])
   260       804       2002.0      2.5      0.0          long_vols = np.array([
   261       804       1670.0      2.1      0.0              np.std(ai_log_returns[i:i+long_w], ddof=1)
   262       804    1129126.0   1404.4     10.5              for i in range(len(ai_log_returns) - long_w + 1)
   263                                                   ])
   264       804       2655.0      3.3      0.0          common_len = min(len(short_vols), len(long_vols))
   265       804       1516.0      1.9      0.0          if common_len > 1:
   266       804       6162.0      7.7      0.1              vol_ratios = short_vols[-common_len:] / np.maximum(long_vols[-common_len:], 1e-10)
   267       804       1772.0      2.2      0.0              vol_current = vol_ratios[-1]
   268       804      61408.0     76.4      0.6              vol_score = zscore_clip(vol_current, vol_ratios)
   269                                                   else:
   270                                                       vol_score = 0.0
   271                                               else:
   272                                                   vol_score = 0.0
   273       804       1738.0      2.2      0.0      dd_window = g.drawdown_window
   274       804       1662.0      2.1      0.0      if len(ai_prices) >= dd_window:
   275       804       1446.0      1.8      0.0          ai_max60 = np.array([
   276       804       1598.0      2.0      0.0              np.max(ai_prices[i:i+dd_window])
   277       804     170712.0    212.3      1.6              for i in range(len(ai_prices) - dd_window + 1)
   278                                                   ])
   279       804       1904.0      2.4      0.0          ai_aligned_dd = ai_prices[dd_window-1:]
   280       804       4980.0      6.2      0.0          dd_vals = 1.0 - ai_aligned_dd / ai_max60
   281       804       1715.0      2.1      0.0          dd_current = dd_vals[-1]
   282       804      62810.0     78.1      0.6          dd_score = zscore_clip(dd_current, dd_vals, floor=0.0, ceiling=1.0)
   283                                               else:
   284                                                   dd_score = 0.0
   285                                               s_A = (g.ai_momentum_w * mom_score
   286                                                      + g.ai_trend_w * trend_score
   287                                                      - g.ai_volpenalty_w * vol_score
   288       804       3192.0      4.0      0.0             - g.ai_drawdown_w * dd_score)
   289       804      13965.0     17.4      0.1      return float(np.clip(s_A, -1.0, 1.0))

Total time: 17.3507 s
File: /tmp/strategy/user_code.py
Function: compute_nasdaq_factors at line 290

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   290                                           def compute_nasdaq_factors(nasdaq_prices, gold_prices, check_date,
   291                                                                       nasdaq_code='513100.XSHG', gold_code='518880.XSHG'):
   292       804       2296.0      2.9      0.0      if len(nasdaq_prices) < g.trend_ma_window + 1:
   293                                                   return 0.0
   294       804       6946.0      8.6      0.0      n_log_returns = np.log(nasdaq_prices[1:] / nasdaq_prices[:-1])
   295       804       1534.0      1.9      0.0      mom_long_w = g.momentum_window_long
   296       804       1418.0      1.8      0.0      if len(nasdaq_prices) > mom_long_w:
   297       804    3652097.0   4542.4     21.0          roc_result = ROC([nasdaq_code], check_date=check_date, timeperiod=60)
   298       804       3163.0      3.9      0.0          roc60_current = roc_result.get(nasdaq_code, 0.0) / 100.0
   299       804       8386.0     10.4      0.0          roc60_series = nasdaq_prices[mom_long_w:] / nasdaq_prices[:-mom_long_w] - 1.0
   300       804      89626.0    111.5      0.5          mom_score = zscore_clip(roc60_current, roc60_series)
   301                                               else:
   302                                                   mom_score = 0.0
   303       804       2393.0      3.0      0.0      min_len = g.trend_ma_window
   304       804    3632669.0   4518.2     20.9      bias_result = BIAS([nasdaq_code], check_date=check_date, N1=20)
   305       804       2760.0      3.4      0.0      trend_current = bias_result[0].get(nasdaq_code, 0.0) / 100.0
   306       804      27267.0     33.9      0.2      n_ma20 = np.convolve(nasdaq_prices, np.ones(min_len)/min_len, mode='valid')
   307       804       1885.0      2.3      0.0      n_aligned = nasdaq_prices[min_len-1:]
   308       804       3990.0      5.0      0.0      trend_vals = (n_aligned - n_ma20) / n_ma20
   309       804      84615.0    105.2      0.5      trend_score = zscore_clip(trend_current, trend_vals)
   310       804       1950.0      2.4      0.0      short_w = g.vol_window_short
   311       804       1322.0      1.6      0.0      long_w = g.vol_window_long
   312       804       1622.0      2.0      0.0      if len(n_log_returns) >= long_w:
   313       804       1322.0      1.6      0.0          short_vols = np.array([
   314       804       1496.0      1.9      0.0              np.std(n_log_returns[i:i+short_w], ddof=1)
   315       804    2267630.0   2820.4     13.1              for i in range(len(n_log_returns) - short_w + 1)
   316                                                   ])
   317       804       1888.0      2.3      0.0          long_vols = np.array([
   318       804       1481.0      1.8      0.0              np.std(n_log_returns[i:i+long_w], ddof=1)
   319       804    1126921.0   1401.6      6.5              for i in range(len(n_log_returns) - long_w + 1)
   320                                                   ])
   321       804       2553.0      3.2      0.0          common_len = min(len(short_vols), len(long_vols))
   322       804       1413.0      1.8      0.0          if common_len > 1:
   323       804       5945.0      7.4      0.0              vol_ratios = short_vols[-common_len:] / np.maximum(long_vols[-common_len:], 1e-10)
   324       804       1749.0      2.2      0.0              vol_current = vol_ratios[-1]
   325       804      60681.0     75.5      0.3              vol_score = zscore_clip(vol_current, vol_ratios)
   326                                                   else:
   327                                                       vol_score = 0.0
   328                                               else:
   329                                                   vol_score = 0.0
   330       804       1929.0      2.4      0.0      if len(nasdaq_prices) > min_len and len(gold_prices) > min_len:
   331       804    3176386.0   3950.7     18.3          roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
   332       804    3145239.0   3912.0     18.1          roc_g = ROC([gold_code], check_date=check_date, timeperiod=20)
   333       804       3270.0      4.1      0.0          n_20d_ret = roc_n.get(nasdaq_code, 0.0) / 100.0
   334       804       1591.0      2.0      0.0          g_20d_ret = roc_g.get(gold_code, 0.0) / 100.0
   335       804       2582.0      3.2      0.0          riskon_score = 1.0 if (n_20d_ret > 0 and n_20d_ret > g_20d_ret) else 0.0
   336                                               else:
   337                                                   riskon_score = 0.0
   338                                               s_N = (g.nasdaq_momentum_w * mom_score
   339                                                      + g.nasdaq_trend_w * trend_score
   340                                                      + g.nasdaq_riskon_w * riskon_score
   341       804       3663.0      4.6      0.0             - g.nasdaq_volpenalty_w * vol_score)
   342       804      17023.0     21.2      0.1      return float(np.clip(s_N, -1.0, 1.0))

Total time: 0.020654 s
File: /tmp/strategy/user_code.py
Function: compute_target_weights at line 343

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   343                                           def compute_target_weights(volatilities, factor_scores, k):
   344       804       4155.0      5.2     20.1      adjusted_factor = 1.0 + k * factor_scores
   345       804       2323.0      2.9     11.2      adjusted_factor = np.maximum(adjusted_factor, 0.01)
   346       804        556.0      0.7      2.7      eps = 1e-10
   347       804       2750.0      3.4     13.3      raw_weights = adjusted_factor / (volatilities + eps)
   348       804       6524.0      8.1     31.6      total = np.sum(raw_weights)
   349       804       1125.0      1.4      5.4      if total > eps:
   350       804       2730.0      3.4     13.2          weights = raw_weights / total
   351                                               else:
   352                                                   weights = np.ones(3) / 3.0
   353       804        491.0      0.6      2.4      return weights

Total time: 0.069964 s
File: /tmp/strategy/user_code.py
Function: apply_weight_constraints at line 354

Line #      Hits         Time  Per Hit   % Time  Line Contents
==============================================================
   354                                           def apply_weight_constraints(target_weights, current_weights, bounds, max_change):
   355       163       1309.0      8.0      1.9      lower_bounds = np.array([b[0] for b in bounds])
   356       163        766.0      4.7      1.1      upper_bounds = np.array([b[1] for b in bounds])
   357       163       1992.0     12.2      2.8      has_position = np.sum(current_weights) > 1e-10
   358       163        218.0      1.3      0.3      if has_position:
   359       162       1188.0      7.3      1.7          effective_lower = np.maximum(lower_bounds, current_weights - max_change)
   360       162        787.0      4.9      1.1          effective_upper = np.minimum(upper_bounds, current_weights + max_change)
   361                                               else:
   362         1          1.0      1.0      0.0          effective_lower = lower_bounds
   363         1          2.0      2.0      0.0          effective_upper = upper_bounds
   364       652       1100.0      1.7      1.6      for i in range(3):
   365       489        838.0      1.7      1.2          if effective_lower[i] > effective_upper[i]:
   366                                                       effective_lower[i] = lower_bounds[i]
   367                                                       effective_upper[i] = upper_bounds[i]
   368       163       2206.0     13.5      3.2      if np.sum(effective_lower) > 1.0 + 1e-10 or np.sum(effective_upper) < 1.0 - 1e-10:
   369                                                   log.warning("【权重约束】含 max_change 无可行解（下界和=%.4f, 上界和=%.4f），"
   370                                                               "放宽至 hard bounds 重试" % (np.sum(effective_lower), np.sum(effective_upper)))
   371                                                   effective_lower = lower_bounds
   372                                                   effective_upper = upper_bounds
   373                                                   if np.sum(effective_lower) > 1.0 + 1e-10 or np.sum(effective_upper) < 1.0 - 1e-10:
   374                                                       log.warning("【权重约束】hard bounds 亦不可行，回退到等权分配")
   375                                                       w_fallback = np.clip(np.ones(3) / 3.0, effective_lower, effective_upper)
   376                                                       return w_fallback / np.sum(w_fallback)
   377       163       1519.0      9.3      2.2      w = np.clip(target_weights, effective_lower, effective_upper)
   378       163       1144.0      7.0      1.6      total = np.sum(w)
   379       163        390.0      2.4      0.6      if abs(total - 1.0) < 1e-12:
   380        96        119.0      1.2      0.2          return w
   381        67        122.0      1.8      0.2      if total < 1e-12:
   382                                                   w = np.clip(np.ones(3) / 3.0, effective_lower, effective_upper)
   383                                                   return w / np.sum(w)
   384        67       1201.0     17.9      1.7      theta_low = np.min(w) - np.max(upper_bounds)
   385        67        699.0     10.4      1.0      theta_high = np.max(w) - np.min(effective_lower)
   386      2582       3120.0      1.2      4.5      for _ in range(50):
   387      2582       3953.0      1.5      5.7          theta = (theta_low + theta_high) / 2.0
   388      2582      18411.0      7.1     26.3          w_proj = np.clip(w - theta, effective_lower, effective_upper)
   389      2582      17561.0      6.8     25.1          total_proj = np.sum(w_proj)
   390      2582       4622.0      1.8      6.6          if abs(total_proj - 1.0) < 1e-12:
   391        67         90.0      1.3      0.1              return w_proj
   392      2515       3372.0      1.3      4.8          if total_proj < 1.0:
   393      1194       1584.0      1.3      2.3              theta_high = theta
   394                                                   else:
   395      1321       1650.0      1.2      2.4              theta_low = theta
   396                                               return np.clip(w - theta, effective_lower, effective_upper)

