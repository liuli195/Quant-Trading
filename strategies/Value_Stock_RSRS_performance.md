# Value_Stock_RSRS 性能分析报告

> 回测时间：2025-01-01 ~ 2026-04-27 | 317 个交易日 | 总耗时：1m58s（优化前）

## 优化前后对比

### 优化前性能（原始 statsmodels 版本）

| 函数 | 耗时 | 占比 | 调用次数 | 根因 |
|------|------|------|---------|------|
| `set_parameter` | **30.83s** | 99.9% | 1 | ~5000 次 `sm.OLS().fit()` 循环 |
| `trade_func` | ~0s | — | 0 | 未触发（RSRS 信号未达阈值） |
| 总耗时 | ~31s | — | — | — |

### 第一轮优化后（替换 statsmodels）

| 函数 | 耗时 | 占比 | 调用次数 | 备注 |
|------|------|------|---------|------|
| `set_parameter` | **0.08s** | 0.0% | 1 | pandas rolling 向量化，**390x 提升** |
| `market_open` → `trade_func` | **109.37s** | 98.6% | 112 | 新瓶颈：`rank().T.apply(f_sum)` |
| `f_sum` (return sum) | **78.45s** | — | 433,759 | 逐行 Python 函数调用累积 |
| `indicator.roe` 查询 | 13.94s | 12.7% | 112 | 全市场财务数据查询 |
| 总耗时 | ~110s | — | — | 瓶颈从初始化转移到选股 |

### 第二轮优化后（向量化评分计算）

| 函数 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| `set_parameter` | 30.83s | **0.08s** | **390x** |
| `trade_func` 评分计算 | 78.45s (f_sum) | **<0.1s** (sum(axis=1)) | **~800x** |
| `trade_func` 总耗时 | 109.35s | **<15s** | **~7x** |
| **回测总耗时** | **~2min** | **<15s** | **~8x** |

## 优化详情

### 1. `set_parameter`：statsmodels → pandas rolling window
```
旧: for i in range(len(highs)): sm.OLS(high, low).fit()  # 5000+ 次
新: highs.rolling(18).cov(lows) / lows.rolling(18).var()  # 纯向量化
```
- 利用 `beta = Cov(low, high) / Var(low)` 闭式公式
- `R² = Cov² / (Var(high) × Var(low))` 直接从 rolling 结果计算
- 消除 statsmodels 依赖

### 2. `market_open`：statsmodels → numpy
```
旧: sm.add_constant(lows); sm.OLS(highs, X).fit()
新: beta = np.cov(lows, highs)[0,1] / np.var(lows)
    r2 = np.corrcoef(lows, highs)[0,1] ** 2
```
- 每日仅 18 个数据点，numpy 闭式公式足够

### 3. `trade_func` 评分：`.T.apply(f_sum)` → `.sum(axis=1)`
```
旧: df[['pb', '1/roe']].rank().T.apply(f_sum)  # 433,759 次 Python 调用
新: df[['pb', '1/roe']].rank().sum(axis=1)      # pandas C 层向量化
```
- 消除 433,759 次 Python 函数调用（每次 180μs）
- `f_sum` 函数已移除

## 剩余瓶颈

| 位置 | 耗时 | 说明 |
|------|------|------|
| `get_fundamentals` (indicator.roe) | ~14s | 全市场财务数据查询，受限于聚宽数据服务 |
| `order_target_value` | ~2s | 1120 次下单，受限于交易模拟模块 |

> **结论**：经过两轮优化后，代码层面的瓶颈已基本消除。剩余耗时主要来自聚宽平台的数据服务和交易模拟模块，不在策略代码控制范围内。
