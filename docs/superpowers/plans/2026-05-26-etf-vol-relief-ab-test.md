# ETF Vol Relief A/B Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设计并执行 ETF 因子轮动策略的组合波控现金再利用云端 A/B 回测，比较当前基准、固定黄金弱缩放、动态低边际风险弱缩放三组结果。

**Architecture:** 策略端只增加可关闭的组合波控弱缩放模式，默认仍保持当前基准行为。云端 A/B 使用同一份代码和三组参数切换，完成后用审计日志和回测结果做深度归因。

**Tech Stack:** JoinQuant 云端回测、`scripts.tools.jq_automation` A/B 工具、Python `.venv`、`numpy` / `pandas`、现有 pytest 测试。

---

## Related Files

- Strategy: [etf_factor_rotation.py](../../../strategies/etf_factor_rotation/etf_factor_rotation.py) <!-- pathref: strategies/etf_factor_rotation/etf_factor_rotation.py -->
- Tests: [test_etf_factor_rotation.py](../../../strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) <!-- pathref: strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py -->
- A/B tool docs: [README.md](../../../scripts/tools/jq_automation/README.md) <!-- pathref: scripts/tools/jq_automation/README.md -->

## Design Decision

本次不继续本地网格扫描，只做 3 组云端完整回测：

1. `baseline_current`: 当前组合波控基准，重新云端跑一次。
2. `fixed_gold_f50_r2`: 当 `portfolio_vol / target_vol <= 2.0` 时，黄金恢复 50% 被组合波控压掉的仓位。
3. `dyn_marginal_f100_r1.5_mom`: 当 `portfolio_vol / target_vol <= 1.5` 时，在动量为正的持仓里选择边际风险最低资产，恢复 100% 被组合波控压掉的仓位。

正式策略默认值必须保持当前行为。候选逻辑只能通过参数打开，不能默认启用。

## Public Parameters

在 `set_parameter()` 增加这些默认参数，并纳入 `snapshot_params()` / `validate_params()`：

```python
g.PortfolioVolReliefMode = "baseline"
g.GoldVolReliefFraction = 0.5
g.GoldVolReliefMaxRatio = 2.0
g.DynamicVolReliefFraction = 1.0
g.DynamicVolReliefMaxRatio = 1.5
g.DynamicVolReliefMomentumWindow = 20
g.DynamicVolReliefCovWindow = 40
```

合法模式只允许：

```python
{"baseline", "fixed_gold", "dyn_marginal"}
```

校验规则：

- 所有 `Fraction` 必须在 `[0.0, 1.0]`。
- 所有 `MaxRatio` 必须大于 `1.0`。
- 动态窗口必须是正整数。
- 默认 `baseline` 路径必须和现有 `compute_portfolio_vol_scale()` 行为等价。

## Audit Fields

在 `rebalance_signals` 审计事件里补充：

```python
portfolio_vol_relief_mode
portfolio_vol_ratio
portfolio_vol_base_scale
portfolio_vol_asset_scales
portfolio_vol_relief_asset
portfolio_vol_relief_weight
portfolio_vol_relief_reason
```

字段含义：

- `portfolio_vol_ratio`: `portfolio_vol / TargetVol`，没有触发波控时为 `None` 或小于等于 `1.0` 的实际值。
- `portfolio_vol_base_scale`: 当前基准缩放系数。
- `portfolio_vol_asset_scales`: 每只 ETF 的最终组合波控缩放系数。
- `portfolio_vol_relief_asset`: 弱缩放恢复仓位的 ETF 代码；无恢复时为 `None`。
- `portfolio_vol_relief_weight`: 相对基准额外恢复的组合权重。
- `portfolio_vol_relief_reason`: `baseline`、`ratio_too_high`、`no_active_asset`、`negative_momentum`、`selected_low_marginal_risk` 等明确原因。

## Task 1: Add Parameters and Validation

**Files:**

- Modify: `strategies/etf_factor_rotation/etf_factor_rotation.py`
- Modify: `strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py`

- [ ] **Step 1: Add failing parameter snapshot tests**

Add tests asserting the new keys exist after `set_parameter()` and `snapshot_params()`:

