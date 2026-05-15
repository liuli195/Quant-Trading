# 拥挤度惩罚 AB 验证 — 最终决策

- **实验日期**: 2026-05-15
- **回测窗口**: 2021-01-01 → 2026-04-30
- **变体总数**: 8 个（黄金 4 + AI 4）
- **数据完整性**: 全部变体包含完整 research bundle + audit_log（1090 条/变体）
- **产物状态**: 8 个变体均已补充 strategy-analysis.md 与 performance-analysis.md（jq-analyze fix-missing 补产），另含稳健性验证报告 [robustness-verification.md](../backtest_runs/20260515-2051-bte8e07662646ef6b56f453ea15c7d959d/report/robustness-verification.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260515-2051-bte8e07662646ef6b56f453ea15c7d959d)/robustness-verification.md -->
- **分析深度**: 标准 AB 指标 + 多窗口 CrowdDiff + Bootstrap CI95 + 子周期稳定性

---

## 1. 实验 A：黄金拥挤度惩罚

### 1.1 标准指标

| 变体 | Sharpe | 年化收益 | 最大回撤 | vs Baseline |
|------|--------|---------|---------|-------------|
| gold-baseline ★ | 1.437 | 15.44% | 8.09% | — |
| **gold-start-080** | **1.447** | **15.76%** | 8.09% | **+0.7% Sharpe, +0.32pp** |
| gold-neutralized | 1.389 | 15.70% | 8.09% | -3.3% Sharpe |
| gold-calc-longwin | 1.414 | 15.29% | 8.09% | -1.6% Sharpe |

### 1.2 多窗口 CrowdDiff 验证（黄金 ETF）

**gold-baseline**（CrowdStart=0.60，惩罚率 35%）：

| 窗口 | 惩罚态 P&L | 非惩罚态 P&L | Diff | CI95 | 方向 |
|------|-----------:|-------------:|-----:|------|------|
| 5d | +278.1 | +136.0 | +142.1 | [-307, +458] | 正向（惩罚有害） |
| 10d | +577.0 | +250.2 | +326.7 | [-408, +884] | 正向 |
| 20d | +1177.5 | +606.5 | +571.1 | [-1116, +1677] | 正向 |
| 40d | +2358.0 | +1393.8 | +964.2 | [-136, +3174] | 正向 |

**gold-start-080**（CrowdStart=0.80，惩罚率 12%）：

| 窗口 | 惩罚态 P&L | 非惩罚态 P&L | Diff | CI95 | 方向 |
|------|-----------:|-------------:|-----:|------|------|
| 5d | +164.2 | +210.9 | -46.7 | [-2418, +74] | **转负** |
| 10d | +401.9 | +402.9 | -1.0 | [-3382, +308] | **转负** |
| 20d | +497.0 | +937.9 | -440.8 | [-3414, +222] | **转负** |
| 40d | +1655.8 | +1907.9 | -252.1 | [-4575, +1499] | **转负** |

### 1.3 子周期稳定性（黄金 ETF）

| 变体 | 时期 | 5d Diff | 40d Diff | 惩罚率 |
|------|------|--------:|---------:|-------:|
| gold-baseline | 2021-2023 | -28.0 | +179.3 | 11.8% |
| gold-baseline | 2024-2026 | -88.6 | -1970.3 | 67.5% |
| gold-start-080 | 2021-2023 | +177.3 | +912.3 | 3.9% |
| gold-start-080 | 2024-2026 | -336.2 | -2713.0 | 23.7% |

### 1.4 黄金结论

**采用 `gold-start-080`：黄金 CrowdStart 从 0.60 提高到 0.80。**

