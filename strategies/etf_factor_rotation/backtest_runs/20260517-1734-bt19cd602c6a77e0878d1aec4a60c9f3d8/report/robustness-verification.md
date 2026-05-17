# 稳健性验证：linear-025

- **对比**: `20260517-1724-bt580e16e5a3f1bf99d197cea88889da1a` -> `20260517-1734-bt19cd602c6a77e0878d1aec4a60c9f3d8`
- **方法**: 配对 block bootstrap + 滚动 `252` 日 Sharpe + 年度分解 + ETF 贡献拆解

## 总体指标

| 方案 | 年化 | Sharpe | 最大回撤 |
| --- | --- | --- | --- |
| baseline | 15.76% | 1.447 | 8.09% |
| linear-025 | 15.91% | 1.469 | 8.09% |

## 配对 Bootstrap

| variant-baseline 日均差(bp) | CI95低(bp) | CI95高(bp) | p-value |
| --- | --- | --- | --- |
| 0.054 | -0.089 | 0.22 | 0.2344 |

- **滚动 Sharpe 胜率**: `45.5%`
- **年度 Sharpe 改善**: `3/6`
- **单一 ETF 最大解释占比**: `63.6%`

## 年度分解

| year | sharpe_baseline | sharpe_variant | annual_return_baseline | annual_return_variant | max_drawdown_baseline | max_drawdown_variant |
| --- | --- | --- | --- | --- | --- | --- |
| 2021 | 0.382 | 0.380 | 2.62% | 2.60% | 4.15% | 4.09% |
| 2022 | -0.152 | -0.152 | 1.42% | 1.43% | 5.39% | 5.39% |
| 2023 | 2.232 | 2.199 | 18.16% | 17.76% | 6.08% | 6.39% |
| 2024 | 2.340 | 2.408 | 22.48% | 23.23% | 4.29% | 4.50% |
| 2025 | 4.151 | 4.203 | 44.19% | 44.55% | 3.21% | 3.17% |
| 2026 | 1.416 | 1.502 | 12.25% | 13.07% | 5.21% | 5.24% |

## ETF 贡献拆解

| ETF | 贡献(bp近似) | leave-one-out Sharpe差 |
| --- | --- | --- |
| AI | -16.9 | 0.023 |
| NASDAQ | -13.5 | 0.0121 |
| GOLD | 94.9 | 0.0024 |

## 决策门槛

| 门槛 | 结果 |
| --- | --- |
| sharpe_higher | True |
| annual_within_threshold | True |
| drawdown_within_threshold | True |
| rolling_win_rate_pass | False |
| years_better_pass | False |
| dominant_share_pass | True |
| leave_one_pass | True |
| all_passed | False |
