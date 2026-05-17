# 稳健性验证：linear-035

- **对比**: `20260517-1724-bt580e16e5a3f1bf99d197cea88889da1a` -> `20260517-1731-btbe2e525c63caec09d9355836a69f8676`
- **方法**: 配对 block bootstrap + 滚动 `252` 日 Sharpe + 年度分解 + ETF 贡献拆解

## 总体指标

| 方案 | 年化 | Sharpe | 最大回撤 |
| --- | --- | --- | --- |
| baseline | 15.76% | 1.447 | 8.09% |
| linear-035 | 15.85% | 1.459 | 8.09% |

## 配对 Bootstrap

| variant-baseline 日均差(bp) | CI95低(bp) | CI95高(bp) | p-value |
| --- | --- | --- | --- |
| 0.032 | -0.083 | 0.169 | 0.3028 |

- **滚动 Sharpe 胜率**: `45.8%`
- **年度 Sharpe 改善**: `4/6`
- **单一 ETF 最大解释占比**: `65.5%`

## 年度分解

| year | sharpe_baseline | sharpe_variant | annual_return_baseline | annual_return_variant | max_drawdown_baseline | max_drawdown_variant |
| --- | --- | --- | --- | --- | --- | --- |
| 2021 | 0.382 | 0.379 | 2.62% | 2.60% | 4.15% | 4.12% |
| 2022 | -0.152 | -0.151 | 1.42% | 1.42% | 5.39% | 5.39% |
| 2023 | 2.232 | 2.195 | 18.16% | 17.78% | 6.08% | 6.33% |
| 2024 | 2.340 | 2.386 | 22.48% | 23.02% | 4.29% | 4.50% |
| 2025 | 4.151 | 4.183 | 44.19% | 44.42% | 3.21% | 3.19% |
| 2026 | 1.416 | 1.471 | 12.25% | 12.83% | 5.21% | 5.27% |

## ETF 贡献拆解

| ETF | 贡献(bp近似) | leave-one-out Sharpe差 |
| --- | --- | --- |
| AI | -14.6 | 0.0131 |
| NASDAQ | -7.1 | 0.0055 |
| GOLD | 57.5 | -0.0003 |

## 决策门槛

| 门槛 | 结果 |
| --- | --- |
| sharpe_higher | True |
| annual_within_threshold | True |
| drawdown_within_threshold | True |
| rolling_win_rate_pass | False |
| years_better_pass | True |
| dominant_share_pass | True |
| leave_one_pass | False |
| all_passed | False |
