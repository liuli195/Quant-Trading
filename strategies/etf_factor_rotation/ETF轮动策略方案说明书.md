# ETF 轮动策略方案说明书：方案1线性乘数版

> 主结构：**趋势门槛 + 动量选择 + 风险平价 + RSRS 线性修正 + 拥挤度线性惩罚 + 组合波动率控制风险**

---

## 0. 方案定位

本方案是一套用于 ETF / 场内基金轮动的多模块配置框架，适合用于以下资产池：

- AI / 科技成长类 ETF
- 纳斯达克100 ETF
- 黄金 ETF
- 其他高流动性、可连续交易的 ETF / 场内基金

本方案的目标是：

1. 在中期趋势成立时参与上涨；
2. 在趋势破坏时退出风险资产；
3. 在多个入选 ETF 之间合理分配风险；
4. 在价格结构转弱时平滑降仓；
5. 在交易拥挤、过热时平滑降低仓位；
6. 通过组合层面波动率控制总风险；
7. 允许最终仓位低于满仓，剩余资金保留为现金或低风险资产。

本版本只保留主方案实现路径，不包含双均线交叉、最大回撤控制、单 ETF 波动率惩罚等非主方案模块。

---

## 1. 核心原则

本方案不是单一择时指标，而是多个模块分工协作：

| 模块 | 主要职责 | 回答的问题 | 是否线性化 |
|---|---|---|---|
| 趋势门槛 | 判断资产是否允许进入候选池 | 能不能买？ | 否，保留硬过滤 |
| 动量选择 | 在可买资产中选择强势标的 | 买谁？ | 动量分数为线性组合，TopK 保留离散选择 |
| 风险平价 | 在入选资产之间分配基础权重 | 买多少的初始比例？ | 是，连续权重 |
| RSRS 修正 | 判断价格结构是否支持持有 | 结构是否健康？ | 是，截断线性乘数 |
| 拥挤度惩罚 | 判断交易是否过热 | 仓位是否需要打折？ | 是，截断线性惩罚 |
| 组合波动率控制 | 控制组合整体风险 | 总仓位是否需要缩放？ | 是，连续缩放 |

最终公式：

```text
FinalWeight_i,t
= RPWeight_i,t
× TrendGate_i,t
× RSRSMultiplier_i,t
× CrowdPenalty_i,t
× PortfolioVolScale_t
```

其中：

| 符号 | 含义 |
|---|---|
| `FinalWeight_i,t` | 第 `i` 只 ETF 在 `t` 日调仓后的最终目标仓位 |
| `RPWeight_i,t` | 风险平价得到的基础权重 |
| `TrendGate_i,t` | 趋势门槛，取值为 0 或 1 |
| `RSRSMultiplier_i,t` | RSRS 价格结构修正乘数，取值区间 `[0, 1]` |
| `CrowdPenalty_i,t` | 拥挤度惩罚乘数，取值区间 `[MinCrowdPenalty, 1]` |
| `PortfolioVolScale_t` | 组合波动率缩放系数，取值区间 `(0, 1]` |

---

## 2. 总体实施流程

每个调仓日执行以下流程：

```text
1. 更新 ETF 行情数据
2. 计算趋势门槛 TrendGate
3. 只保留 TrendGate = 1 的资产
4. 计算多周期动量分数 MomentumScore
5. 在趋势成立资产中选择 TopK
6. 对 TopK 入选资产计算风险平价基础权重 RPWeight
7. 计算 RSRS_Adj，并转化为线性 RSRSMultiplier
8. 计算 CrowdingScore，并转化为线性 CrowdPenalty
9. 合成 RawWeight
10. 根据 RawWeight 计算组合年化波动率 PortfolioVol
11. 计算 PortfolioVolScale
12. 得到 FinalWeight
13. 应用单资产最大仓位、最小有效仓位、最小调仓阈值等交易约束
14. 执行调仓，剩余仓位保留为现金或低风险资产
```

---

## 3. 数据定义

对第 `i` 只 ETF，在交易日 `t` 定义：

```text
Close_i,t  = 收盘价
High_i,t   = 最高价
Low_i,t    = 最低价
Amount_i,t = 成交额
Return_i,t = 日收益率
```

