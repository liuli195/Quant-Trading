# 策略分析

## 回测概况

- 回测对象：ETF 因子轮动策略，120 日均线参数化软门槛版本。
- 回测区间：2026-04-01 至 2026-04-30。
- 回测 ID：`3f882f065d574703da0e74f180e2a24b`。
- 数据来源：[summary_metrics.json](../summary_metrics.json) <!-- pathref: backtest_run(strategy=etf_factor_rotation, run_id=20260507-2242-bt3f882f065d574703da0e74f180e2a24b)/summary_metrics.json -->、[logs.md](../tabs_raw/logs.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260507-2242-bt3f882f065d574703da0e74f180e2a24b)/logs.md -->、[transactioninfo.md](../tabs_raw/transactioninfo.md) <!-- pathref: backtest_tabs_dir(strategy=etf_factor_rotation, run_id=20260507-2242-bt3f882f065d574703da0e74f180e2a24b)/transactioninfo.md -->。

## 核心结果

| 指标 | 数值 |
|---|---:|
| 策略收益 | 4.59% |
| 策略年化收益 | 70.60% |
| 基准收益 | 8.03% |
| 超额收益 | -3.18% |
| 最大回撤 | 0.55% |
| Beta | 0.301 |
| 夏普比率 | 10.483 |

本次是 1 个月烟雾回测，核心价值是验证软门槛实盘链路，而不是得出长期收益结论。策略收益为正但低于基准，主要原因是组合保持低 Beta、低总仓位，未满额参与 2026 年 4 月反弹。

## 软门槛验证

日志确认 `TrendGate` 已从 0/1 改为连续值并参与后续链路：

| 调仓日 | 159819.XSHE | 513100.XSHG | 518880.XSHG | 观察 |
|---|---:|---:|---:|---|
| 2026-04-01 | 0.40 | 0.00 | 1.00 | 人工智能 ETF 低于 MA120 但进入软门槛区间，获得部分仓位资格 |
| 2026-04-07 | 0.49 | 0.27 | 1.00 | 纳指 ETF 从硬门槛下的 0 变为可参与候选 |
| 2026-04-13 | 1.00 | 0.69 | 1.00 | 纳指 ETF 以软门槛乘数参与 TopK 和最终权重 |
| 2026-04-27 | 1.00 | 1.00 | 1.00 | 三只 ETF 均完整通过趋势门槛 |

链路上，`TrendGate > 0` 的资产参与动量、TopK、风险平价与最终权重合成；最终权重继续按 `TrendGate` 折扣，降下来的部分保留现金。2026-04-01 人工智能 ETF 的 `TrendGate=0.40`，最终目标权重为 18.64%，说明软门槛已经实际影响仓位。

## 交易与风险

- 全月 3 笔成交：2026-04-01 买入人工智能 ETF，2026-04-13 卖出部分人工智能 ETF 并买入纳指 ETF。
- 最大回撤仅 0.55%，发生在 2026-04-01 至 2026-04-02。
- 组合 Beta 为 0.301，说明软门槛没有破坏原策略低市场暴露特征。
- 日志 `ERROR=0`，云端编译、运行、交易、抓取链路完成。

## 结论

本次云端烟雾回测通过。软门槛在聚宽云端真实运行中输出连续 `TrendGate`，并且影响候选资格、TopK、最终仓位和实际成交。下一步若要判断参数优劣，应补充长周期 A/B：硬门槛基线 vs `TrendGateLower=-0.10, TrendGateUpper=0.00`。