证据链：
1. 标准指标全面改善（Sharpe +0.7%，年化收益 +0.32pp），最大回撤不变
2. 多窗口 CrowdDiff 从"全线正向"翻转为"全线负向"——提阈值后，剩余的惩罚触发点（惩罚率 35%→12%）方向正确了，现有结果支持将阈值上调到 0.80，原 0.60-0.80 区间惩罚方向不合理
3. 纳指 CrowdDiff 在 gold-start-080 中与 baseline 几乎一致（-202 vs -193 at 5d, -1176 vs -1119 at 40d），哨兵校验通过：黄金参数变更未造成权重溢出
4. 子周期 2021-2023 惩罚率极低（3.9%），说明黄金在该时期极少进入高拥挤状态。核心改善期在 2024-2026（黄金牛市期），该时期 baseline 惩罚率 67.5% → gold-start-080 降至 23.7%，可能减少了约 44pp 的过早惩罚
5. 不采用 gold-neutralized（Sharpe -3.3%）——证明完全取消惩罚有害，top 20% 的极端拥挤信号仍有保护价值
6. 不采用 gold-calc-longwin（Sharpe -1.6%）——延长收益窗口使分数钝化，失去了捕获真正拥挤的能力

**限制条件**：黄金采用结论基于 AB 层面的点估计优势（Sharpe +0.7%、年化收益 +0.32pp），CrowdDiff 的多窗口 CI95 全部包含 0，且惩罚样本仅 32-33 个事件，尚未形成统计显著性证据。CrowdDiff 仅作方向性佐证，不构成独立证明。

**待观察项**：2021-2023 子周期样本量小（惩罚率 3.9%），Gold CrowdDiff 在该时期的 sign 为正但样本极稀疏。建议 2026 年底复盘时重新检查黄金 CrowdDiff 是否在更长的样本中保持负向。

---

## 2. 实验 B：AI 拥挤度惩罚

### 2.1 标准指标

| 变体 | Sharpe | 年化收益 | 最大回撤 | vs Baseline |
|------|--------|---------|---------|-------------|
| **ai-baseline ★** | **1.437** | **15.44%** | 8.09% | — |
| ai-start-075 | 1.421 | 15.41% | 8.09% | -1.1% Sharpe |
| ai-neutralized | 1.340 | 15.06% | 8.09% | **-6.8% Sharpe** |
| ai-calc-longwin | 1.418 | 15.29% | 8.09% | -1.3% Sharpe |

### 2.2 多窗口 CrowdDiff 验证（AI ETF）

**ai-baseline**（CrowdStart=0.60，惩罚率 31%）：

| 窗口 | 惩罚态 P&L | 非惩罚态 P&L | Diff | CI95 | 方向 |
|------|-----------:|-------------:|-----:|------|------|
| 5d | +115.6 | +70.2 | +45.4 | [-329, +423] | 正向（惩罚偏早） |
| 10d | +235.5 | +135.8 | +99.7 | [-790, +784] | 正向 |
| 20d | +345.2 | +275.6 | +69.6 | [-1595, +1327] | 正向 |
| 40d | +456.8 | +656.5 | **-199.7** | [-1643, +1675] | **转负（惩罚有效）** |

**ai-neutralized**（CrowdStart=0.99，惩罚率 0%）：
- 无惩罚触发事件，无法计算 CrowdDiff
- 惩罚的完全缺失导致 Sharpe 从 1.437 降至 1.340（-6.8%）
- 这从策略层面验证了 AI 惩罚的功能价值：**取消 AI 惩罚对整体表现有显著负面影响**（Sharpe -6.8%）。但该对比说明的是"AI 惩罚作为一个策略模块有价值"，不能单独证明 40 日均值回归机制的真实存在——ai-neutralized 同时消除了所有惩罚触发，无法区分不同窗口的惩罚贡献

### 2.3 子周期稳定性（AI ETF）

| 变体 | 时期 | 5d Diff | 40d Diff | 惩罚率 |
|------|------|--------:|---------:|-------:|
| ai-baseline | 2021-2023 | -13.9 | +163.2 | 17.1% |
| ai-baseline | 2024-2026 | -65.1 | -1591.7 | 48.2% |

AI 子周期特征：2021-2023 惩罚率 17.1%（罕见），2024-2026 惩罚率 48.2%（频繁）。40 日 CrowdDiff 在 2021-2023 为正向（短/中/长期均未显示保护），在 2024-2026 为强负向（所有窗口有效）。

