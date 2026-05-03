# ETF 动态调仓策略 性能分析报告

> 回测时间：2026-04-01 ~ 2026-04-30 | 总耗时：4 秒（实际回测）| 代码执行时间：~0.67s

## 函数级耗时总览

| 函数 | 总耗时 | 占比 | 调用次数 | 核心瓶颈 |
|------|--------|------|----------|----------|
| `weekly_rebalance` | 401.2ms | 59.7% | 5 | 因子计算 + jqlib 指标调用 |
| `compute_nasdaq_factors` | 108.1ms | 16.1% | 5 | ROC(3次) + BIAS + 波动率循环 |
| `compute_gold_factors` | 86.2ms | 12.8% | 5 | BIAS + ROC(3次) |
| `compute_ai_factors` | 65.6ms | 9.8% | 5 | BIAS + ROC + 波动率循环 |
| `zscore_clip` | 4.1ms | 0.6% | 45 | np.std (53.9%) |
| `initialize` | 2.1ms | 0.3% | 1 | reference_security 查询 (83.2%) |
| `compute_target_weights` | 0.2ms | <0.1% | 5 | — |
| `apply_weight_constraints` | 0.3ms | <0.1% | 5 | — |
| `set_parameter` | ~0ms | <0.1% | 1 | — |

## 瓶颈详细分析

### 1. jqlib 内置指标调用（最大瓶颈，~55% 占比）

三个因子计算函数中，`BIAS` 和 `ROC` 调用是最昂贵的单操作：

| 调用 | 次数/调仓 | 单次耗时 | 每月总耗时 |
|------|-----------|----------|-----------|
| `BIAS(518880, 20)` | 1 | 5.1ms | 25.4ms |
| `BIAS(159819, 20)` | 1 | 4.4ms | 22.2ms |
| `BIAS(513100, 20)` | 3 | 4.5ms | 67.6ms（重复调用） |
| `ROC(518880, 20)` | 2 | 3.9~4.0ms | 39.5ms |
| `ROC(513100, 20/60)` | 4 | 3.9~4.5ms | 80.7ms |
| `ROC(159819, 20)` | 1 | 3.8ms | 19.2ms |

**关键问题：513100.XSHG（纳指）的 BIAS 被重复调用了 3 次**（compute_gold_factors 中的 RS 和 RiskOff，以及 compute_nasdaq_factors 中的 Trend），ROC 被重复调用 4 次。合并去重可节省 ~60ms。

### 2. 波动率循环计算（~15% 占比）

`compute_ai_factors` 和 `compute_nasdaq_factors` 中各有一段 Python 循环计算滚动波动率：

```python
short_vols = np.array([
    np.std(log_returns[i:i+short_w], ddof=1)
    for i in range(len(log_returns) - short_w + 1)
])
```

每个 ETF 每个调仓日执行 2 个循环（short+long），共 40 个 np.std 调用，耗时约 20ms。可改用 `pd.Series.rolling().std()` 向量化单次完成。

### 3. get_price 单独调用（~14% 占比）

每月 3 ETF × 5 周 = 15 次 `get_price` 调用，每次 3.7ms，合计 55.4ms。原代码设计为 1 次批量调用但因 MultiIndex 解析问题改为单独调用。修复后可将 15 次合并为 1 次。

## 潜在优化方案

| 方案 | 预期节省 | 实施难度 |
|------|----------|----------|
| P0: BIAS/ROC 去重缓存 | ~60ms（-9%） | 低 |
| P1: 批量 get_price 修复 | ~50ms（-7%） | 中 |
| P2: 波动率向量化 | ~15ms（-2%） | 低 |
| P3: 代码总耗时优化后 | ~0.55s（-18%） | — |

**注意**：策略总执行时间仅 0.67s，在当前 4 周回测中性能已很好。以上优化在更长回测周期或更高频调仓时价值更大。
