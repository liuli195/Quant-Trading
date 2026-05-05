# 性能分析报告

> run_id: `20260505-2218-bt149cf2096d978f58083820813960d145`
> 场景: s04-test-params (R3 测试参数)

## 1. 运行性能

| 指标 | 数值 | 说明 |
| --- | --- | --- |
| 策略文件大小 | ~32 KB | 上传版去除注释后 |
| 编译耗时 | 正常 | 编译无 Error/Traceback |
| 回测总耗时 | 短 | 6 个月 24 周调仓，约 8 min 预算内完成 |
| 数据拉取 | 正常 | fq='pre' 在此区间可用 |
| API Bundle | 完整 | 16 个文件全部成功抓取 |

## 2. 计算负载分析

### 各模块每调仓周期开销（24 次 × 3 ETF）

| 模块 | 操作 | 复杂度 | 实际影响 |
| --- | --- | --- | --- |
| fetch_field × 4 | 逐 ETF 拉取 close/high/low/amount | O(n × count) | 主要耗时，每次拉 ~750 bars |
| compute_trend_gates | MA120 均值 | O(n × window) | 可忽略 |
| compute_momentum_scores | 3 窗口排名 | O(n) | 可忽略 |
| select_topk | 排序取前 K | O(n log n) | n=3，可忽略 |
| compute_rp_weights | 波动率计算 | O(n × vol_window) | 可忽略 |
| compute_rsrs_multipliers | 滚动 β/R² | O(count) per ETF | **RSRS 是主要计算热点**，RSRS_M=600 + N=18 |
| compute_crowd_penalties | 5 指标分位排名 | O(count) per ETF | CrowdWindow=500 |
| compute_portfolio_vol_scale | 协方差矩阵 | O(m² × vol_window) | m=2（活跃 ETF），极轻 |

### 热点排名

1. **get_price × 4 次/周**：每次拉取 ~750 bars × 3 ETF，I/O 为主
2. **compute_rsrs_multipliers**：600 窗口滚动回归，numpy 向量化实现
3. **compute_crowd_penalties**：500 窗口 5 指标批量计算

### Profile 数据

profile.md 共 3073 行，覆盖全部 24 个调仓周期。主要耗时分布符合预期：数据拉取 >> RSRS 计算 >> 其他模块。

## 3. 数据管道效率

| 环节 | 效率 | 说明 |
| --- | --- | --- |
| close_ret 复用 | ✅ 好 | pct_change 只计算一次，RP 和 VolScale 共用 |
| 批量排名 | ✅ 好 | momentum 在截面上用 rank(pct=True) 批量完成 |
| 滚动计算 | ✅ 好 | RSRS 用 pandas rolling + 闭式公式，避免 lstsq 循环 |
| DataFrame 级批量 | ✅ 好 | CrowdPenalty 先在 DataFrame 层预计算 5 类指标 |

## 4. 资源消耗

| 指标 | 数值 |
| --- | --- |
| 回测自然天数 | 180 天 |
| 调仓次数 | 24 次 |
| 实际交易 | 4 笔 |
| profile 记录数 | 3073 条 |
| 日志记录数 | 312 条 |
| 内存占用 | 低（3 ETF，~750 bars） |

## 5. 与 R1/R2 性能对比

| 指标 | R1 (fq=pre, 12月) | R2 (fq=None, 12月) | R3 (测试参数, 6月) |
| --- | --- | --- | --- |
| 回测区间 | 2025-04~2026-04 | 2025-04~2026-04 | 2025-11~2026-04 |
| 调仓次数 | 52 | 52 | 24 |
| 交易笔数 | 0 | 82 | 4 |
| 编译耗时 | 正常 | 正常 | 正常 |
| profile 行数 | 3065 | 949 | 3073 |
| 日志行数 | 672 | 949 | 312 |
| 数据获取 | **失败** | 正常 | 正常 |

> R2 profile 仅 949 行 vs R1/R3 的 3000+ 行，差异可能是因为 R2 不复权模式下各计算分支耗时更短，profile 采样更少。

## 6. 性能风险评估

- ✅ 6 个月回测耗时在预算（8 min）内，计算负载未超预期
- ✅ RSRS_M=600 的向量化计算表现稳定
- ⚠️ profile 完整（3073 行），无性能异常退化
- ⚠️ R3 交易极少（4 笔），执行路径未充分覆盖，无法评估账单内交易的执行效率

## 7. 附录

- 原始数据目录：`backtest_runs/20260505-2218-bt149cf2096d978f58083820813960d145/`
- profile 数据：3073 条完整
- 备注：R3 计算负载低，未形成性能瓶颈