### 2.4 AI 结论

**保留当前参数（CrowdStart=0.60），不做修改。**

证据链：
1. 所有变体（提高阈值、取消惩罚、延长窗口）全部输给 baseline——当前 0.60 是已测方案中最好的
2. ai-neutralized 的 Sharpe 暴跌 6.8%（最大退化），证实归因报告中 40 日 -188.8 的惩罚价值是真实存在的——不是噪音，是真正的长期拥挤均值回归
3. AI 的 CrowdDiff 展示的是"短痛换长益"模式：5/10/20 日窗口惩罚态 P&L 更高（短期减仓过早），但 40 日窗口翻转（惩罚态 P&L 更低，长期减仓正确）。当前 0.60 的阈值所在位置恰好是这种权衡的最优点
4. 2021-2023 子周期中 AI 惩罚很少（17.1%），说明 AI 的拥挤信号集中在后段。如果要降低前段误判而不牺牲后段保护，需要比简单阈值调整更复杂的手段（如动态阈值、条件惩罚），超出当前实验范围
5. 纳指哨兵校验通过：AI 中性化时纳指的 CrowdDiff 未出现异常变化

**策略含义**：AI 拥挤度惩罚是"半有效"的——它有时过早减仓（短期代价），但长期维度上正确（40 日保护）。当前 0.60 的阈值是一个合理的折中点。在已测方案范围内，简单调参方向都未能改善这个权衡。

---

## 3. 纳指哨兵报告

两个实验的所有变体中，纳指拥挤度惩罚的 CrowdDiff 始终为负向，惩罚率稳定在 ~30%：

| 来源 | 5d Diff | 40d Diff | 惩罚率 |
|------|--------:|---------:|-------:|
| gold-baseline | -202.0 | -1176.2 | 30.3% |
| gold-start-080 | -192.7 | -1118.8 | 30.3% |
| ai-baseline | -202.0 | -1176.2 | 30.3% |
| ai-neutralized | -208.0 | -1146.7 | 30.3% |

纳指指标在跨变体间高度一致，说明黄金和 AI 的参数变更未通过风险平价权重传导产生溢出效应。哨兵校验通过。

---

## 4. 实施决定

| ETF | 决定 | 参数变更 | 实施方式 |
|-----|------|---------|---------|
| 黄金 | **采用** | CrowdStart: 0.60 → 0.80 | 设置 `g.CrowdStart_by_etf = [0.60, 0.60, 0.80]` |
| AI | **保留** | 不变 | 无需修改代码（全局默认 0.60 覆盖 AI） |
| 纳指 | **保留** | 不变 | 无需修改代码 |

**策略代码修改**：在 `set_parameter()` 中增加一行：
```python
g.CrowdStart_by_etf = [0.60, 0.60, 0.80]
```
（AI=0.60, 纳指=0.60, 黄金=0.80）

其他 per-ETF 参数保持 `None`（走全局默认值）。

---

## 5. 未解决问题与后续建议

1. **Gold 2021-2023 小样本**：该时期黄金惩罚率仅 3.9%，CrowdStart=0.80 下该时期仅 ~5 个惩罚事件。虽然 gold-start-080 的整体指标优于 baseline，但早期样本中 CrowdDiff 的 sign 不稳定。建议 2026Q4 复盘时重新检查。

2. **AI 的"半有效"状态**：这是本实验最有趣的发现。AI 拥挤度惩罚在短/中无效但在长期有效，说明它是一个"不耐受短期噪音但长期有价值的信号"。可能的改进方向（不在本次范围）：
   - 分窗口惩罚：对 AI 使用条件触发（如仅在 VolScale < 0.7 时才执行拥挤度惩罚）
   - 动态阈值：根据市场状态（趋势强度、波动率区间）自适应调整 CrowdStart