```python
assert params["PortfolioVolReliefMode"] == "baseline"
assert params["GoldVolReliefFraction"] == 0.5
assert params["GoldVolReliefMaxRatio"] == 2.0
assert params["DynamicVolReliefFraction"] == 1.0
assert params["DynamicVolReliefMaxRatio"] == 1.5
assert params["DynamicVolReliefMomentumWindow"] == 20
assert params["DynamicVolReliefCovWindow"] == 40
```

- [ ] **Step 2: Add failing validation tests**

Add tests for invalid values:

```python
params["PortfolioVolReliefMode"] = "bad_mode"
with pytest.raises(ValueError, match="PortfolioVolReliefMode"):
    strategy.validate_params(params)

params = strategy.snapshot_params()
params["GoldVolReliefFraction"] = 1.5
with pytest.raises(ValueError, match="GoldVolReliefFraction"):
    strategy.validate_params(params)

params = strategy.snapshot_params()
params["DynamicVolReliefMomentumWindow"] = 0
with pytest.raises(ValueError, match="DynamicVolReliefMomentumWindow"):
    strategy.validate_params(params)
```

- [ ] **Step 3: Run targeted tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: fails because the new parameters are not implemented yet.

- [ ] **Step 4: Implement parameters and validation**

Add the parameters to `set_parameter()`, include them in `snapshot_params()`, and add explicit validation in `validate_params()`.

- [ ] **Step 5: Re-run targeted tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: parameter and validation tests pass.

- [ ] **Step 6: Commit**

```powershell
git add strategies\etf_factor_rotation\etf_factor_rotation.py strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py
git commit -m "增加组合波控弱缩放参数"
```

## Task 2: Refactor Portfolio Vol Scaling Without Changing Baseline

**Files:**

- Modify: `strategies/etf_factor_rotation/etf_factor_rotation.py`
- Modify: `strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py`

- [ ] **Step 1: Add failing baseline equivalence tests**

Add tests that compare the old scalar scale to the new per-asset scale behavior:

```python
base_scale = strategy.compute_portfolio_vol_scale(prices, pool, raw_weights, params)
asset_scales, meta = strategy.compute_portfolio_vol_asset_scales(prices, pool, raw_weights, params)

assert np.allclose(asset_scales, np.full(len(pool), base_scale))
assert meta["relief_asset"] is None
assert meta["relief_weight"] == 0.0
assert meta["reason"] == "baseline"
```

- [ ] **Step 2: Run targeted tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: fails because `compute_portfolio_vol_asset_scales()` does not exist yet.

- [ ] **Step 3: Implement base scale metadata helper**

Keep `compute_portfolio_vol_scale()` available for existing tests. Add a helper that computes base scale plus metadata:

```python
def compute_portfolio_vol_asset_scales(prices, pool, raw_weights, params):
    base_scale, vol_ratio = compute_portfolio_vol_scale_detail(prices, pool, raw_weights, params)
    asset_scales = np.full(len(pool), base_scale)
    meta = {
        "mode": params["PortfolioVolReliefMode"],
        "vol_ratio": vol_ratio,
        "base_scale": base_scale,
        "relief_asset": None,
        "relief_weight": 0.0,
        "reason": "baseline",
    }
    return asset_scales, meta
```

`compute_portfolio_vol_scale_detail()` should reuse the current covariance logic and return `(scale, vol_ratio)`. Existing `compute_portfolio_vol_scale()` should call it and return only `scale`.

- [ ] **Step 4: Wire final weight calculation to asset scales**

Replace:

```python
final_weights = raw_weights * portfolio_vol_scale
```

with:

```python
portfolio_vol_asset_scales, portfolio_vol_meta = compute_portfolio_vol_asset_scales(
    prices, pool, raw_weights, params
)
portfolio_vol_scale = portfolio_vol_meta["base_scale"]
final_weights = raw_weights * portfolio_vol_asset_scales
```

- [ ] **Step 5: Add audit fields**

Include the audit fields from the `Audit Fields` section in the existing `rebalance_signals` event.

- [ ] **Step 6: Re-run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: existing behavior remains green under `baseline`.

- [ ] **Step 7: Commit**

