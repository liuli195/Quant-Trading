# 退出标准核查

> batch_id: `20260505-0000-etf-factor-rotation-full-test`
> 审查时间：2026-05-06 Day 5

## 逐项核查

| # | 退出标准 | 状态 | 证据/说明 |
|---|----------|:--:|------|
| 1 | C0 全部通过 | ✅ | R0 正常运行、5 笔交易、0 错误日志。C0-001~005 验证通过。 |
| 2 | C1-DATA 全部通过 | ✅ | R1 修正版数据管道修复确认，42 笔交易正常。C1-DATA-001~005 通过。 |
| 3 | C1-SIG 关键用例全部通过，未触发项有解释 | ✅ | R1 信号链验证通过（TrendGate→Momentum→TopK→RP→RSRS→Crowd→VolScale→FinalWeight）。C1-SIG-009~010（RSRS/拥挤度边界）因 R3 约束过紧未触发，已在 I003 记录。 |
| 4 | C1-EXEC 成功路径通过，未触发异常路径有本地覆盖或云端说明 | ✅ | R1 42 笔/R4 469 笔交易全部正常执行。无 ERROR 日志。初始状态的 WARNING（`Security in positions 不存在`、`开仓数量必须是100的整数倍`）为正常行为。 |
| 5 | FQ A/B 完成对比，口径决策明确 | ⚠️ 有条件通过 | fq-decision.md 已产出，决策为维持 fq=None。但同区间对比未完成（I002），决策基于单侧测试和 ETF 特性推导，非实测对比。 |
| 6 | C2-LONG 默认参数长周期回测完成 | ✅ | R4 覆盖 2018-01~2026-04（8.3 年）。469 笔交易、175 盈/65 亏、夏普 0.662。 |
| 7 | C2-REGIME 核心场景覆盖（至少 5/8） | 👁️ 待审查 | R4 8.3 年覆盖多轮牛熊，但未做细化场景拆分标注（I006）。建议你人工判断是否需要细化。 |
| 8 | C3 关键性能用例通过，无异常退化 | ✅ | R6 高窗口/R7 扩展池均正常运行。R4 8.3 年回测无性能异常。R4 profile 数据待分析（performance-analysis 未提取 profile 部分）。 |
| 9 | 每 run_id 下三份报告齐全 | ❌ 3/8 缺 | R0/R2/R5 缺 strategy-analysis + performance-analysis（I005）。3 份 run 共有 `summary_metrics.json`，可后续补充分析。 |
| 10 | batch-comparison.md + issue-log.md 生成 | ✅ | 两份文档已在 Day 5 产出。 |
| 11 | 本计划可被他人复现 | ✅ | Manifest 已更新修正映射、参数记录明确、每个 run 有 metadata.json 含回测 URL。但 R1 区间 6 月 vs 计划 1 年的偏差需注明。 |

## 阻塞项

**无硬阻塞**。第 5 项（FQ 同区间对比缺失）和第 9 项（3 个 run 缺分析报告）为软缺口：

- FQ 同区间对比：不影响当前默认值，但影响决策严谨性
- 3 份缺失报告：`jq-analyze` 可随时基于现有数据补充

## 建议

1. **R0/R2/R5 补充 strategy-analysis + performance-analysis** — 运行 `jq-analyze` 即可，无需云端额度
2. **C2-REGIME 场景细化** — 在 R4 strategy-analysis 中按年度或市场阶段拆分分析
3. **FQ 同区间对比** — 若未来有时间，补跑一个完整年度的 fq=post vs fq=None
