# ETF 动态调仓本地 Calmar 候选清单

- 来源 full run：`2026-05-26-full-calmar`。
- 选择规则：本地 Calmar 前 4，加当前默认附近的 `window=40`、`target=0.08`。
- 本地 replay 只用于候选筛选，不代表云端最终确认。

| role | label | window | target | avg_position | annual_return | max_drawdown | calmar | sharpe | volatility |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| local_calmar_top4 | global-w40-t0.296684328514 | 40 | 0.296684 | 100.00% | 22.13% | -17.42% | 1.270469 | 1.483501 | 14.16% |
| local_calmar_top4 | global-w40-t0.296661808562 | 40 | 0.296662 | 100.00% | 22.13% | -17.42% | 1.270468 | 1.483501 | 14.16% |
| local_calmar_top4 | global-w40-t0.296639288611 | 40 | 0.296639 | 100.00% | 22.13% | -17.42% | 1.270467 | 1.483501 | 14.16% |
| local_calmar_top4 | global-w40-t0.296851013760 | 40 | 0.296851 | 100.00% | 22.13% | -17.42% | 1.270462 | 1.483492 | 14.16% |
| current_default_nearest | default-w40-tv008 | 40 | 0.079968 | 70.69% | 15.24% | -13.30% | 1.145748 | 1.568868 | 9.32% |

## 云端确认参数

- `global-w40-t0.296684328514`: `portfolio_vol_window=40`, `target_vol=0.296684328514`
- `global-w40-t0.296661808562`: `portfolio_vol_window=40`, `target_vol=0.296661808562`
- `global-w40-t0.296639288611`: `portfolio_vol_window=40`, `target_vol=0.296639288611`
- `global-w40-t0.296851013760`: `portfolio_vol_window=40`, `target_vol=0.296851013760`
- `default-w40-tv008`: `portfolio_vol_window=40`, `target_vol=0.079967537322`