日收益率：

```text
Return_i,t = Close_i,t / Close_i,t-1 - 1
```

L 日收益率：

```text
Ret_i,t,L = Close_i,t / Close_i,t-L - 1
```

L 日移动平均：

```text
MA_i,t,L = Mean(Close_i,t-L+1 ... Close_i,t)
```

年化波动率：

```text
Vol_i,t,L = Std(Return_i,t-L+1 ... Return_i,t) × √252
```

截断函数：

```text
clip(x, lower, upper) = min(max(x, lower), upper)
```

---

## 4. 趋势门槛

### 4.1 设计目的

趋势门槛用于判断 ETF 是否处于可持有的大方向状态。

它只回答一个问题：

```text
这只 ETF 当前能不能进入候选池？
```

### 4.2 计算公式

使用 120 日均线作为中期趋势过滤：

```text
TrendGate_i,t = 1, if Close_i,t > MA_i,t,120
TrendGate_i,t = 0, otherwise
```

### 4.3 处理规则

- `TrendGate = 1`：允许进入候选池；
- `TrendGate = 0`：剔除，不参与动量排序，也不分配仓位。

趋势门槛不做线性化，原因是它的职责是过滤大方向风险。如果价格低于中期趋势线仍保留部分仓位，会削弱趋势过滤的意义。

---

## 5. 动量选择

### 5.1 设计目的

动量模块负责在趋势成立的资产中选择强势 ETF。

它回答：

```text
在可买资产中，买谁？
```

### 5.2 多周期收益率

计算 20 日、60 日、120 日收益率：

```text
Ret20_i,t  = Close_i,t / Close_i,t-20 - 1
Ret60_i,t  = Close_i,t / Close_i,t-60 - 1
Ret120_i,t = Close_i,t / Close_i,t-120 - 1
```

### 5.3 排名分数

由于 AI ETF、纳斯达克100 ETF、黄金 ETF 的波动率差异较大，直接使用收益率原值容易天然偏向高波动资产。

因此推荐使用排名分数。

假设候选池共有 `N` 只 ETF，对每个周期收益率从高到低排名：

```text
Rank_i,t,L = 第 i 只 ETF 在 L 日收益率上的排名
```

其中：

```text
Rank = 1 表示收益率最高
Rank = N 表示收益率最低
```

将排名转换为 0 到 1 的分数：

```text
RankScore_i,t,L = (N - Rank_i,t,L) / (N - 1)
```

如果候选池只有 1 只资产，则该资产的 `RankScore` 记为 1。

### 5.4 动量总分

```text
MomentumScore_i,t
= w20 × RankScore_i,t,20
+ w60 × RankScore_i,t,60
+ w120 × RankScore_i,t,120
```

默认：

```text
w20  = 0.2
w60  = 0.3
w120 = 0.5
```

### 5.5 TopK 入选规则

在 `TrendGate = 1` 的资产中，按 `MomentumScore` 从高到低排序，选择前 `TopK` 只 ETF。

默认：

```text
TopK = 2
```

入选规则：

```text
Selected_i,t = 1, if i ∈ TopK(MomentumScore)
Selected_i,t = 0, otherwise
```

如果趋势成立资产数量少于 `TopK`，则实际入选数量等于趋势成立资产数量。

---

## 6. 风险平价基础权重

### 6.1 设计目的

风险平价负责在入选资产之间分配基础权重。

它回答：

```text
入选 ETF 之间，基础仓位怎么分？
```

本方案初版推荐使用逆波动率风险平价，原因是：

1. 计算稳定；
2. 参数少；
3. 对小资产池足够实用；
4. 不容易受协方差估计误差影响。

### 6.2 波动率估计

对入选资产计算过去 `VolWindow` 日年化波动率：

```text
σ_i,t = Std(Return_i,t-VolWindow+1 ... Return_i,t) × √252
```

默认：

```text
VolWindow = 60
```

### 6.3 逆波动率权重

先计算原始逆波动率权重：

```text
RawRP_i,t = 1 / σ_i,t
```

再在入选资产中归一化：