```powershell
git add strategies\etf_factor_rotation\etf_factor_rotation.py strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py
git commit -m "保持基准行为并扩展组合波控审计"
```

## Task 3: Implement fixed_gold_f50_r2

**Files:**

- Modify: `strategies/etf_factor_rotation/etf_factor_rotation.py`
- Modify: `strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py`

- [ ] **Step 1: Add failing fixed-gold tests**

Use pool order from the strategy: `["159819.XSHE", "513100.XSHG", "518880.XSHG"]`.

Expected behavior:

```python
params["PortfolioVolReliefMode"] = "fixed_gold"
params["GoldVolReliefFraction"] = 0.5
params["GoldVolReliefMaxRatio"] = 2.0

asset_scales, meta = strategy.compute_portfolio_vol_asset_scales(prices, pool, raw_weights, params)

assert asset_scales[0] == pytest.approx(base_scale)
assert asset_scales[1] == pytest.approx(base_scale)
assert asset_scales[2] == pytest.approx(base_scale + (1.0 - base_scale) * 0.5)
assert meta["relief_asset"] == "518880.XSHG"
assert meta["reason"] == "fixed_gold"
```

Add separate tests for:

- `vol_ratio > 2.0`: no relief, reason `ratio_too_high`。
- gold raw weight is zero: no relief, reason `gold_not_active`。

- [ ] **Step 2: Run targeted tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: fixed-gold tests fail because the mode is not implemented yet.

- [ ] **Step 3: Implement fixed-gold relief**

In `compute_portfolio_vol_asset_scales()`:

```python
if mode == "fixed_gold":
    gold_code = "518880.XSHG"
    if vol_ratio is None or vol_ratio <= 1.0:
        meta["reason"] = "vol_not_above_target"
        return asset_scales, meta
    if vol_ratio > params["GoldVolReliefMaxRatio"]:
        meta["reason"] = "ratio_too_high"
        return asset_scales, meta
    if gold_code not in pool:
        meta["reason"] = "gold_not_in_pool"
        return asset_scales, meta
    gold_idx = pool.index(gold_code)
    if raw_weights[gold_idx] <= 1e-8:
        meta["reason"] = "gold_not_active"
        return asset_scales, meta
    new_scale = min(1.0, base_scale + (1.0 - base_scale) * params["GoldVolReliefFraction"])
    asset_scales[gold_idx] = new_scale
    meta["relief_asset"] = gold_code
    meta["relief_weight"] = float(raw_weights[gold_idx] * (new_scale - base_scale))
    meta["reason"] = "fixed_gold"
```

- [ ] **Step 4: Re-run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: fixed-gold tests pass and baseline tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add strategies\etf_factor_rotation\etf_factor_rotation.py strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py
git commit -m "增加固定黄金组合波控弱缩放"
```

## Task 4: Implement dyn_marginal_f100_r1.5_mom

**Files:**

- Modify: `strategies/etf_factor_rotation/etf_factor_rotation.py`
- Modify: `strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py`

- [ ] **Step 1: Add failing dynamic marginal tests**

Create synthetic `close_ret` where one active asset has lower marginal risk contribution and positive 20-day momentum.

Expected behavior:

```python
params["PortfolioVolReliefMode"] = "dyn_marginal"
params["DynamicVolReliefFraction"] = 1.0
params["DynamicVolReliefMaxRatio"] = 1.5
params["DynamicVolReliefMomentumWindow"] = 20
params["DynamicVolReliefCovWindow"] = 40

asset_scales, meta = strategy.compute_portfolio_vol_asset_scales(prices, pool, raw_weights, params)

