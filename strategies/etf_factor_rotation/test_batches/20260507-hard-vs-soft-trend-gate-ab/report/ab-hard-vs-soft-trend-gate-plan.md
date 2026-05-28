# Hard vs Soft Trend Gate AB Plan

## Purpose

Compare whether the ETF factor rotation strategy benefits from replacing the main branch hard 120-day moving-average gate with the current workspace branch linear soft gate.

## Governance Status

This historical batch is archived as `archived_partial`, not as promotion evidence. The imported data-center snapshots are missing `tabs_raw/audit_log.jsonl`, and the soft-gate source commit is not reachable from origin refs. Treat this plan as historical context only; rerun the experiment under the current PR/data-center rules before using the result for merge, promotion, or parameter scanning.

## Artifacts

- AB config: [hard-vs-soft-trend-gate.json](../abtests/hard-vs-soft-trend-gate.json) <!-- pathref: strategies/etf_factor_rotation/test_batches/20260507-hard-vs-soft-trend-gate-ab/abtests/hard-vs-soft-trend-gate.json -->
- Batch manifest: [manifest.json](../manifest.json) <!-- pathref: strategies/etf_factor_rotation/test_batches/20260507-hard-vs-soft-trend-gate-ab/manifest.json -->
- Generated comparison report after run: `report/ab-hard-vs-soft-trend-gate-comparison.md`

## Design

| Variant | Role | Git ref | Gate logic | Params mode |
|---|---|---|---|---|
| `hard_gate_main` | Baseline/control | `main` | `current_close > MA120` gives 1.0, otherwise 0.0 | `baked_in_git` |
| `soft_gate_workspace` | Variant | `默认工作区` | `close / MA120 - 1` maps linearly from `-0.10` to `0.00` into `[0, 1]` | `baked_in_git` |

All other strategy parameters remain baked into each Git source. The current diff shows common defaults for `TopK=3`, `TargetVol=0.08`, `use_real_price=False`, and `fq_mode=None`.

## Backtest Window

- Period: `2021-01-01` to `2026-04-30`
- Capital: `100000`
- Frequency: `1d`
- Result source: `research`

This window is longer than 252 trading days and covers several ETF market regimes while keeping the quota estimate manageable.

## Decision Criteria

Prefer the soft gate only if it improves risk-adjusted performance without materially increasing drawdown or volatility:

| Metric | Direction | Primary use |
|---|---|---|
| `annual_return` | Maximize | Return efficiency |
| `excess_return` | Maximize | Benchmark-relative value |
| `max_drawdown` | Minimize | Tail risk |
| `sharpe` | Maximize | Risk-adjusted return |
| `volatility` | Minimize | Smoothness |
| `win_ratio` | Maximize | Trade-level consistency |
| `profit_loss_ratio` | Maximize | Payoff quality |
| `actual_minutes` | Minimize | Runtime sanity check |

## Quota Check

Estimated runtime is `8` minutes per variant, `16` minutes total. The local quota ledger for `2026-05-07` showed about `21.159` minutes remaining before this experiment was created, so the planned runtime is within the 80% guardrail. The actual cloud page quota is still checked by `ab run` before starting each variant.

## Run Commands

```powershell
.\.venv\Scripts\python.exe -m scripts.jq_automation ab expand strategies\etf_factor_rotation\test_batches\20260507-hard-vs-soft-trend-gate-ab\abtests\hard-vs-soft-trend-gate.json
.\.venv\Scripts\python.exe -m scripts.jq_automation ab run strategies\etf_factor_rotation\test_batches\20260507-hard-vs-soft-trend-gate-ab\abtests\hard-vs-soft-trend-gate.json --yes --backtest-timeout 180 --result-source research
.\.venv\Scripts\python.exe -m scripts.jq_automation ab report strategies\etf_factor_rotation\test_batches\20260507-hard-vs-soft-trend-gate-ab\abtests\hard-vs-soft-trend-gate.json --experiment hard-vs-soft-trend-gate
```

Do not run the cloud backtests until the user explicitly confirms quota use.
