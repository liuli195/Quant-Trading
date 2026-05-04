# 风险序列明细

本文件补充聚宽回测详情页左侧“策略收益”到“最大回撤”的 10 个标签数据。数据来源为详情页只读接口 `/algorithm/backtest/risk`，未使用扣积分导出。

| 标签 | JSON 键 | 记录数 | 起始月份 | 截止月份 | CSV |
| --- | --- | ---: | --- | --- | --- |
| 策略收益 | algorithmPeriodReturn | 40 | 2023-01 | 2026-04 | raw/risk_algorithm_period_return.csv |
| 基准收益 | benchmarkPeriodReturn | 40 | 2023-01 | 2026-04 | raw/risk_benchmark_period_return.csv |
| 阿尔法 | alpha | 40 | 2023-01 | 2026-04 | raw/risk_alpha.csv |
| 贝塔 | beta | 40 | 2023-01 | 2026-04 | raw/risk_beta.csv |
| 夏普比率 | sharp | 40 | 2023-01 | 2026-04 | raw/risk_sharpe.csv |
| 索提诺比率 | sortino | 40 | 2023-01 | 2026-04 | raw/risk_sortino.csv |
| 信息比率 | information | 40 | 2023-01 | 2026-04 | raw/risk_information.csv |
| 波动率 | algovolatility | 40 | 2023-01 | 2026-04 | raw/risk_algo_volatility.csv |
| 基准波动率 | benchmarkvolatility | 40 | 2023-01 | 2026-04 | raw/risk_benchmark_volatility.csv |
| 最大回撤 | maxdrawdown | 40 | 2023-01 | 2026-04 | raw/risk_max_drawdown.csv |

## 合并文件

- raw/risk_series_combined.csv：10 个标签纵向合并，字段为 `label,key,date,1month,3month,6month,12month`。
- raw/risk_series_index.json：标签、JSON 键与分表文件的索引。

## 说明

每个序列按月份给出 1个月、3个月、6个月、12个月窗口指标；窗口不足时为 `N/A`。
