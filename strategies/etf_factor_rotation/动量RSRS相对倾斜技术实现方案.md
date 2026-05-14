# 动量与 RSRS 相对倾斜技术实现方案

设计日期：2026-05-14  
适用策略：[etf_factor_rotation.py](etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->  
原技术方案：[ETF轮动策略技术实现方案.md](ETF轮动策略技术实现方案.md) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/ETF轮动策略技术实现方案.md -->  
原方案说明：[ETF轮动策略方案说明书.md](ETF轮动策略方案说明书.md) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/ETF轮动策略方案说明书.md -->  
测试文件：[test_etf_factor_rotation.py](tests/test_etf_factor_rotation.py) <!-- pathref: strategy_tests(strategy=etf_factor_rotation)/test_etf_factor_rotation.py -->  

## 1. 文档目标

本文是针对 `etf_factor_rotation` 的专项技术改造方案，目标是把动量与 RSRS 从原来的“筛选 / 加减仓信号”改造成“资产间相对倾斜信号”。

改造后的模块职责如下：

| 模块 | 职责 | 是否改变组合总仓位 |
|---|---|---|
| 趋势门槛 | 判断资产能不能参与配置 | 是，趋势不成立则该资产权重为 0 |
| 风险平价 | 在趋势成立资产之间生成基础权重 | 否，基础权重内部归一化 |
| 动量倾斜 | 按相对动量强弱调整资产间权重 | 否，倾斜后重新归一化 |
| RSRS 倾斜 | 按价格结构强弱调整资产间权重 | 否，倾斜后重新归一化 |
| 拥挤度惩罚 | 对过热资产进行仓位打折 | 是，打折后不重新归一化 |
| 组合波动率 | 当组合波动率超目标时整体缩仓 | 是，整体缩放后不重新归一化 |
| 交易约束 | 应用单资产、最小有效仓位和总仓位兜底 | 是，约束后不重新归一化 |

核心原则：动量和 RSRS 只回答“谁相对更多、谁相对更少”，不回答“组合整体要不要满仓”。整体仓位控制交给趋势门槛、拥挤度惩罚、组合波动率和交易约束。

## 2. 改造前后流程

### 2.1 改造前

当前主流程是：

```text
TrendGate
-> MomentumScore
-> TopK Selected
-> RPWeight
-> RSRSMultiplier
-> CrowdPenalty
-> PortfolioVolScale
-> FinalWeight
```

其含义是：

- 动量先做 TopK 硬筛选，决定哪些资产参与风险平价。
- 风险平价只对 TopK 入选资产分配基础权重。
- RSRS 以乘数形式直接影响单资产权重，可能提高或降低组合总仓位。
- 拥挤度和组合波动率继续做仓位打折。

### 2.2 改造后

目标流程调整为：

```text
TrendGate
-> RPWeight
-> MomentumScore
-> MomentumTilt
-> RSRSTilt
-> TiltedWeight
-> CrowdPenalty
-> PortfolioVolScale
-> FinalWeight
```

核心变化：

- `TopK` 不再决定买谁。
- 所有趋势成立资产都参与风险平价基础权重计算。
- 动量不再硬筛选资产，只生成相对倾斜乘数。
- RSRS 不再直接改变组合总仓位，只生成相对倾斜乘数。
- 动量和 RSRS 倾斜合成后必须重新归一化。
- 拥挤度惩罚和组合波动率缩放后不重新归一化，剩余仓位保留为现金。

## 3. 参数设计

新增参数写入 `set_parameter()`，并同步进入 `snapshot_params()` 与 `validate_params()`。

| 参数 | 默认值 | 含义 | 调大影响 |
|---|---:|---|---|
| `MomentumTiltStrength` | `0.50` | 动量分数对倾斜乘数的影响强度 | 更偏向强动量资产 |
| `MomentumTiltMin` | `0.70` | 动量弱资产的最低倾斜乘数 | 弱动量资产更不容易被压低 |
| `MomentumTiltMax` | `1.30` | 动量强资产的最高倾斜乘数 | 强动量资产可获得更高相对权重 |
| `RSRSTiltMin` | `0.70` | RSRS 弱资产的最低倾斜乘数 | 结构弱资产更不容易被压低 |
| `RSRSTiltMax` | `1.30` | RSRS 强资产的最高倾斜乘数 | 结构强资产可获得更高相对权重 |

参数校验规则：

```text
MomentumTiltStrength >= 0
0 < MomentumTiltMin <= 1 <= MomentumTiltMax
0 < RSRSTiltMin <= 1 <= RSRSTiltMax
```

保留参数：

- `TopK` 暂时保留在参数快照和校验中，兼容已有参数扫描与测试，但不参与新主流程。
- `RSRS_NegativeFullCut` 继续作为 RSRS 原始信号到倾斜乘数的缩放分母，避免新增过多参数。
- `RSRSMinMultiplier`、`RSRSMaxMultiplier` 若短期保留，仅用于兼容旧函数或旧测试，不再参与新主流程。

## 4. 核心公式

### 4.1 活跃资产集合

只把趋势成立资产视为活跃资产：

```text
Active_i = TrendGate_i > 0
```

趋势不成立资产在风险平价、动量倾斜、RSRS 倾斜和最终权重中都保持为 0。

### 4.2 风险平价基础权重

风险平价仍使用逆波动率模型：

```text
RPWeight_i = inverse_vol_i / sum(inverse_vol_active)
```

其中：

```text
inverse_vol_i = 1 / annualized_vol_i
```

边界处理：

- 无活跃资产时返回全 0。
- 单个活跃资产时该资产权重为 1。
- 数据缺失或收益样本不足时沿用现有退化逻辑。

### 4.3 动量倾斜乘数

继续使用现有多周期排名动量分数：

```text
MomentumScore_i = w20 * rank(ret20_i)
                + w60 * rank(ret60_i)
                + w120 * rank(ret120_i)
```

再把动量分数转换为相对倾斜乘数：

```text
momentum_edge_i = MomentumScore_i - mean(MomentumScore_active)

MomentumTilt_i = clip(
    1 + MomentumTiltStrength * momentum_edge_i,
    MomentumTiltMin,
    MomentumTiltMax
)
```

边界处理：

- 无活跃资产时返回全 0。
- 活跃资产但动量数据不足时，现有 `MomentumScore` 为 0，所有活跃资产的 `MomentumTilt` 退化为 1。
- 非活跃资产 `MomentumTilt` 记为 0，便于日志识别。

### 4.4 RSRS 倾斜乘数

RSRS 原始结构信号沿用现有计算方式：

```text
RSRSAdj_i = RSRS_Z_i * R2_i
```

其中：

- `RSRS_Z_i` 是最近一期 beta 相对过去 `RSRS_M` 期 beta 的标准化值。
- `R2_i` 是最近一期 High ~ Low 回归的拟合优度。

把 RSRS 原始信号转换为相对倾斜乘数：

```text
rsrs_edge_i = RSRSAdj_i - mean(RSRSAdj_active)

RSRSTilt_i = clip(
    1 + rsrs_edge_i / RSRS_NegativeFullCut,
    RSRSTiltMin,
    RSRSTiltMax
)
```

边界处理：

- 无活跃资产时返回全 0。
- 活跃资产 RSRS 数据不足时，该资产 `RSRSAdj` 退化为 0。
- 如果所有活跃资产 `RSRSAdj` 都退化为 0，则所有活跃资产 `RSRSTilt` 为 1。
- 非活跃资产 `RSRSTilt` 记为 0。

### 4.5 倾斜权重合成与归一化

动量和 RSRS 同时参与相对倾斜：

```text
tilted_raw_i = RPWeight_i * MomentumTilt_i * RSRSTilt_i
```

随后只在活跃资产内部重新归一化，并保持风险平价基础总权重：

```text
base_total = sum(RPWeight_active)
TiltedWeight_i = tilted_raw_i / sum(tilted_raw_active) * base_total
```

通常 `base_total = 1.0`。保留该变量是为了兼容未来风险平价基础权重不是满仓的情形。

边界处理：

- 如果 `sum(tilted_raw_active) <= 0`，退回原始 `RPWeight`。
- 非活跃资产权重保持 0。
- 该步骤不创造现金，也不消耗现金，只改变活跃资产之间的相对比例。

### 4.6 后续仓位控制

拥挤度惩罚直接降低单资产权重：

```text
CrowdAdjustedWeight_i = TiltedWeight_i * CrowdPenalty_i
```

组合波动率缩放直接降低组合整体权重：

```text
FinalWeight_i = CrowdAdjustedWeight_i * PortfolioVolScale
```

这两步不重新归一化，降低后的剩余仓位保留为现金。

## 5. 函数改造

### 5.1 参数函数

调整 `set_parameter()`：

```python
g.MomentumTiltStrength = 0.50
g.MomentumTiltMin = 0.70
g.MomentumTiltMax = 1.30
g.RSRSTiltMin = 0.70
g.RSRSTiltMax = 1.30
```

调整 `snapshot_params()`：

```python
"MomentumTiltStrength": g.MomentumTiltStrength,
"MomentumTiltMin": g.MomentumTiltMin,
"MomentumTiltMax": g.MomentumTiltMax,
"RSRSTiltMin": g.RSRSTiltMin,
"RSRSTiltMax": g.RSRSTiltMax,
```

调整 `validate_params()`：

```python
if params["MomentumTiltStrength"] < 0:
    errors.append("MomentumTiltStrength must be >= 0")
if not (0 < params["MomentumTiltMin"] <= 1 <= params["MomentumTiltMax"]):
    errors.append("Momentum tilt bounds must satisfy 0 < min <= 1 <= max")
if not (0 < params["RSRSTiltMin"] <= 1 <= params["RSRSTiltMax"]):
    errors.append("RSRS tilt bounds must satisfy 0 < min <= 1 <= max")
```

### 5.2 `compute_momentum_tilt_multipliers`

新增函数：

```python
def compute_momentum_tilt_multipliers(momentum_scores, trend_gates, params):
    """
    将动量分数转换为资产间相对倾斜乘数。
    活跃资产围绕均值上下倾斜，非活跃资产返回 0。
    """
```

实现要点：

- 输入使用现有 `compute_momentum_scores()` 的输出。
- 只统计 `trend_gates > 0` 的资产均值。
- 活跃资产使用 `clip(1 + strength * edge, min, max)`。
- 非活跃资产返回 0。

### 5.3 `compute_rsrs_tilt_multipliers`

新增函数：

```python
def compute_rsrs_tilt_multipliers(prices, pool, trend_gates, params):
    """
    计算 RSRS 原始结构信号，并转换为资产间相对倾斜乘数。
    """
```

实现要点：

- 复用现有 `compute_rsrs_multipliers()` 内部的 rolling beta、R2、标准化逻辑。
- 新函数应先得到每只 ETF 的 `RSRSAdj`，再对活跃资产做去均值相对化。
- 数据不足或数值异常时，该资产 `RSRSAdj` 退化为 0。
- 非活跃资产返回 0。

建议实现时可拆出内部辅助函数：

```python
def compute_rsrs_adjusted_scores(prices, pool, params):
    """
    返回 RSRSAdj_i = RSRS_Z_i * R2_i。
    """
```

这样旧 RSRS 乘数函数和新 RSRS 倾斜函数都能复用同一份原始信号计算，减少重复。

### 5.4 `apply_relative_tilts`

新增函数：

```python
def apply_relative_tilts(rp_weights, trend_gates, momentum_tilts, rsrs_tilts):
    """
    将风险平价基础权重、动量倾斜和 RSRS 倾斜合成，并在活跃资产内归一化。
    """
```

实现要点：

- 只处理 `trend_gates > 0` 且 `rp_weights > 0` 的资产。
- `tilted_raw = rp_weights * momentum_tilts * rsrs_tilts`。
- 归一化到 `sum(rp_weights_active)`。
- 若归一化分母无效，则退回 `rp_weights`。

### 5.5 `compose_raw_weights`

调整函数签名：

```python
def compose_raw_weights(tilted_weights, trend_gates, crowd_penalties):
```

调整后公式：

```text
RawWeight_i = TiltedWeight_i * TrendGate_i * CrowdPenalty_i
```

说明：

- 动量与 RSRS 已经体现在 `TiltedWeight` 中，不再作为此函数的独立乘数。
- `TrendGate` 仍保留在合成函数中作为二次保护。
- 不重新归一化。

### 5.6 `weekly_check`

目标编排顺序：

```text
1. get_history_data
2. compute_trend_gates
3. compute_rp_weights(prices, pool, active_mask, params)
4. compute_momentum_scores
5. compute_momentum_tilt_multipliers
6. compute_rsrs_tilt_multipliers
7. apply_relative_tilts
8. compute_crowd_penalties
9. compose_raw_weights
10. compute_portfolio_vol_scale
11. apply_weight_constraints
12. execute_rebalance
```

其中 `active_mask` 可由趋势门槛生成：

```python
active_mask = [gate > 0 for gate in trend_gates]
```

`select_topk()` 暂时不在主流程中调用。

### 5.7 `apply_weight_constraints`

建议补齐 `MaxTotalWeight` 总仓位约束：

```text
if sum(result) > MaxTotalWeight:
    result = result * MaxTotalWeight / sum(result)
```

该缩放应放在单资产 `MaxWeight` 与 `MinWeight` 处理之后。缩放后如果再次出现低于 `MinWeight` 的资产，可在首版不做二次裁剪，避免引入循环；如需更严格，可另行设计迭代约束。

## 6. 日志设计

建议 `weekly_check()` 输出以下模块级日志：

```text
TrendGate
RPWeight
MomentumScore
MomentumTilt
RSRSTilt
TiltedWeight
CrowdPenalty
PortfolioVolScale
FinalWeight
```

日志含义：

| 日志 | 含义 |
|---|---|
| `TrendGate` | 是否通过趋势硬过滤 |
| `RPWeight` | 倾斜前的风险平价基础权重 |
| `MomentumScore` | 现有多周期排名动量分数 |
| `MomentumTilt` | 动量相对倾斜乘数 |
| `RSRSTilt` | RSRS 相对倾斜乘数 |
| `TiltedWeight` | 动量与 RSRS 倾斜后重新归一化的权重 |
| `CrowdPenalty` | 拥挤度惩罚乘数 |
| `PortfolioVolScale` | 组合层面波动率缩放 |
| `FinalWeight` | 交易约束前的最终目标仓位 |

不再输出 `Selected` 作为主流程日志。若保留 `select_topk()` 的兼容测试，不代表主流程仍使用 TopK。

## 7. 测试方案

### 7.1 参数测试

新增或更新：

- `snapshot_params()` 包含 5 个新增倾斜参数。
- 默认参数通过 `validate_params()`。
- `MomentumTiltStrength < 0` 抛出错误。
- `MomentumTiltMin <= 0`、`MomentumTiltMin > 1`、`MomentumTiltMax < 1` 抛出错误。
- `RSRSTiltMin <= 0`、`RSRSTiltMin > 1`、`RSRSTiltMax < 1` 抛出错误。

### 7.2 动量倾斜测试

覆盖场景：

- 动量强资产 `MomentumTilt > 1`。
- 动量弱资产 `MomentumTilt < 1`。
- 动量等于活跃资产均值时 `MomentumTilt == 1`。
- 非活跃资产 `MomentumTilt == 0`。
- 无活跃资产返回全 0。
- 极端动量差异被 `MomentumTiltMin` / `MomentumTiltMax` 截断。

### 7.3 RSRS 倾斜测试

覆盖场景：

- RSRS 强资产 `RSRSTilt > 1`。
- RSRS 弱资产 `RSRSTilt < 1`。
- 所有活跃资产 RSRS 原始信号相同，则倾斜乘数为 1。
- 非活跃资产 `RSRSTilt == 0`。
- 数据不足时活跃资产退化为中性倾斜。
- 极端 RSRS 差异被 `RSRSTiltMin` / `RSRSTiltMax` 截断。

### 7.4 倾斜合成测试

覆盖场景：

- 动量与 RSRS 都为中性乘数时，`TiltedWeight == RPWeight`。
- 倾斜后活跃资产权重合计等于原始 `sum(RPWeight_active)`。
- 趋势不成立资产权重保持 0。
- `tilted_raw` 分母为 0 时回退原始 `RPWeight`。
- 强动量或强 RSRS 资产倾斜后相对权重上升。

### 7.5 主流程集成测试

更新 `weekly_check` 集成测试：

- 日志应包含 `MomentumTilt`、`RSRSTilt`、`TiltedWeight`。
- 日志不再要求 `Selected` 必须出现。
- 全部趋势失败时，不下单或只执行清仓逻辑。
- 正常上涨数据下至少有一只 ETF 产生正目标仓位。

### 7.6 仓位控制测试

保留并补充：

- 拥挤度惩罚后总仓位可以低于 1。
- 组合波动率超目标时 `PortfolioVolScale < 1`。
- `MaxWeight` 能限制单资产仓位。
- `MinWeight` 能裁剪低于最小有效仓位的资产。
- `MaxTotalWeight` 能限制最终总仓位。

## 8. 验证命令

本地只做语法和单元测试，不执行完整策略回测：

```powershell
.\.venv\Scripts\python.exe -m py_compile strategies\etf_factor_rotation\etf_factor_rotation.py
.\.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests -q
.\.venv\Scripts\python.exe -m scripts.path_tools.refactor check
```

说明：

- 聚宽策略完整运行必须在云端回测环境中完成。
- 本地测试使用 mock 数据验证纯函数、参数校验和主流程编排。
- 若本地通过，应再用 `scripts.jq_automation compile-check` 做云端编译检查。

## 9. 兼容与迁移

### 9.1 对旧参数的兼容

短期保留：

- `TopK`
- `select_topk()`
- `RSRSMinMultiplier`
- `RSRSMaxMultiplier`
- `compute_rsrs_multipliers()`

保留原因：

- 减少一次性删除带来的测试和参数扫描影响。
- 便于和旧回测结果做 A/B 对比。
- 后续确认新方案稳定后，再单独清理旧接口。

### 9.2 对旧报告的影响

旧报告中关于“动量选择 TopK”和“RSRS 乘数可加可减仓”的描述不再适用于新主流程。实现完成后，应同步更新：

- [ETF轮动策略方案说明书.md](ETF轮动策略方案说明书.md) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/ETF轮动策略方案说明书.md -->
- [ETF轮动策略技术实现方案.md](ETF轮动策略技术实现方案.md) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/ETF轮动策略技术实现方案.md -->
- [测试方案设计文档.md](tests/测试方案设计文档.md) <!-- pathref: strategy_tests(strategy=etf_factor_rotation)/测试方案设计文档.md -->

本文件作为专项改造方案，优先指导代码实现。

## 10. 风险与注意事项

| 风险 | 说明 | 控制方式 |
|---|---|---|
| 相对倾斜无法整体避险 | 如果所有资产 RSRS 都差，RSRS 仍会把仓位分给相对没那么差的资产 | 由趋势门槛、拥挤度和组合波动率负责整体降仓 |
| 三资产池中倾斜较敏感 | 资产数量少，强弱差异会更直接反映到权重 | 使用 `TiltMin` / `TiltMax` 限制极端倾斜 |
| 动量与 RSRS 同向强化 | 两个相对信号可能同时偏向同一资产 | 用倾斜上限、`MaxWeight` 和 `MaxTotalWeight` 兜底 |
| 旧测试依赖 `Selected` 日志 | 主流程移除 TopK 后集成测试需要更新 | 测试改为验证 `MomentumTilt` 和 `TiltedWeight` |
| 旧文档口径不一致 | 旧方案仍描述 TopK 和 RSRS 加减仓 | 实现后同步更新主说明文档 |

## 11. 完成标准

代码实现完成后，应满足：

- 动量与 RSRS 不再直接改变组合总仓位。
- 倾斜后活跃资产权重在内部重新归一化。
- 趋势不成立资产权重始终为 0。
- 拥挤度和组合波动率仍可降低总仓位。
- 新增参数已进入参数快照和参数校验。
- 单元测试覆盖新增函数和主流程日志。
- 本地语法检查、单元测试、路径引用校验通过。
- 云端编译检查通过。