```text
RPWeight_i,t = RawRP_i,t / Σ_j RawRP_j,t
```

其中：

```text
j ∈ SelectedAssets
```

如果只有一只资产入选：

```text
RPWeight_i,t = 1
```

未入选资产：

```text
RPWeight_i,t = 0
```

---

## 7. RSRS 线性修正

### 7.1 设计目的

RSRS 用于判断价格结构是否健康。

它不是独立买入信号，也不是趋势过滤器，而是仓位修正因子。

它回答：

```text
当前价格结构是否支持继续持有？
```

本版本使用线性乘数，使仓位变化更平滑。

### 7.2 RSRS 回归

对每只 ETF，在过去 `RSRS_N` 日内做回归：

```text
High_i,k = α_i,t + β_i,t × Low_i,k + ε_i,k
```

其中：

```text
k = t - RSRS_N + 1, ..., t
```

默认：

```text
RSRS_N = 18
```

得到：

```text
β_i,t  = 回归斜率
R²_i,t = 回归拟合优度
```

### 7.3 标准化

使用过去 `RSRS_M` 日的 β 序列计算均值和标准差：

```text
MeanBeta_i,t = Mean(β_i,t-RSRS_M+1 ... β_i,t)
```

```text
StdBeta_i,t = Std(β_i,t-RSRS_M+1 ... β_i,t)
```

标准分：

```text
RSRS_Z_i,t = (β_i,t - MeanBeta_i,t) / StdBeta_i,t
```

默认：

```text
RSRS_M = 600
```

### 7.4 R² 修正

```text
RSRS_Adj_i,t = RSRS_Z_i,t × R²_i,t
```

含义：

- `RSRS_Adj > 0`：价格结构偏强；
- `RSRS_Adj < 0`：价格结构偏弱；
- `R²` 越低，信号自动打折。

### 7.5 截断线性乘数

推荐使用只减仓、不加仓版本：

```text
RSRSMultiplier_i,t
= clip(1 + RSRS_Adj_i,t / RSRS_NegativeFullCut, 0, 1)
```

默认：

```text
RSRS_NegativeFullCut = 1.0
```

因此默认公式为：

```text
RSRSMultiplier_i,t = clip(1 + RSRS_Adj_i,t, 0, 1)
```

对应效果：

| RSRS_Adj | RSRSMultiplier |
|---:|---:|
| `≤ -1.0` | 0.0 |
| `-0.8` | 0.2 |
| `-0.5` | 0.5 |
| `-0.2` | 0.8 |
| `0` | 1.0 |
| `> 0` | 1.0 |

核心原则：

```text
RSRS 只减仓，不加仓。
```

---

## 8. 拥挤度线性惩罚

### 8.1 设计目的

拥挤度用于判断交易是否过热。

它不是买入信号，也不是准入门槛，而是风险惩罚因子。

它回答：

```text
当前 ETF 是否过热，仓位是否需要打折？
```

核心原则：

```text
低拥挤不加仓，高拥挤才减仓。
```

### 8.2 拥挤度指标

对每只 ETF 计算以下五类指标。

#### 8.2.1 20日涨幅分位数

```text
Ret20_i,t = Close_i,t / Close_i,t-20 - 1
```

```text
PctRet20_i,t = PercentileRank(Ret20_i,t, CrowdWindow)
```

#### 8.2.2 60日涨幅分位数

```text
Ret60_i,t = Close_i,t / Close_i,t-60 - 1
```

```text
PctRet60_i,t = PercentileRank(Ret60_i,t, CrowdWindow)
```

#### 8.2.3 成交额分位数

```text
AmountMA20_i,t = Mean(Amount_i,t-19 ... Amount_i,t)
```

```text
PctAmount_i,t = PercentileRank(AmountMA20_i,t, CrowdWindow)
```

#### 8.2.4 偏离均线程度分位数

```text
DeviationMA20_i,t = Close_i,t / MA_i,t,20 - 1
```

```text
PctDeviation_i,t = PercentileRank(DeviationMA20_i,t, CrowdWindow)
```

#### 8.2.5 短期波动率分位数