assert meta["relief_asset"] == expected_code
assert asset_scales[pool.index(expected_code)] == pytest.approx(1.0)
assert meta["reason"] == "selected_low_marginal_risk"
```

Add separate tests for:

- `vol_ratio > 1.5`: no relief, reason `ratio_too_high`。
- selected asset momentum below zero: no relief, reason `no_positive_momentum_asset`。
- fewer than `DynamicVolReliefCovWindow` return rows: no relief, reason `insufficient_cov_data`。

- [ ] **Step 2: Run targeted tests and confirm failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: dynamic tests fail because the mode is not implemented yet.

- [ ] **Step 3: Implement dynamic marginal relief**

Rules:

- Only active assets with `raw_weights[i] > 1e-8` can be selected.
- Use `prices["close_ret"]` only. This data is historical and already anchored before the rebalance trade date.
- Candidate momentum is compounded return over the last `DynamicVolReliefMomentumWindow` rows.
- Candidate must have momentum `>= 0.0`。
- Marginal risk score is `cov_annual[idx, :] @ active_weights` within active assets.
- Select the candidate with the lowest marginal risk score.
- Restore only the selected asset's own vol-scale cut.

Implementation shape:

```python
if mode == "dyn_marginal":
    if vol_ratio is None or vol_ratio <= 1.0:
        meta["reason"] = "vol_not_above_target"
        return asset_scales, meta
    if vol_ratio > params["DynamicVolReliefMaxRatio"]:
        meta["reason"] = "ratio_too_high"
        return asset_scales, meta

    selected_idx = select_dynamic_marginal_relief_asset(prices, pool, raw_weights, params)
    if selected_idx is None:
        meta["reason"] = "no_positive_momentum_asset"
        return asset_scales, meta

    new_scale = min(1.0, base_scale + (1.0 - base_scale) * params["DynamicVolReliefFraction"])
    asset_scales[selected_idx] = new_scale
    meta["relief_asset"] = pool[selected_idx]
    meta["relief_weight"] = float(raw_weights[selected_idx] * (new_scale - base_scale))
    meta["reason"] = "selected_low_marginal_risk"
```

- [ ] **Step 4: Re-run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py -q
```

Expected: dynamic tests pass and existing tests still pass.

- [ ] **Step 5: Commit**

```powershell
git add strategies\etf_factor_rotation\etf_factor_rotation.py strategies\etf_factor_rotation\tests\test_etf_factor_rotation.py
git commit -m "增加动态低边际风险组合波控弱缩放"
```

## Task 5: Create Cloud A/B Config

**Files:**

- Create: `strategies/etf_factor_rotation/test_batches/20260526-vol-relief-ab/abtests/portfolio-vol-relief-ab-v1.json`

- [ ] **Step 1: Read the latest valid baseline scenario**

Use the existing full baseline run settings as the source of truth:

```powershell
Get-ChildItem -Path research_datasets\etf_factor_rotation_backtest_runs -Directory | Sort-Object Name -Descending | Select-Object -First 10
```

Then inspect the matching scenario or dataset metadata for dates, initial cash, frequency, benchmark, and result source.

- [ ] **Step 2: Create the A/B config**

The config must contain three variants:

```json
{
  "experiment_id": "portfolio-vol-relief-ab-v1",
  "strategy": "etf_factor_rotation",
  "variants": [
    {
      "variant_id": "baseline_current",
      "params_diff": {
        "PortfolioVolReliefMode": "baseline"
      }
    },
    {
      "variant_id": "fixed_gold_f50_r2",
      "params_diff": {
        "PortfolioVolReliefMode": "fixed_gold",
        "GoldVolReliefFraction": 0.5,
        "GoldVolReliefMaxRatio": 2.0
      }
    },
    {
      "variant_id": "dyn_marginal_f100_r1.5_mom",
      "params_diff": {
        "PortfolioVolReliefMode": "dyn_marginal",
        "DynamicVolReliefFraction": 1.0,
        "DynamicVolReliefMaxRatio": 1.5,
        "DynamicVolReliefMomentumWindow": 20,
        "DynamicVolReliefCovWindow": 40
      }
    }
  ]
}
```

Use the exact schema currently accepted by `scripts.tools.jq_automation ab expand`; adjust only field names required by the tool, not the experiment design.

