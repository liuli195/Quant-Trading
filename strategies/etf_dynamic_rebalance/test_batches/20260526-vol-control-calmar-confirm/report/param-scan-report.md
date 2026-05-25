# ETF 动态调仓波动率控制参数扫描报告

- 批次：`20260526-vol-control-calmar-confirm` / `s01-local-shortlist`
- 云端确认：5 组参数，完成 5 组；完整性：`complete`。
- 本地 shortlist：[local-calmar-shortlist.md](../../../reports/research/portfolio_volatility/reports/local-calmar-shortlist.md) <!-- pathref: strategies/etf_dynamic_rebalance/reports/research/portfolio_volatility/reports/local-calmar-shortlist.md -->
- 云端 run 根目录：[backtest_runs](../../../backtest_runs) <!-- pathref: strategies/etf_dynamic_rebalance/backtest_runs -->

## 结论

云端 Calmar 最优为 `local-01-w40-tv0296684`，参数 `portfolio_vol_window=40`、`target_vol=0.296684328514`，Calmar `1.302`。本地 Calmar 第一名为 `global-w40-t0.296684328514`；本地与云端第一名一致。

默认参数 `window=40 / target_vol=0.08` 的云端 Calmar 为 `1.294`。云端冠军相对默认：Calmar `+0.009`，年化 `+5.94%`，最大回撤绝对值 `+4.48%`，波动率 `+4.30%`。

判断：不建议现在改默认参数。候选参数年化更高，但几乎满仓，回撤和波动率也明显高于默认；按本轮云端汇总精度，Calmar 优势很小，证据不足以直接推广为默认。

## 云端 Calmar 排名

| 排名 | label | run_id | window | target_vol | 年化 | 最大回撤 | Calmar | Sharpe | 波动率 | integrity | audit |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| 1 | `local-01-w40-tv0296684` | `20260526-0214-bt24c9d8b410c21d7da6229fe0d3c94901` | 40 | 0.296684328514 | 21.40% | 16.43% | 1.302 | 1.297 | 13.40% | complete | 3120 |
| 2 | `local-03-w40-tv0296639` | `20260526-0221-bt3259066658e5135eb443ce3f05689b72` | 40 | 0.296639288611 | 21.40% | 16.43% | 1.302 | 1.297 | 13.40% | complete | 3120 |
| 3 | `local-02-w40-tv0296662` | `20260526-0217-bt649414737cca9f694bc92e09c5cdd140` | 40 | 0.296661808562 | 21.39% | 16.43% | 1.302 | 1.297 | 13.40% | complete | 3120 |
| 4 | `local-04-w40-tv0296851` | `20260526-0225-bt8a0c34a15f9adffd8446ae39d2e7ee7e` | 40 | 0.296851013760 | 21.39% | 16.44% | 1.301 | 1.297 | 13.40% | complete | 3120 |
| 5 | `default-w40-tv008` | `20260526-0229-btee809d4cea8f278df764d8dd0c195e5f` | 40 | 0.080000000000 | 15.46% | 11.95% | 1.294 | 1.261 | 9.10% | complete | 3006 |

## 本地与云端对照

| 云端 label | 本地 label | 本地 Calmar | 云端 Calmar | 本地年化 | 云端年化 | 本地最大回撤 | 云端最大回撤 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `local-01-w40-tv0296684` | `global-w40-t0.296684328514` | 1.270 | 1.302 | 22.13% | 21.40% | 17.42% | 16.43% |
| `local-02-w40-tv0296662` | `global-w40-t0.296661808562` | 1.270 | 1.302 | 22.13% | 21.39% | 17.42% | 16.43% |
| `local-03-w40-tv0296639` | `global-w40-t0.296639288611` | 1.270 | 1.302 | 22.13% | 21.40% | 17.42% | 16.43% |
| `local-04-w40-tv0296851` | `global-w40-t0.296851013760` | 1.270 | 1.301 | 22.13% | 21.39% | 17.42% | 16.44% |
| `default-w40-tv008` |  |  | 1.294 |  | 15.46% |  | 11.95% |

## 数据说明

- 指标来自每个云端 run 的 `summary_metrics.json`；Calmar 按 `策略年化收益 / abs(最大回撤)` 计算。
- 5 个云端 run 的 `integrity.json` 均为 `complete`，`audit_log.jsonl` 均存在。
- 本轮只做参数确认，没有改动策略默认参数。