```text
Vol20_i,t = Std(Return_i,t-19 ... Return_i,t) × √252
```

```text
PctVol_i,t = PercentileRank(Vol20_i,t, CrowdWindow)
```

默认：

```text
CrowdWindow = 500
```

### 8.3 拥挤度总分

```text
CrowdingScore_i,t
= Mean(
    PctRet20_i,t,
    PctRet60_i,t,
    PctAmount_i,t,
    PctDeviation_i,t,
    PctVol_i,t
)
```

取值范围：

```text
0 ≤ CrowdingScore_i,t ≤ 1
```

含义：

| CrowdingScore | 状态 |
|---:|---|
| 接近 0 | 极度冷清 |
| 0.5 左右 | 正常 |
| 接近 1 | 极度拥挤 |

### 8.4 截断线性惩罚

设：

```text
CrowdStart = 0.60
CrowdEnd = 0.95
MinCrowdPenalty = 0.30
```

当拥挤度不高时不惩罚：

```text
CrowdingScore ≤ CrowdStart 时，CrowdPenalty = 1.0
```

当拥挤度极高时惩罚到最低值：

```text
CrowdingScore ≥ CrowdEnd 时，CrowdPenalty = MinCrowdPenalty
```

中间线性下降：

```text
CrowdPenalty_i,t
= clip(
    1 - (CrowdingScore_i,t - CrowdStart)
        / (CrowdEnd - CrowdStart)
        × (1 - MinCrowdPenalty),
    MinCrowdPenalty,
    1.0
)
```

默认公式：

```text
CrowdPenalty_i,t
= clip(
    1 - (CrowdingScore_i,t - 0.60) / 0.35 × 0.70,
    0.30,
    1.00
)
```

对应效果：

| CrowdingScore | CrowdPenalty |
|---:|---:|
| 0.50 | 1.00 |
| 0.60 | 1.00 |
| 0.70 | 0.80 |
| 0.75 | 0.70 |
| 0.85 | 0.50 |
| 0.90 | 0.40 |
| 0.95 | 0.30 |
| 0.98 | 0.30 |

---

## 9. 合成调整前权重

对入选资产，合成调整前权重：

```text
RawWeight_i,t
= RPWeight_i,t
× TrendGate_i,t
× RSRSMultiplier_i,t
× CrowdPenalty_i,t
```

未入选资产的 `RPWeight = 0`，因此 `RawWeight = 0`。

注意：

```text
RawWeight 不重新归一化到满仓。
```

如果 RSRS 或拥挤度降低了仓位，降低出来的部分应保留为现金或低风险资产。

---

## 10. 组合波动率控制

### 10.1 设计目的

组合波动率控制用于控制整体组合风险。

它回答：

```text
当前组合的整体波动风险是否过高？
```

该模块只做组合层面控制，不做单 ETF 波动率惩罚。

### 10.2 协方差矩阵

使用过去 `PortfolioVolWindow` 日的 ETF 日收益率估计协方差矩阵：

```text
Σ_daily,t = Cov(Returns over PortfolioVolWindow)
```

年化协方差矩阵：

```text
Σ_annual,t = Σ_daily,t × 252
```

默认：

```text
PortfolioVolWindow = 60
```

### 10.3 组合年化波动率

设调整前权重向量为：

```text
RawW_t = [RawWeight_1,t, RawWeight_2,t, ..., RawWeight_N,t]'
```

组合年化波动率：

```text
PortfolioVol_t = √(RawW_t' Σ_annual,t RawW_t)
```

### 10.4 波动率缩放系数

目标年化波动率：

```text
TargetVol = 12%
```

组合波动率缩放：

```text
PortfolioVolScale_t = min(1, TargetVol / PortfolioVol_t)
```

含义：

| 条件 | 处理 |
|---|---|
| `PortfolioVol ≤ TargetVol` | 不加仓，`PortfolioVolScale = 1` |
| `PortfolioVol > TargetVol` | 按比例降仓 |

不使用杠杆，所以 `PortfolioVolScale` 最大为 1。

---

## 11. 最终权重

最终目标仓位：

```text
FinalWeight_i,t
= RawWeight_i,t × PortfolioVolScale_t
```

