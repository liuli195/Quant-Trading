# 回测报告 — ETF 动态调仓策略

## 回测概况

| 项目 | 内容 |
| --- | --- |
| 策略名称 | ETF 动态调仓策略 |
| 策略文件 | strategies/etf_dynamic_rebalance/etf_dynamic_rebalance.py |
| 回测区间 | 2023-01-01 至 2026-04-30 |
| 实际交易日 | 804 天 |
| 初始资金 | ￥500,000 |
| 最终市值 | ￥1,478,250 |
| 回测耗时 | 1 分 24 秒 |
| 回测链接 | https://www.joinquant.com/algorithm/backtest/detail?backtestId=b26d8c5b1ebb6f50300c02321aa68785 |

## 核心指标

| 指标 | 数值 |
| --- | --- |
| 策略总收益 | 195.65% |
| 策略年化收益 | 40.08% |
| 基准收益（沪深300） | 24.17% |
| 超额收益 | 138.11% |
| 最大回撤 | 16.40% |
| 最大回撤区间 | 2026/01/29 ~ 2026/03/23 |
| 夏普比率 | 2.438 |
| 索提诺比率 | 3.109 |
| Alpha | 0.347 |
| Beta | 0.457 |
| 信息比率 | 2.122 |
| 策略波动率 | 0.148 |
| 基准波动率 | 0.169 |
| 超额收益最大回撤 | 18.00% |
| 超额收益夏普比率 | 1.729 |
| 胜率（调仓） | 85.9% |
| 盈亏比 | 45.845 |
| 日胜率 | 58.0% |
| 盈利次数 / 亏损次数 | 183 / 30 |

## 交易统计

| 指标 | 数值 |
| --- | --- |
| 总成交笔数 | 436 |
| 买入笔数 | 223 |
| 卖出笔数 | 213 |
| 调仓天数 | 163 / 804（20.3%） |
| 覆盖月份 | 38 个月 |
| 标的 | 黄金 ETF(518880)、AI ETF(159819)、纳指100 ETF(513100) |

## 数据完整度

| 数据类型 | 完整度 | 提取方式 |
| --- | --- | --- |
| 交易详情 | 100%（436 条） | 内部 API |
| 每日持仓&收益 | 100%（1000 条） | 内部 API |
| 每日收益曲线 | 100% | 内部 API |
| 日志输出 | 部分 | DOM 提取 |
| 性能分析 | 100% | DOM 提取 |
| 各项指标 | 100% | DOM 提取 |

## 相关报告

- [策略分析](strategy-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_dynamic_rebalance, run_id=20260504_1)/strategy-analysis.md -->
- [性能分析](performance-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_dynamic_rebalance, run_id=20260504_1)/performance-analysis.md -->
- [归因分析](attribution-analysis.md) <!-- pathref: backtest_report_dir(strategy=etf_dynamic_rebalance, run_id=20260504_1)/attribution-analysis.md -->
