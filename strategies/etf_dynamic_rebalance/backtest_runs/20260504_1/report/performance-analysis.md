# 性能分析报告 — ETF 动态调仓策略

## 1. 性能分析概览

- 策略名称：ETF 动态调仓策略
- 是否启用 `enable_profile()`：是
- 数据来源：聚宽 `#tab-profile` DOM 提取
- 回测链接：https://www.joinquant.com/algorithm/backtest/detail?backtestId=b26d8c5b1ebb6f50300c02321aa68785

## 2. 主要耗时函数

| 函数名 | 调用次数 | 总耗时 (s) | 单次耗时 (ms) | 占总耗时比例 | 主要瓶颈 |
| --- | --- | --- | --- | --- | --- |
| `daily_check`（整体） | 804 | 56.836 | 70.7 | 100% | 因子计算 + API 调用 |
| `compute_nasdaq_factors` | 804 | 17.434 | 21.7 | 30.7% | BIAS/ROC 逐次 API 调用 |
| `compute_gold_factors` | 804 | 13.553 | 16.9 | 23.8% | BIAS/ROC 逐次 API 调用 |
| `compute_ai_factors` | 804 | 10.864 | 13.5 | 19.1% | BIAS/ROC + 波动率滚动计算 |
| `get_price`（3 ETF × 804 天） | 2,412 | 8.030 | 3.3 | 14.1% | fq=None 无复权模式耗时 |
| `order_target_value` | 489 | 1.448 | 3.0 | 2.5% | 下单执行 |
| `pd.DataFrame` 构建 + `dropna` | 804 | 2.311 | 2.9 | 4.1% | DataFrame 构造开销 |
| `initialize` | 1 | 0.002 | 2.4 | 0.0% | 可忽略 |
| `set_parameter` | 1 | ~0 | ~0 | 0.0% | 可忽略 |

## 3. 热点路径解读

### 最耗时函数：因子计算链（占 73.6%）

三个 `compute_*_factors` 函数合计耗时 41.85s，占 `daily_check` 总耗时的 73.6%。每条因子计算路径依次调用：

1. **BIAS / ROC API**（聚宽技术指标库）：每次调用都是独立的网络/数据库查询
2. **numpy 滚动统计**：zscore 标准化、vol_ratios 向量化计算
3. **线性组合**：加权求和得到最终因子得分

### 根本原因：逐 ETF 逐函数的 API 调用

每个交易日的因子计算路径：

```
daily_check (804次)
├── get_price × 3           → 8.0s (3次独立查询)
├── compute_gold_factors    → 13.6s
│   ├── BIAS(gold)          → 独立API调用
│   ├── ROC(gold)           → 独立API调用
│   └── ROC(nasdaq)         → 独立API调用（跨资产引用）
├── compute_ai_factors      → 10.9s
│   ├── ROC(ai)             → 独立API调用
│   ├── BIAS(ai)            → 独立API调用
│   └── 波动率滚动计算       → Python循环
├── compute_nasdaq_factors  → 17.4s
│   ├── ROC(nasdaq)         → 独立API调用
│   ├── BIAS(nasdaq)        → 独立API调用
│   ├── ROC(gold)           → 独立API调用（重复！）
│   └── 波动率滚动计算       → Python循环
└── order_target_value × 3  → 1.4s
```

**注意**：`compute_gold_factors` 和 `compute_nasdaq_factors` 重复调用了 `ROC(gold)` 和 `ROC(nasdaq)`，存在重复计算。

### get_price 开销分析

每天 3 次 `get_price()` 调用合计 8.0s（占总耗时 14.1%）。`fq=None`（不复权）模式下单次约 3.3ms，对于 100 天的历史数据量来说效率尚可。瓶颈在于调用次数（804 × 3 = 2412 次）而非单次耗时。

### 波动率计算中的 Python 循环

`compute_ai_factors` 和 `compute_nasdaq_factors` 中的 20/60 日滚动波动率计算使用了 Python `for` 循环逐窗口计算 `np.std`，而非向量化 `pandas.rolling().std()`，这在不支持 numpy 向量化加速的环境中可能较慢。

## 4. 优化建议

| 建议 | 预期收益 | 实施难度 | 备注 |
| --- | --- | --- | --- |
| 批量调用技术指标 API | 减少 60-70% 因子计算耗时（~25s） | 中 | 需确认聚宽是否支持批量 BIAS/ROC 调用 |
| 缓存跨日可复用数据 | 减少 10-15% 总耗时 | 低 | 因子计算中的历史序列缓存 |
| 消除重复 API 调用 | 减少 5-10% | 低 | gold/nasdaq ROC 被计算两次，可缓存到局部变量 |
| 使用 pandas rolling 替代 Python for 循环 | 减少 5-8% | 低 | 波动率惩罚计算的向量化 |
| get_price 使用 panel=True | 减少 3-5% | 低 | 一次调用获取所有 ETF 数据 |
| 因子计算延迟化 | 减少 80% 因子计算 | 高 | 仅在偏离度超过阈值时计算因子（skip 约 80% 交易日） |

### 关键优化：因子计算延迟化

当前策略每次 `daily_check` 都完整计算了三个因子函数，但 80% 的交易日最终因偏离度未超过阈值而跳过调仓。如果将因子计算移到偏离度检查之后（仅在需要调仓时计算），理论上可节省约 33.5s（73.6% × 80% ≈ 59% 的总耗时）。

需要注意的是，日志中的因子得分和风险平价权重仍可能对调试有价值，可考虑通过 `log.level` 控制在生产环境关闭。

## 5. 建议优先级

1. **消除重复 API 调用**（低难度、立即见效）：将 `ROC(gold)` 和 `ROC(nasdaq)` 提取到 `daily_check` 级别，传入因子函数而非各自调用。
2. **因子计算延迟化**（中难度、最大收益）：将因子计算移到偏离度检查之后，仅在需要调仓时计算。预期减少 ~60% 的回测耗时。
3. **get_price 合并为批量调用**（中难度、需验证 API 支持）：使用 `panel=True` 或批量获取，减少调用次数。
4. **向量化波动率计算**（低难度）：用 `pd.Series.rolling().std()` 替代 Python 循环。
5. **批量技术指标调用**（高难度、依赖平台支持）：需确认聚宽是否支持一次传入多个股票代码。

## 6. 结论

- **当前最大性能问题**：因子计算链（compute_gold/ai/nasdaq_factors）占 daily_check 总耗时的 73.6%，其中 BIAS/ROC API 调用是绝对瓶颈。
- **最值得优先处理的改动**：因子计算延迟化——仅在实际需要调仓时才计算因子得分，可将 80% 的无效计算消除。
- **预计对回测耗时的改善**：实施优先级 1-3 后，预期回测耗时从 84 秒降至 30-40 秒（减少 50-60%）。