展开为：

```text
FinalWeight_i,t
= RPWeight_i,t
× TrendGate_i,t
× RSRSMultiplier_i,t
× CrowdPenalty_i,t
× PortfolioVolScale_t
```

最终总仓位：

```text
TotalWeight_t = Σ_i FinalWeight_i,t
```

现金或低风险资产仓位：

```text
CashWeight_t = 1 - TotalWeight_t
```

要求：

```text
0 ≤ TotalWeight_t ≤ 1
```

---

## 12. 仓位约束与交易约束

### 12.1 单资产最大仓位

为了避免单只 ETF 风险集中：

```text
FinalWeight_i,t ≤ MaxWeight
```

默认：

```text
MaxWeight = 60%
```

### 12.2 最小有效仓位

如果某只 ETF 的最终目标仓位过小，可以直接设为 0：

```text
如果 FinalWeight_i,t < MinWeight，则 FinalWeight_i,t = 0
```

默认：

```text
MinWeight = 5%
```

### 12.3 最小调仓阈值

为降低换手率，如果新旧仓位差异太小，则不交易：

```text
如果 |FinalWeight_i,t - CurrentWeight_i,t| < RebalanceThreshold，则不调整该 ETF
```

默认：

```text
RebalanceThreshold = 3%
```

### 12.4 不重新归一化

应用 RSRS、拥挤度、组合波动率、最小有效仓位等规则之后，不把剩余资产重新放大到满仓。

错误做法：

```text
FinalWeight_i = FinalWeight_i / Σ FinalWeight_i
```

正确做法：

```text
剩余仓位保留现金或低风险资产。
```

---

## 13. 特殊情况处理

### 13.1 没有资产通过趋势门槛

如果所有 ETF 的：

```text
TrendGate_i,t = 0
```

则：

```text
全部空仓，资金保留为现金或低风险资产。
```

### 13.2 只有一只资产通过趋势门槛

如果只有一只 ETF 通过趋势门槛，则该 ETF 入选：

```text
RPWeight = 1
```

但仍然需要经过：

```text
RSRSMultiplier
CrowdPenalty
PortfolioVolScale
```

最终仓位不一定是 100%。

### 13.3 历史数据不足

建议最低数据要求：

| 模块 | 最低数据要求 | 推荐数据长度 |
|---|---:|---:|
| 趋势门槛 | 120日 | 120日以上 |
| 动量排序 | 120日 | 120日以上 |
| 风险平价 | 60日 | 60日以上 |
| RSRS回归 | 18日 | 18日以上 |
| RSRS标准化 | 250日 | 600日 |
| 拥挤度分位 | 250日 | 500日 |
| 组合波动率 | 60日 | 60日以上 |

历史数据不足的资产，初版建议暂不纳入策略。

---

## 14. 全部可调参数列表

以下参数是本策略实现时的主要可调参数。初版建议使用默认值，不要同时优化过多参数。

### 14.1 资产池参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 资产池 | `AssetPool` | AI ETF、纳指 ETF、黄金 ETF | 3 到 8 只 ETF | 资产数量不宜过多，优先选择高流动性 ETF |
| 入选数量 | `TopK` | 2 | 1 到 3 | 动量排序后最终入选数量 |

### 14.2 趋势参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 长期均线窗口 | `MA_long` | 120 | 100 到 150 | 用于趋势门槛 |

### 14.3 动量参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 短期动量窗口 | `MomShort` | 20 | 10 到 30 | 反映短期强弱 |
| 中期动量窗口 | `MomMid` | 60 | 40 到 80 | 反映中短期趋势 |
| 长期动量窗口 | `MomLong` | 120 | 100 到 150 | 反映中期主趋势 |
| 短期动量权重 | `w20` | 0.2 | 0.1 到 0.3 | 三个动量权重之和应为 1 |
| 中期动量权重 | `w60` | 0.3 | 0.2 到 0.4 | 三个动量权重之和应为 1 |
| 长期动量权重 | `w120` | 0.5 | 0.4 到 0.6 | 三个动量权重之和应为 1 |
| 动量打分方式 | `MomentumMode` | 排名分数 | 排名分数 / 原始收益率 / 风险调整收益率 | 初版推荐排名分数 |

