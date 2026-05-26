# 组合波控弱缩放 A/B 深度归因

## 结论

- `fixed_gold_f50_r2`：通过。年化收益相对 baseline 为 0.51%，最大回撤变化 -0.19%，Sharpe 变化 0.017，触发 127 次。
- `dyn_marginal_f100_r1.5_mom`：通过。年化收益相对 baseline 为 0.90%，最大回撤变化 -0.39%，Sharpe 变化 0.084，触发 91 次。

按本计划规则，`dyn_marginal_f100_r1.5_mom` 值得进入下一步默认候选评审；本次不直接改默认参数，策略默认仍保持 `PortfolioVolReliefMode="baseline"`。

## 输入

- A/B 配置：[portfolio-vol-relief-ab-v1.json](../../../../test_batches/20260526-vol-relief-ab/abtests/portfolio-vol-relief-ab-v1.json) <!-- pathref: strategies/etf_factor_rotation/test_batches/20260526-vol-relief-ab/abtests/portfolio-vol-relief-ab-v1.json -->
- A/B 比较：[ab-portfolio-vol-relief-ab-v1-comparison.md](../../../../test_batches/20260526-vol-relief-ab/report/ab-portfolio-vol-relief-ab-v1-comparison.md) <!-- pathref: strategies/etf_factor_rotation/test_batches/20260526-vol-relief-ab/report/ab-portfolio-vol-relief-ab-v1-comparison.md -->
- 指标表：[summary.csv](summary.csv) <!-- pathref: strategies/etf_factor_rotation/reports/research/portfolio_volatility/vol-relief-ab-v1/summary.csv -->
- `baseline_current` run: [20260526-2327-bta35e64a2599b009eba3c6b8219d61e22](../../../../backtest_runs/20260526-2327-bta35e64a2599b009eba3c6b8219d61e22/report/backtest_report.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260526-2327-bta35e64a2599b009eba3c6b8219d61e22)/backtest_report.md -->
- `fixed_gold_f50_r2` run: [20260526-2330-btfefcb2db54c231df54d773457629bda1](../../../../backtest_runs/20260526-2330-btfefcb2db54c231df54d773457629bda1/report/backtest_report.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260526-2330-btfefcb2db54c231df54d773457629bda1)/backtest_report.md -->
- `dyn_marginal_f100_r1.5_mom` run: [20260526-2333-bt36f34fb52505979aa53d97ef4949fc60](../../../../backtest_runs/20260526-2333-bt36f34fb52505979aa53d97ef4949fc60/report/backtest_report.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260526-2333-bt36f34fb52505979aa53d97ef4949fc60)/backtest_report.md -->

## 核心指标

| 组别 | 总收益 | 年化 | 年化差值 | 波动率 | 最大回撤 | 回撤差值 | Sharpe | Calmar | 平均仓位 | 平均现金 | 年化换手 | 费用 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_current` | 118.32% | 16.35% | 0.00% | 8.20% | 7.99% | 0.00% | 1.498 | 2.046 | 58.11% | 55,547.69 | 1030.29% | 684.06 |
| `fixed_gold_f50_r2` | 123.34% | 16.86% | 0.51% | 8.50% | 7.80% | -0.19% | 1.515 | 2.162 | 60.08% | 53,464.66 | 1017.28% | 683.13 |
| `dyn_marginal_f100_r1.5_mom` | 127.12% | 17.25% | 0.90% | 8.40% | 7.60% | -0.39% | 1.582 | 2.270 | 59.49% | 54,721.92 | 1035.13% | 698.50 |

## 现金再利用

| 组别 | 平均组合波控现金拖累 | 平均恢复权重 | 触发次数 | 触发年份 | 选择资产分布 | 原因分布 |
|---|---:|---:|---:|---|---|---|
| `baseline_current` | 24.48% | 0.00% | 0 | {} | {} | {"baseline": 272} |
| `fixed_gold_f50_r2` | 24.48% | 3.69% | 127 | {"2021": 13, "2022": 23, "2023": 25, "2024": 38, "2025": 25, "2026": 3} | {"518880.XSHG": 127} | {"fixed_gold": 127, "gold_not_active": 23, "ratio_too_high": 49, "vol_not_above_target": 73} |
| `dyn_marginal_f100_r1.5_mom` | 24.48% | 2.91% | 91 | {"2021": 16, "2022": 14, "2023": 24, "2024": 20, "2025": 16, "2026": 1} | {"159819.XSHE": 6, "513100.XSHG": 25, "518880.XSHG": 60} | {"no_positive_momentum_asset": 4, "ratio_too_high": 104, "selected_low_marginal_risk": 91, "vol_not_above_target": 73} |

## 年度和样本切分

| 组别 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | 2021-2023 年化 | 2024-2026 年化 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `baseline_current` | 2.30% | -1.40% | 18.14% | 22.46% | 43.71% | 4.10% | 6.27% | 31.19% |
| `fixed_gold_f50_r2` | 1.93% | -0.61% | 18.46% | 23.39% | 44.70% | 4.23% | 6.53% | 32.11% |
| `dyn_marginal_f100_r1.5_mom` | 2.09% | -0.85% | 18.57% | 24.24% | 46.06% | 4.28% | 6.53% | 33.11% |

相对 baseline 的年度收益差值：

| 组别 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 | 正贡献年份数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fixed_gold_f50_r2` | -0.37% | 0.79% | 0.32% | 0.93% | 0.99% | 0.13% | 5 |
| `dyn_marginal_f100_r1.5_mom` | -0.21% | 0.55% | 0.43% | 1.78% | 2.34% | 0.18% | 5 |