- [ ] **Step 3: Expand without running cloud backtests**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation ab expand strategies\etf_factor_rotation\test_batches\20260526-vol-relief-ab\abtests\portfolio-vol-relief-ab-v1.json
```

Expected: A/B materialization succeeds and produces local scenario files.

- [ ] **Step 4: Commit**

```powershell
git add strategies\etf_factor_rotation\test_batches\20260526-vol-relief-ab\abtests\portfolio-vol-relief-ab-v1.json
git commit -m "增加组合波控弱缩放云端AB配置"
```

## Task 6: Run Cloud A/B and Fetch Results

**Files:**

- Generated by A/B tool under the batch directory and research dataset registry.

- [ ] **Step 1: Run cloud A/B**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation ab run strategies\etf_factor_rotation\test_batches\20260526-vol-relief-ab\abtests\portfolio-vol-relief-ab-v1.json --yes --backtest-timeout 600
```

Expected: three variants complete successfully.

- [ ] **Step 2: Generate A/B report**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation ab report strategies\etf_factor_rotation\test_batches\20260526-vol-relief-ab\abtests\portfolio-vol-relief-ab-v1.json --experiment portfolio-vol-relief-ab-v1
```

Expected: comparison Markdown and summary JSON are produced under the A/B report directory.

- [ ] **Step 3: Verify audit completeness**

For each variant, confirm:

- `run_start` exists.
- `run_end` exists.
- `rebalance_signals` count matches the baseline run for the same date range.
- `seq` is monotonic.
- new `portfolio_vol_relief_*` fields exist in `rebalance_signals`。

- [ ] **Step 4: Commit fetched A/B metadata and reports**

```powershell
git add strategies\etf_factor_rotation\test_batches\20260526-vol-relief-ab
git commit -m "保存组合波控弱缩放云端AB结果"
```

## Task 7: Build Deep Attribution Report

**Files:**

- Create: `strategies/etf_factor_rotation/reports/research/portfolio_volatility/vol-relief-ab-v1/deep-attribution.md`
- Create: `strategies/etf_factor_rotation/reports/research/portfolio_volatility/vol-relief-ab-v1/summary.csv`

- [ ] **Step 1: Load A/B run artifacts**

Use each variant's fetched dataset:

- daily portfolio value.
- orders and trades if available.
- `audit_events.parquet` or equivalent audit event table.

- [ ] **Step 2: Produce summary metrics**

Report for each variant:

- total return.
- annual return.
- annual volatility.
- max drawdown.
- Sharpe.
- Calmar.
- average total position.
- average cash.
- turnover.
- fees.

- [ ] **Step 3: Attribute position changes**

For each variant, calculate:

- baseline portfolio-vol cash drag.
- restored weight from relief logic.
- average restored weight.
- trigger count.
- trigger count by year.
- selected asset distribution for `dyn_marginal_f100_r1.5_mom`。

- [ ] **Step 4: Attribute returns and drawdowns**

For each variant, calculate:

- annual return delta vs `baseline_current`。
- max drawdown delta vs `baseline_current`。
- ETF-level contribution for `159819.XSHE`, `513100.XSHG`, `518880.XSHG`。
- max drawdown window attribution.
- 2021-2023 discovery split and 2024-2026 validation split.

- [ ] **Step 5: Apply decision rules**

Candidate passes only if all are true:

- annual return improves by at least `0.5pp` vs `baseline_current`。
- max drawdown worsens by no more than `0.3pp`。
- Sharpe is not lower than `baseline_current`。
- Calmar is not lower than `baseline_current`。
- improvement is not concentrated in one year or fewer than five rebalance points.
- audit completeness passes.

- [ ] **Step 6: Commit deep attribution report**

```powershell
git add strategies\etf_factor_rotation\reports\research\portfolio_volatility\vol-relief-ab-v1
git commit -m "增加组合波控弱缩放AB深度归因"
```

## Final Verification

Run:

```powershell
.\.venv\Scripts\python.exe -m py_compile strategies\etf_factor_rotation\etf_factor_rotation.py
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests -q
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
git status --short
```

Expected:

- strategy compiles.
- strategy tests pass.
- pathref check passes.
- only intentional files are changed before final commit.

## Completion Criteria

Work is complete when:

- three cloud variants finished successfully.
- A/B comparison report exists.
- deep attribution report exists.
- audit completeness is verified.
- final conclusion explicitly says whether either candidate is worth promoting to strategy default.

If neither candidate passes the decision rules, keep default strategy unchanged and record the reason in the deep attribution report.