### 14.4 风险平价参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 波动率估计窗口 | `VolWindow` | 60 | 40 到 120 | 用于逆波动率风险平价 |
| 风险平价方式 | `RPMode` | 逆波动率 | 逆波动率 / 协方差风险平价 | 初版推荐逆波动率 |

### 14.5 RSRS 参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| RSRS回归窗口 | `RSRS_N` | 18 | 16 到 24 | High 对 Low 回归的窗口 |
| RSRS标准化窗口 | `RSRS_M` | 600 | 250 到 750 | β 序列标准化窗口 |
| RSRS满额减仓阈值 | `RSRS_NegativeFullCut` | 1.0 | 0.7 到 1.5 | `RSRS_Adj ≤ -该值` 时乘数降为 0 |
| RSRS乘数下限 | `RSRSMinMultiplier` | 0.0 | 0 到 0.3 | 初版推荐 0 |
| RSRS乘数上限 | `RSRSMaxMultiplier` | 1.0 | 1.0 到 1.1 | 初版推荐 1.0，即只减不加 |

### 14.6 拥挤度参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 拥挤度分位窗口 | `CrowdWindow` | 500 | 250 到 750 | 用于计算各拥挤度指标分位数 |
| 短期涨幅窗口 | `CrowdRetShort` | 20 | 10 到 30 | 拥挤度指标之一 |
| 中期涨幅窗口 | `CrowdRetMid` | 60 | 40 到 80 | 拥挤度指标之一 |
| 成交额均值窗口 | `AmountMAWindow` | 20 | 10 到 30 | 用于成交额分位数 |
| 均线偏离窗口 | `DeviationMAWindow` | 20 | 10 到 30 | 用于计算偏离 MA 的程度 |
| 短期波动率窗口 | `CrowdVolWindow` | 20 | 10 到 30 | 用于波动率分位数 |
| 拥挤惩罚起点 | `CrowdStart` | 0.60 | 0.55 到 0.70 | 低于该值不惩罚 |
| 拥挤惩罚终点 | `CrowdEnd` | 0.95 | 0.90 到 0.98 | 高于该值惩罚到最低 |
| 最低拥挤惩罚乘数 | `MinCrowdPenalty` | 0.30 | 0.20 到 0.50 | 极度拥挤时最低保留仓位比例 |

### 14.7 组合波动率控制参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 组合波动率窗口 | `PortfolioVolWindow` | 60 | 40 到 120 | 用于估计协方差矩阵 |
| 目标年化波动率 | `TargetVol` | 12% | 10% 到 15% | 控制组合总风险 |
| 波动率缩放上限 | `MaxPortfolioVolScale` | 1.0 | 固定 1.0 | 不使用杠杆 |
| 波动率缩放下限 | `MinPortfolioVolScale` | 无 | 0 到 0.3 | 可不设；若设则避免极端低仓位 |

### 14.8 仓位与交易约束参数

| 参数 | 符号 | 默认值 | 建议范围 | 说明 |
|---|---:|---:|---:|---|
| 单资产最大仓位 | `MaxWeight` | 60% | 40% 到 70% | 避免单 ETF 过度集中 |
| 最小有效仓位 | `MinWeight` | 5% | 3% 到 8% | 低于该值可设为 0 |
| 最小调仓阈值 | `RebalanceThreshold` | 3% | 2% 到 5% | 降低换手 |
| 总仓位上限 | `MaxTotalWeight` | 100% | 固定 100% | 不使用杠杆 |
| 调仓频率 | `RebalanceFreq` | 周频 | 周频 / 双周 / 月频 | 初版推荐周频 |

---

## 15. 推荐初始参数组合

初版建议直接使用以下参数，不要过度优化：