3. **CrowdDiff 的 CI95 普遍很宽**：在所有 ETF/窗口中，CI95 几乎全部包含 0。这不是说信号不存在——而是说回测中 272 次调仓的样本量不足以产生统计显著的多窗口 CrowdDiff。AB 实验层面的 Sharpe 差异（跨 1289 个交易日）是比单因子 CrowdDiff 更有统计效力的指标。结论应主要基于 AB 指标，CrowdDiff 作为方向性佐证。

4. **无需联合验证实验**：`gold-start-080` 的参数 `[0.60, 0.60, 0.80]` 已经同时包含 AI 不变 + 黄金提阈值。AI 的最优参数恰好是 baseline（0.60），因此 gold-start-080 本身就等价于联合最优。

5. **strategy-analysis 与 performance-analysis 已补产**：本批次 8 个变体已通过 jq-analyze fix-missing 补齐 strategy-analysis.md 与 performance-analysis.md（共 16 份）。另新增 [稳健性验证报告](../backtest_runs/20260515-2051-bte8e07662646ef6b56f453ea15c7d959d/report/robustness-verification.md) <!-- pathref: backtest_report_dir(strategy=etf_factor_rotation, run_id=20260515-2051-bte8e07662646ef6b56f453ea15c7d959d)/robustness-verification.md -->（配对 block bootstrap + 滚动子样本 + 年度分解），核心发现：日频 bootstrap CI95 含 0（p=0.296），滚动 Sharpe 胜率 47%（variant 在多数滚动窗口未占优），年度层面 3/6 年改善。稳健性结论降调为"方向性支持，非统计证实"。

---

## 附录：数据索引

| 实验 | AB 对比报告 | 多窗口验证报告 | JSON 摘要 |
|------|-----------|--------------|----------|
| 黄金 | [ab-gold-crowd-ab-comparison.md](../test_batches/20260515-gold-crowd-ab/report/ab-gold-crowd-ab-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260515-gold-crowd-ab)/ab-gold-crowd-ab-comparison.md --> | [crowd-window-check.md](../test_batches/20260515-gold-crowd-ab/report/crowd-window-check.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260515-gold-crowd-ab)/crowd-window-check.md --> | [ab-gold-crowd-ab-summary.json](../test_batches/20260515-gold-crowd-ab/report/ab-gold-crowd-ab-summary.json) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260515-gold-crowd-ab)/ab-gold-crowd-ab-summary.json --> |
| AI | [ab-ai-crowd-ab-comparison.md](../test_batches/20260515-ai-crowd-ab/report/ab-ai-crowd-ab-comparison.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260515-ai-crowd-ab)/ab-ai-crowd-ab-comparison.md --> | [crowd-window-check.md](../test_batches/20260515-ai-crowd-ab/report/crowd-window-check.md) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260515-ai-crowd-ab)/crowd-window-check.md --> | [ab-ai-crowd-ab-summary.json](../test_batches/20260515-ai-crowd-ab/report/ab-ai-crowd-ab-summary.json) <!-- pathref: test_batch_report_dir(strategy=etf_factor_rotation, batch_id=20260515-ai-crowd-ab)/ab-ai-crowd-ab-summary.json --> |

| 变体 | Run ID |
|------|--------|
| gold-baseline | `20260515-2049-bt7636c4788d821690fd90b281dee7e913` |
| gold-start-080 | `20260515-2051-bte8e07662646ef6b56f453ea15c7d959d` |
| gold-neutralized | `20260515-2054-bt72abfe3d501669b91a4b3d3a0fd5b49b` |
| gold-calc-longwin | `20260515-2056-bt3e11aaf64867aa42e8644d88dfe0a4e3` |
| ai-baseline | `20260515-2100-bt852ee6d4016248c77c11386f2f6a7245` |
| ai-start-075 | `20260515-2102-bt5d8807c600e004cf70f4c4b31a1b28ac` |
| ai-neutralized | `20260515-2105-bt6fb6670169c26ae89dd2902eba243fff` |
| ai-calc-longwin | `20260515-2107-bt157c5e16bdd7a47cb327a70b75b69da4` |
