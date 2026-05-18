# 执行时序影响研究计划

- **制定日期**: 2026-05-18
- **适用策略**: [etf_factor_rotation.py](../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->
- **技术实现依据**: [ETF轮动策略技术实现方案.md](ETF轮动策略技术实现方案.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/design/ETF轮动策略技术实现方案.md -->
- **本地研究平台依据**: [scripts/research/README.md](../../../../scripts/research/README.md) <!-- pathref: scripts/research/README.md -->
- **平台核心能力说明**: [scripts/research/platform/README.md](../../../../scripts/research/platform/README.md) <!-- pathref: scripts/research/platform/README.md -->
- **价格数据模型**: [scripts/research/research_core/prices.py](../../../../scripts/research/research_core/prices.py) <!-- pathref: scripts/research/research_core/prices.py -->
- **研究主题**: 量化“执行晚一天”和“盘后多看一天数据”对当前标准回测的影响，并在确认真实实盘口径前先完成最小必要研究

## 1. 研究目标

当前正式回测口径和人工实盘流程并不完全一致。

正式回测代码采用：

```text
本周首个交易日开盘执行
信号数据截止到上一交易日
```

普通交易周等价于：

```text
周五收盘数据 -> 周一开盘成交
```

当前人工流程表面上是：

```text
周一盘后查看聚宽模拟盘信号 -> 周二开盘实盘成交
```

但截至 2026-05-18，尚未确认聚宽模拟盘实际对应：

1. `logic-2`：周五收盘数据 -> 周一开盘已经生成信号 / 执行，人工只是在周二复制
2. `logic-3`：周一收盘数据 -> 周二开盘执行

本研究先不等待真实口径确认，而是先回答一个更基础的问题：

> 无论最终实盘是 `logic-2` 还是 `logic-3`，它相对当前标准回测到底会造成多大影响？

## 2. 当前已知事实

### 2.1 标准回测口径

当前策略在 `initialize()` 中注册：

```python
run_weekly(
    weekly_check,
    weekday=1,
    time='open',
    reference_security='000300.XSHG'
)
```

并在取历史数据时统一使用：

```python
end_date=context.previous_date
```

对应代码见：

- [etf_factor_rotation.py](../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->
- [ETF轮动策略技术实现方案.md](ETF轮动策略技术实现方案.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/design/ETF轮动策略技术实现方案.md -->

因此当前标准回测应定义为：

```text
baseline:
asof = 上一交易日收盘
trade = 本周首个交易日开盘
```

### 2.2 当前本地平台的边界

现有本地研究平台适合优先筛选、拆解差异来源，但还不能直接把本研究作为正式定案工具：

1. `ParameterFollowupPlugin` 明确把 `signal_definition`、`execution_logic` 列为不支持变化
2. 当前价格数据模型只有 `close/high/low/money`，没有 `open`
3. 现有研究数据更适合复放信号、权重和日收益路径，不足以完整模拟“周一开盘 vs 周二开盘”的执行差异

对应依据：

- [scripts/research/platform/README.md](../../../../scripts/research/platform/README.md) <!-- pathref: scripts/research/platform/README.md -->
- [scripts/research/platform/plugins.py](../../../../scripts/research/platform/plugins.py) <!-- pathref: scripts/research/platform/plugins.py -->
- [scripts/research/research_core/prices.py](../../../../scripts/research/research_core/prices.py) <!-- pathref: scripts/research/research_core/prices.py -->

### 2.3 当前决策边界

在真实实盘口径尚未确认前：

- 不提前认定 `logic-2` 或 `logic-3`
- 不直接把人工实盘结果与标准回测结果并列解释
- 先把两类影响拆开测清：
  - **执行延迟影响**
  - **信号刷新影响**

## 3. 三组研究口径

| 口径 | 数据截止 | 成交时点 | 研究含义 |
|---|---|---|---|
| `baseline` | 上一交易日收盘 | 本周首个交易日开盘 | 当前标准回测 |
| `logic-2-delay-only` | 上一交易日收盘 | 下一交易日开盘 | 只改变执行日，衡量晚一天成交 |
| `logic-3-live-like` | 本周首个交易日收盘 | 下一交易日开盘 | 同时改变信号日和执行日，模拟“盘后出信号、次日执行” |

普通交易周下可直观理解为：

| 口径 | 普通周示意 |
|---|---|
| `baseline` | 周五收盘信号 -> 周一开盘成交 |
| `logic-2-delay-only` | 周五收盘信号 -> 周二开盘成交 |
| `logic-3-live-like` | 周一收盘信号 -> 周二开盘成交 |

三组关系必须按以下方式解释：

```text
logic-2-delay-only - baseline
= 纯执行延迟影响

logic-3-live-like - logic-2-delay-only
= 周一收盘新增信息导致的信号刷新影响

logic-3-live-like - baseline
= 实盘近似流程相对标准回测的总影响
```

## 4. 研究假设

| 编号 | 假设 | 需要验证的问题 |
|---|---|---|
| `H1` | `logic-2` 的主要差异来自多持有旧仓一天，而不是组合结构变化 | 晚一天成交会造成多大收益和风险偏移 |
| `H2` | `logic-3` 是否显著不同，取决于周一收盘后信号是否经常改变 | 新增一天数据会不会经常改动最终权重 |
| `H3` | 如果 `logic-2` 和 `logic-3` 相对 `baseline` 都很小，则当前标准回测仍可作为主要解释口径 | 是否可以继续把标准回测作为主基准 |
| `H4` | 如果 `logic-3` 明显偏离 `logic-2`，则真实实盘口径确认将直接影响后续评估方式 | 明天确认后是否需要改主基线 |

## 5. 为什么先本地、再云端

### 5.1 先本地的原因

本研究最先需要回答的是“值不值得上云”，不是立刻写回策略默认值。

先本地有三个好处：

1. 可以把 `执行延迟` 和 `信号刷新` 两个机制先拆开
2. 可以快速识别差异主要来自哪里，避免一上来做三组云端黑盒对比
3. 可以减少云端配额消耗，把云端留给最终需要确认的口径

### 5.2 本地不能直接定案的原因

当前本地平台还缺两个关键条件：

1. 没有 `open` 字段，无法精确还原开盘成交路径
2. 现有 replay 机制没有把 `execution_logic` 作为已支持能力

因此本地阶段的结论只能分为：

- **方向性判断**
- **是否值得云端确认**

不能直接写成：

- “实盘口径已经确认优于 / 劣于标准回测”
- “可以替代正式回测结果”

## 6. Phase 0：先补本地研究底座

### 6.1 数据补齐

需要把现有 JoinQuant 价格导出从：

```text
close / high / low / money
```

扩展为：

```text
open / close / high / low / money
```

涉及改动：

| 位置 | 目的 |
|---|---|
| 价格导出脚本 | 导出 `open` |
| `PriceFrames` | 增加 `open` 字段 |
| 数据集归一化逻辑 | 保留 `open` |
| 数据契约与 README | 更新字段说明 |

### 6.2 研究项目

建议新建正式研究项目：

```text
strategies/etf_factor_rotation/reports/research/execution_timing/
```

建议目录结构：

```text
docs/
inputs/raw/
exports/joinquant/
runs/<run_id>/{reports,tables,curves}
```

理由：

- 与现有 `window_heterogeneity`、`portfolio_volatility` 项目布局一致
- 后续如果确认需要反复研究执行口径，不必把脚本和产物散落在 `design/`

## 7. Phase 1：本地优先研究

### 7.1 子问题 A：执行延迟影响

目标：

> 在信号不变的前提下，只把成交从本周首个交易日开盘推迟到下一交易日开盘，影响有多大？

核心输出：

| 产物 | 说明 |
|---|---|
| `delay_only_weekly_impact.csv` | 每周晚一天执行造成的收益差 |
| `delay_only_summary.json` | 总体均值、累计差、年度拆解、最差周 |
| `delay_only_impact.md` | 解释“晚一天”是否本身就足够重要 |

建议指标：

- 周度延迟收益差
- 全样本累计差
- 年度分解
- 最差 `10` 个周
- 对三只 ETF 的贡献拆分

### 7.2 子问题 B：信号刷新影响

目标：

> 把信号从“上一交易日收盘”改成“本周首个交易日收盘”后，目标权重是否经常明显变化？

核心输出：

| 产物 | 说明 |
|---|---|
| `signal_shift_weekly.csv` | 每周两套目标权重及差异 |
| `signal_shift_summary.json` | 变化次数、L1 距离、全空/半仓状态切换 |
| `signal_shift_report.md` | 解释新增一天数据是否改变策略判断 |

建议指标：

- 目标权重 L1 距离
- 每周是否发生任何持仓权重变化
- TopK 排序是否改变
- 全空仓 / 非全空仓状态切换次数
- 各模块中最常触发差异的来源：
  - `TrendGate`
  - `MomentumScore`
  - `CrowdPenalty`
  - `PortfolioVolScale`

### 7.3 子问题 C：近似总影响

目标：

> 在本地先构建一个近似的三组收益路径，判断是否已经足以显示明显偏离。

注意：

- 这一步只能作为 `LOCAL_REPLAYABLE` 近似
- 不能替代云端最终回测

核心输出：

| 产物 | 说明 |
|---|---|
| `timing_path_compare.csv` | `baseline / logic-2 / logic-3` 的近似日收益路径 |
| `timing_path_summary.json` | 近似绩效对比 |
| `timing_local_decision.md` | 是否需要进入云端确认 |

建议指标：

- 年化收益差
- 最大回撤差
- 波动率差
- Sharpe 差
- 年度分解
- 配对 block bootstrap
- 滚动 `252` 日 Sharpe 胜率

## 8. Phase 1 的解释规则

### 8.1 判断“影响很小”

若同时满足以下条件，可把本地结论解释为“实盘时序差异大概率不是当前策略表现解释的首要来源”：

- `logic-2-delay-only` 相对 `baseline` 的年化差绝对值 `<= 0.30pp`
- `logic-3-live-like` 相对 `baseline` 的年化差绝对值 `<= 0.50pp`
- `logic-2` 与 `logic-3` 的最大回撤都不比 `baseline` 恶化超过 `0.30pp`
- `signal_shift` 中大部分周的目标权重 L1 距离较小，且状态切换罕见
- 没有单一年份承担绝大部分差异

### 8.2 判断“需要尽快云端确认”

满足任一条件，就应进入云端正式 A/B：

- `logic-2-delay-only` 相对 `baseline` 的年化差绝对值 `> 0.30pp`
- `logic-3-live-like` 相对 `baseline` 的年化差绝对值 `> 0.50pp`
- 任一逻辑把最大回撤恶化超过 `0.30pp`
- `logic-3` 相对 `logic-2` 出现明显额外偏移，说明新增一天数据确实改变了策略判断
- 信号状态切换集中出现在关键年份或关键回撤区间

## 9. Phase 2：云端正式确认

### 9.1 进入条件

仅在下列任一情形触发：

1. 本地结果显示差异不小
2. 明天确认真实模拟盘口径后，需要对真实执行流程给出正式量化结果
3. 本地近似路径与标准回测已经出现解释冲突

### 9.2 云端最小矩阵

| 变体 | 用途 |
|---|---|
| `baseline` | 当前标准回测 |
| `logic-2-delay-only` | 只晚一天成交 |
| `logic-3-live-like` | 盘后信号、次日成交 |

### 9.3 云端正式产物

| 产物 | 内容 |
|---|---|
| A/B 配置 | 三组正式云端场景 |
| 对比报告 | 收益、回撤、Sharpe、年度拆解 |
| 审计日志 | 逐周确认 `signal_date / asof_date / trade_date` |
| 决策报告 | 标准回测是否仍可作为主解释口径 |

## 10. 研究产物清单

| 阶段 | 必要产物 |
|---|---|
| Phase 0 | `open` 数据补齐、数据契约更新、项目骨架 |
| Phase 1A | `delay_only_weekly_impact.csv`、`delay_only_summary.json`、`delay_only_impact.md` |
| Phase 1B | `signal_shift_weekly.csv`、`signal_shift_summary.json`、`signal_shift_report.md` |
| Phase 1C | `timing_path_compare.csv`、`timing_path_summary.json`、`timing_local_decision.md` |
| Phase 2 | 云端 A/B 配置、comparison 报告、decision 报告 |

## 11. 推荐执行顺序

1. 先补 `open` 数据和本地数据模型
2. 建立 `execution_timing` 本地研究项目
3. 先跑 `delay_only`
4. 再跑 `signal_shift`
5. 最后生成三组近似路径
6. 明天确认模拟盘真实口径后，优先把真实那一路与 `baseline` 对齐解释
7. 只有本地结果显示影响不小，或真实口径需要正式量化时，才进入三组云端 A/B

## 12. 当前建议

当前不建议立刻消耗云端配额。

更合理的顺序是：

```text
先补本地 open 数据
-> 先量化执行延迟
-> 再量化信号刷新
-> 明天确认真实盘口径
-> 只把真正需要正式回答的分支升级到云端
```

这样可以先回答“实盘逻辑是否足以显著改变标准回测解释”，同时避免在 `logic-2` / `logic-3` 尚未确认前，把两条研究线混在一起。