```text
AssetPool = [AI ETF, 纳斯达克100 ETF, 黄金 ETF]
TopK = 2

MA_long = 120

MomShort = 20
MomMid = 60
MomLong = 120
w20 = 0.2
w60 = 0.3
w120 = 0.5
MomentumMode = 排名分数

VolWindow = 60
RPMode = 逆波动率

RSRS_N = 18
RSRS_M = 600
RSRS_NegativeFullCut = 1.0
RSRSMinMultiplier = 0.0
RSRSMaxMultiplier = 1.0

CrowdWindow = 500
CrowdRetShort = 20
CrowdRetMid = 60
AmountMAWindow = 20
DeviationMAWindow = 20
CrowdVolWindow = 20
CrowdStart = 0.60
CrowdEnd = 0.95
MinCrowdPenalty = 0.30

PortfolioVolWindow = 60
TargetVol = 12%
MaxPortfolioVolScale = 1.0
MinPortfolioVolScale = 不设

MaxWeight = 60%
MinWeight = 5%
RebalanceThreshold = 3%
MaxTotalWeight = 100%
RebalanceFreq = 周频
```

---

## 16. 完整计算示例

假设资产池为：

```text
AI ETF
纳斯达克100 ETF
黄金 ETF
```

某调仓日趋势门槛和动量排序后，入选：

```text
AI ETF
纳斯达克100 ETF
```

### 16.1 风险平价

过去 60 日年化波动率：

| ETF | 年化波动率 |
|---|---:|
| AI ETF | 30% |
| 纳斯达克100 ETF | 20% |

逆波动率：

```text
AI ETF = 1 / 30% = 3.333
纳斯达克100 ETF = 1 / 20% = 5.000
```

基础权重：

```text
AI ETF RPWeight = 3.333 / (3.333 + 5.000) = 40%
纳斯达克100 ETF RPWeight = 5.000 / (3.333 + 5.000) = 60%
```

### 16.2 RSRS 线性修正

假设：

| ETF | RSRS_Adj | RSRSMultiplier |
|---|---:|---:|
| AI ETF | -0.20 | `clip(1 - 0.20, 0, 1) = 0.80` |
| 纳斯达克100 ETF | 0.30 | `clip(1 + 0.30, 0, 1) = 1.00` |

### 16.3 拥挤度线性惩罚

假设：

| ETF | CrowdingScore | CrowdPenalty |
|---|---:|---:|
| AI ETF | 0.85 | 0.50 |
| 纳斯达克100 ETF | 0.70 | 0.80 |

### 16.4 RawWeight

```text
AI RawWeight
= 40% × 1 × 0.80 × 0.50
= 16.0%
```

```text
纳斯达克100 RawWeight
= 60% × 1 × 1.00 × 0.80
= 48.0%
```

调整前总仓位：

```text
RawTotalWeight = 64.0%
```

### 16.5 组合波动率控制

假设根据 `RawWeight` 和协方差矩阵计算得到：

```text
PortfolioVol = 15%
```

目标年化波动率：

```text
TargetVol = 12%
```

则：

```text
PortfolioVolScale = min(1, 12% / 15%) = 0.8
```

最终仓位：

```text
AI FinalWeight = 16.0% × 0.8 = 12.8%
纳斯达克100 FinalWeight = 48.0% × 0.8 = 38.4%
```

最终总仓位：

```text
TotalWeight = 51.2%
```

现金或低风险资产：

```text
CashWeight = 48.8%
```

此时不应把 51.2% 重新归一化到 100%。

---

## 17. 策略定稿摘要

本方案最终定稿为：

```text
趋势硬过滤
+ 多周期排名动量选 TopK
+ 逆波动率风险平价分基础权重
+ RSRS 截断线性减仓
+ 拥挤度截断线性惩罚
+ 组合波动率连续缩放
+ 最终仓位不重新归一化
```

最终公式：

```text
FinalWeight_i,t
= RPWeight_i,t
× TrendGate_i,t
× RSRSMultiplier_i,t
× CrowdPenalty_i,t
× PortfolioVolScale_t
```

本方案保留必要的离散边界：

```text
趋势门槛：0 / 1
TopK选择：离散入选
```

同时将核心仓位修正模块改为线性：

```text
RSRS：截断线性乘数
拥挤度：截断线性惩罚
组合波动率：连续缩放
```

这样可以在保持策略逻辑清晰的同时，减少仓位跳变，提高实盘执行的平滑性。