## ETF 贡献

| 组别 | 人工智能ETF易方达 | 纳指ETF | 黄金ETF |
|---|---:|---:|---:|
| `baseline_current` | 22.42% | 32.12% | 56.54% |
| `fixed_gold_f50_r2` | 23.17% | 32.01% | 60.18% |
| `dyn_marginal_f100_r1.5_mom` | 24.06% | 34.28% | 61.03% |

相对 baseline 的 ETF 贡献差值：

| 组别 | 人工智能ETF易方达 | 纳指ETF | 黄金ETF |
|---|---:|---:|---:|
| `fixed_gold_f50_r2` | 0.74% | -0.11% | 3.64% |
| `dyn_marginal_f100_r1.5_mom` | 1.64% | 2.16% | 4.49% |

## 最大回撤窗口

| 组别 | 回撤区间 | 最大回撤 | 人工智能ETF易方达区间盈亏 | 纳指ETF区间盈亏 | 黄金ETF区间盈亏 |
|---|---|---:|---:|---:|---:|
| `baseline_current` | 2021-11-22 至 2022-01-28 | 7.99% | -3,334.50 | -2,063.80 | -1,969.10 |
| `fixed_gold_f50_r2` | 2021-11-22 至 2022-01-28 | 7.80% | -3,029.60 | -2,055.10 | -2,078.90 |
| `dyn_marginal_f100_r1.5_mom` | 2021-11-22 至 2022-01-28 | 7.60% | -2,728.80 | -2,059.20 | -2,197.20 |

## 审计完整性

| 组别 | run_start | run_end | rebalance_signals | seq 单调唯一 | 新字段缺失 |
|---|---:|---:|---:|---|---|
| `baseline_current` | 1 | 1 | 272 | 是 | 无 |
| `fixed_gold_f50_r2` | 1 | 1 | 272 | 是 | 无 |
| `dyn_marginal_f100_r1.5_mom` | 1 | 1 | 272 | 是 | 无 |

说明：`audit_events.parquet` 的结构是 `payload_json` 承载完整事件，新增 `portfolio_vol_relief_*` 字段在该 payload 中验证。

## 决策规则

| 组别 | 年化 +0.5pp | 回撤恶化 <=0.3pp | Sharpe 不降 | Calmar 不降 | 不集中且触发>=5 | 审计完整 | 结论 |
|---|---|---|---|---|---|---|---|
| `fixed_gold_f50_r2` | 是 | 是 | 是 | 是 | 是 | 是 | 通过 |
| `dyn_marginal_f100_r1.5_mom` | 是 | 是 | 是 | 是 | 是 | 是 | 通过 |

## 默认参数处理

本次代码只新增可开关参数和 A/B 候选逻辑；正式默认仍为 `PortfolioVolReliefMode = "baseline"`。候选若要升级为默认，还需要单独的默认参数变更 PR/提交。
