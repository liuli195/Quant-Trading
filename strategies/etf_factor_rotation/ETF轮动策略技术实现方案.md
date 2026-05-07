# ETF 轮动策略技术实现方案

设计日期：2026-05-05  
适用策略：[etf_factor_rotation.py](etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->  
业务方案依据：[ETF轮动策略方案说明书.md](ETF轮动策略方案说明书.md) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/ETF轮动策略方案说明书.md -->  
测试方案依据：[测试方案设计文档.md](tests/测试方案设计文档.md) <!-- pathref: strategy_tests(strategy=etf_factor_rotation)/测试方案设计文档.md -->  
聚宽 API 依据：[joinquant-api.md](../../docs/joinquant-api.md) <!-- pathref: docs/joinquant-api.md -->  
聚宽数据字典依据：[JQ_场内基金数据.md](../../docs/joinquant-data/JQ_场内基金数据.md) <!-- pathref: joinquant_data/JQ_场内基金数据.md -->

## 1. 文档目标

本文是一份面向落地开发的技术实现方案，不讨论策略收益优劣，不做参数优化结论。

核心目标：

| 目标 | 含义 | 技术落点 |
|---|---|---|
| 解耦 | 聚宽 API、策略计算、交易执行互不污染 | 数据适配层隔离 API；核心计算函数纯函数化；执行层集中下单 |
| 扩展性 | 后续可以扩资产池、加因子、替换权重模型 | 固定模块接口；新增模块只接入 Gate / Selector / Allocator / Multiplier 中一种 |
| 性能 | 在聚宽云端长周期回测可稳定运行 | 批量取数、单次调仓 4 次行情 API、向量化 rolling、单次调仓内缓存 |

约束条件：

- 策略运行环境是聚宽云端，本地不能完整执行真实交易和回测。
- 策略代码优先保持单文件上传形态，降低聚宽云端部署风险。
- 本地主要承担语法检查、单元测试、mock 集成测试、文档和回测结果分析。
- 场内基金复权口径、聚宽真实返回结构、云端性能必须通过云端短回测确认。

非目标：

- 不在本文中设计参数寻优流程。
- 不把双均线交叉、最大回撤止损、单 ETF 波动率惩罚纳入当前主方案。
- 不把策略拆成依赖本地包的多文件运行形态，除非后续确认聚宽上传流程可稳定支持。

## 2. 总体架构

策略采用“单文件、强分层、窄接口”的实现方式。

```text
聚宽生命周期
  initialize(context)
    -> 参数初始化
    -> 交易环境设置
    -> 周频任务注册

调仓编排层
  weekly_check(context)
    -> 读取参数快照
    -> 构造行情快照
    -> 执行信号模块
    -> 执行权重模块
    -> 执行交易模块
    -> 输出审计日志

数据适配层
  fetch_field()
  normalize_field_frame()
  get_history_data()

核心计算层
  compute_trend_gates()
  compute_momentum_scores()
  select_topk()
  compute_rp_weights()
  compute_rsrs_multipliers()
  compute_crowd_penalties()
  compute_portfolio_vol_scale()
  apply_weight_constraints()

交易执行层
  build_rebalance_plan()
  execute_rebalance()
```

分层原则：

| 层 | 允许做什么 | 禁止做什么 |
|---|---|---|
| 生命周期层 | 调用聚宽初始化 API、注册任务 | 写策略计算细节 |
| 编排层 | 串联模块、记录模块级日志 | 直接写复杂指标公式 |
| 数据适配层 | 调用 `get_price`、清洗返回结构 | 下单、计算最终权重 |
| 核心计算层 | 基于 DataFrame / ndarray 计算信号和权重 | 调用聚宽 API、写日志、改 `g` |
| 执行层 | 读取 `get_current_data`、生成订单、记录下单结果 | 修改信号和权重 |

## 3. 文件与文档结构

当前阶段保持以下结构：

```text
strategies/etf_factor_rotation/
  etf_factor_rotation.py
  ETF轮动策略方案说明书.md
  ETF轮动策略技术实现方案.md
  tests/
    conftest.py
    test_etf_factor_rotation.py
    测试方案设计文档.md
  reports/
    2026-05-05-code-review.md
    2026-05-05-technical-design-review.md
  backtest_runs/
    <run_id>/
      report/
        backtest_report.md
        strategy-analysis.md
        performance-analysis.md
```

说明：

- `ETF轮动策略方案说明书.md` 描述业务逻辑和公式。
- `ETF轮动策略技术实现方案.md` 描述代码如何实现、如何解耦、如何扩展、如何保证性能。
- `tests/测试方案设计文档.md` 描述本地和云端测试矩阵。
- `reports/` 放评审、分析和专题报告，不作为主方案入口。

## 4. 核心数据结构

为兼容聚宽单文件运行，首版不强制使用 `dataclass`，可以用 dict 或 `SimpleNamespace` 表达结构。但所有结构必须有清晰契约。

### 4.1 参数快照 `Params`

目标：把 `g` 中的运行参数复制成只读快照，减少核心函数直接读取全局变量。

建议函数：

```python
def snapshot_params():
    return {
        "etf_pool": list(g.etf_pool),
        "etf_names": list(g.etf_names),
        "MA_long": g.MA_long,
        "MomShort": g.MomShort,
        "MomMid": g.MomMid,
        "MomLong": g.MomLong,
        "w20": g.w20,
        "w60": g.w60,
        "w120": g.w120,
        "TopK": g.TopK,
        ...
    }
```

参数类别：

| 类别 | 参数 |
|---|---|
| 资产池 | `etf_pool`、`etf_names`、`benchmark` |
| 趋势 | `MA_long` |
| 动量 | `MomShort`、`MomMid`、`MomLong`、`w20`、`w60`、`w120`、`TopK` |
| 风险平价 | `VolWindow`、`annual_factor` |
| RSRS | `RSRS_N`、`RSRS_M`、`RSRS_NegativeFullCut`、`RSRSMinMultiplier`、`RSRSMaxMultiplier` |
| 拥挤度 | `CrowdWindow`、`CrowdRetShort`、`CrowdRetMid`、`AmountMAWindow`、`DeviationMAWindow`、`CrowdVolWindow`、`CrowdStart`、`CrowdEnd`、`MinCrowdPenalty` |
| 组合波动率 | `PortfolioVolWindow`、`TargetVol`、`MaxPortfolioVolScale` |
| 交易约束 | `MaxWeight`、`MinWeight`、`RebalanceThreshold`、`MaxTotalWeight` |
| 数据口径 | `use_real_price`、`fq_mode`、`history_buffer` |

参数校验：

| 校验项 | 规则 |
|---|---|
| 动量权重 | `w20 + w60 + w120 == 1` |
| TopK | `1 <= TopK <= len(etf_pool)`，超过时按活跃资产数量截断 |
| 仓位上限 | `0 < MaxWeight <= MaxTotalWeight <= 1` |
| 最小仓位 | `0 <= MinWeight <= MaxWeight` |
| 波动目标 | `TargetVol > 0` |
| RSRS 窗口 | `RSRS_M > 0` 且 `RSRS_N > 1` |
| 拥挤阈值 | `0 <= CrowdStart < CrowdEnd <= 1` |

### 4.2 行情快照 `MarketSnapshot`

`get_history_data()` 返回行情快照。首版可继续使用 dict，但 key 必须固定：

| key | 聚宽字段 | 数据形态 | 用途 |
|---|---|---|---|
| `close` | `close` | DataFrame，index=日期，columns=ETF 代码 | 趋势、动量、收益率、拥挤度 |
| `high` | `high` | DataFrame，index=日期，columns=ETF 代码 | RSRS |
| `low` | `low` | DataFrame，index=日期，columns=ETF 代码 | RSRS |
| `amount` | `money` | DataFrame，index=日期，columns=ETF 代码 | 拥挤度成交额 |
| `close_ret` | 由 `close.pct_change()` 生成 | DataFrame，index=日期，columns=ETF 代码 | 风险平价、组合波动率 |

行情快照约束：

- 所有 DataFrame columns 必须至少按 `etf_pool` 重新索引，缺失 ETF 保留为全 NaN 列。
- 每个字段可以有不同日期索引，但跨资产协方差必须在使用前做共同日期对齐。
- 空数据返回空 DataFrame，不抛异常；下游模块负责安全降级。
- 单次调仓内复用快照，不重复调用 API。
- 不跨调仓日缓存快照。聚宽文档说明动态复权模式下不同日期看到的前复权价格可能不同。

### 4.3 模块输出 `SignalBundle`

建议在 `weekly_check()` 中维护一个中间结果字典，便于日志和调试：

```python
signals = {
    "TrendGate": trend_gates,
    "MomentumScore": momentum_scores,
    "Selected": selected_as_float,
    "RPWeight": rp_weights,
    "RSRSMultiplier": rsrs_multipliers,
    "CrowdPenalty": crowd_penalties,
    "RawWeight": raw_weights,
    "PortfolioVolScale": portfolio_vol_scale,
    "FinalWeight": final_weights,
}
```

约束：

- 所有数组长度必须等于 `len(etf_pool)`。
- 所有数组顺序必须与 `etf_pool` 一致。
- 所有模块输出必须是数值型、布尔型或可转为数值型，方便日志和测试断言。

### 4.4 调仓计划 `RebalancePlan`

执行层可先生成调仓计划，再逐项下单。

计划字段：

| 字段 | 含义 |
|---|---|
| `security` | ETF 代码 |
| `target_weight` | 目标权重 |
| `current_weight` | 当前权重 |
| `target_value` | 目标市值 |
| `current_value` | 当前市值 |
| `delta_weight` | 目标权重与当前权重差 |
| `action` | `skip` / `order` |
| `reason` | 跳过或下单原因 |

这样做的好处：

- 交易判断可测试，不必直接依赖真实下单。
- 日志更完整。
- 后续加入涨跌停、最小订单金额、成交量比例限制时，不影响信号层。

## 5. 数据适配层设计

### 5.1 聚宽 API 使用原则

当前策略只依赖以下聚宽 API：

| API | 使用位置 | 用途 |
|---|---|---|
| `set_option` | `initialize` | 设置真实价格、避免未来数据 |
| `set_order_cost` | `initialize` | 设置场内基金交易成本 |
| `set_slippage` | `initialize` | 设置滑点 |
| `run_weekly` | `initialize` | 注册周频调仓 |
| `get_price` | `fetch_field` | 获取历史日线行情 |
| `get_current_data` | `execute_rebalance` | 检查停牌、涨跌停等当前状态 |
| `order_target_value` | `execute_rebalance` | 按目标市值调仓 |
| `log.info/warning/error` | 编排层和执行层 | 审计日志 |

`get_price` 固定参数：

```python
get_price(
    pool,
    count=count,
    end_date=context.previous_date,
    frequency="daily",
    fields=[field],
    skip_paused=True,
    fq=params["fq_mode"],
    panel=False,
)
```

设计依据：

- 开盘调仓时显式使用 `context.previous_date`，避免读取当日收盘价。
- 多标的且 `skip_paused=True` 时按聚宽文档要求设置 `panel=False`。
- 按字段整池批量拉取，把默认调仓 API 调用数控制为 4 次。

### 5.2 字段映射

内部字段名和聚宽字段名分离：

| 内部字段 | 聚宽字段 | 说明 |
|---|---|---|
| `close` | `close` | 收盘价 |
| `high` | `high` | 最高价 |
| `low` | `low` | 最低价 |
| `amount` | `money` | 成交额 |

建议常量：

```python
FIELD_MAP = {
    "close": "close",
    "high": "high",
    "low": "low",
    "amount": "money",
}
```

### 5.3 返回结构归一化

新增函数：

```python
def normalize_field_frame(raw, field, pool):
    """
    将 get_price 返回结果归一化为 DataFrame(index=日期, columns=ETF代码)。
    """
```

处理规则：

| raw 形态 | 处理 |
|---|---|
| `None` | 返回 columns=pool 的空 DataFrame |
| 空 DataFrame | 返回 columns=pool 的空 DataFrame |
| 普通宽表，columns 为 ETF | `reindex(columns=pool)` |
| MultiIndex columns，level 包含字段名 | `xs(field, axis=1, level=0)` 后 `reindex(columns=pool)` |
| MultiIndex columns，level 顺序不确定 | 尝试识别包含 `field` 的 level，失败则记录 warning 并返回空表 |
| 缺少部分 ETF 列 | 保留已有列，缺失列补 NaN |

归一化后统一执行：

```python
df = df.reindex(columns=pool)
df = df.dropna(how="all")
```

### 5.4 历史窗口长度

历史数据长度不应写成模糊的 `max_window + 100`，建议改为按模块显式计算。

```python
def compute_history_count(params):
    requirements = [
        params["MA_long"],
        max(params["MomShort"], params["MomMid"], params["MomLong"]) + 1,
        params["VolWindow"] + 1,
        params["RSRS_M"] + params["RSRS_N"] - 1,
        params["CrowdWindow"],
        params["PortfolioVolWindow"] + 1,
    ]
    return max(requirements) + params.get("history_buffer", 50)
```

说明：

- 动量和收益率类计算需要多取 1 日。
- RSRS 至少需要 `RSRS_M + RSRS_N - 1`。
- buffer 用于容忍停牌、缺失值、上市初期数据不足。

### 5.5 日期对齐策略

| 场景 | 对齐策略 |
|---|---|
| 单 ETF 趋势/RSRS/拥挤度 | 按该 ETF 自身有效数据 `dropna()` |
| 横截面动量排名 | 最新日期和过去日期都需要对应 ETF 有值；缺值 ETF 得分降级 |
| 风险平价单 ETF 波动率 | 按该 ETF 自身最近有效收益计算 |
| 组合波动率协方差 | 必须对活跃 ETF 的收益率按共同日期 inner join，再取最近窗口 |

组合波动率建议实现：

```python
active_cols = [pool[i] for i in active_indices]
ret_df = close_ret[active_cols].dropna(how="any").iloc[-vol_window:]
if len(ret_df) < vol_window:
    return 1.0
cov_daily = ret_df.cov().values
```

这样避免不同 ETF 收益率序列日期错位后直接 `np.column_stack(values)`。

## 6. 参数层设计

### 6.1 `initialize(context)`

职责：

1. 调用 `set_parameter(context)`。
2. 调用 `validate_params()`，本地测试中必须覆盖。
3. 设置 `use_real_price`、`avoid_future_data`。
4. 设置交易费用和滑点。
5. 注册 `run_weekly(weekly_check, weekday=1, time="open", reference_security="000300.XSHG")`。

不做：

- 不拉取行情。
- 不计算信号。
- 不做参数优化。

### 6.2 `set_parameter(context)`

职责：

- 只写 `g` 参数。
- 参数命名和方案说明书保持一致。
- 任何默认值调整都必须同步更新方案说明书、测试和回测记录。

### 6.3 `validate_params(params)`

建议新增轻量校验函数：

```python
def validate_params(params):
    errors = []
    if abs(params["w20"] + params["w60"] + params["w120"] - 1.0) > 1e-8:
        errors.append("momentum weights must sum to 1")
    ...
    if errors:
        raise ValueError("; ".join(errors))
```

聚宽云端运行时参数错误应尽早失败，避免悄悄跑出不可解释的结果。

## 7. 核心计算模块设计

所有核心计算函数必须满足：

- 输入只来自 `MarketSnapshot`、`Params`、上游模块输出。
- 输出固定长度，与 `etf_pool` 顺序一致。
- 缺数据时安全降级，不抛出非预期异常。
- 不调用聚宽 API。
- 不写日志。

### 7.1 趋势门槛 `compute_trend_gates`

类型：Gate  
输出：`np.array(float)`，值为 0 或 1。

逻辑：

- 对每只 ETF 取最近 `MA_long` 日收盘价。
- 当前收盘价严格大于均线时通过。
- 数据不足、缺列、全 NaN 时不通过。

扩展点：

- 可增加上市时长过滤。
- 可增加流动性过滤，但流动性过滤建议作为独立 Gate，不写进趋势函数。

### 7.2 动量分数 `compute_momentum_scores`

类型：Selector 前置分数  
输出：`np.array(float)`。

逻辑：

- 仅对 `TrendGate=1` 的 ETF 计算。
- 分别计算 20/60/120 日收益率。
- 在活跃资产截面内做 rank percentile。
- 按 `w20/w60/w120` 加权。
- 未通过趋势门槛的 ETF 分数为 0。

边界：

- 活跃资产为空，全部返回 0。
- 窗口不足，全部返回 0 或该周期贡献 0。
- 同分时允许排序稳定性由 Python sort 决定，但入选数量不得超过 TopK。

### 7.3 TopK 选择 `select_topk`

类型：Selector  
输出：`list[bool]`。

逻辑：

- 只在 `TrendGate=1` 的资产中选择。
- 按动量分数降序取前 `min(TopK, active_count)`。
- 如果全部趋势失效，返回全 False。

### 7.4 风险平价 `compute_rp_weights`

类型：Allocator  
输出：`np.array(float)`，入选资产权重和为 1，未入选为 0。

逻辑：

- 对入选资产取最近 `VolWindow` 日收益率。
- 年化波动率 `std * sqrt(annual_factor)`。
- 逆波动率归一化。
- 极低波动率用 `1e-8` 下限保护。

边界：

- 无入选资产，返回全 0。
- 某 ETF 收益率不足，可给默认波动率或剔除。当前实现使用默认波动率 1.0，后续如扩池需在测试中固定该行为。

### 7.5 RSRS 乘数 `compute_rsrs_multipliers`

类型：Multiplier  
输出：`np.array(float)`，范围 `[RSRSMinMultiplier, RSRSMaxMultiplier]`，默认 `[0,1]`。

逻辑：

- 使用 High~Low 回归的闭式解批量计算滚动 beta。
- 使用最近 `RSRS_M` 个 beta 标准化。
- 使用最近一期 R² 修正。
- 乘数公式只减不加，强势时最多为 1。

性能要求：

- 使用 pandas rolling 的 cov/var，不引入逐日 `np.linalg.lstsq` 循环。
- 单 ETF 循环允许保留，因为资产池较小；扩展到 8 只 ETF 前需跑性能基线。

边界：

- `len(data) < RSRS_M + RSRS_N - 1` 时乘数为 1。
- high/low 缺失或方差过低时乘数为 1。
- 数值异常时不抛异常，退化为 1。

### 7.6 拥挤度惩罚 `compute_crowd_penalties`

类型：Multiplier  
输出：`np.array(float)`，范围 `[MinCrowdPenalty, 1]`。

指标：

| 指标 | 数据来源 | 缺失默认 |
|---|---|---|
| 20 日涨幅分位 | `close` | 0.5 |
| 60 日涨幅分位 | `close` | 0.5 |
| 成交额 MA20 分位 | `amount` / `money` | 0.5 |
| 偏离 MA20 分位 | `close` | 0.5 |
| 20 日波动率分位 | `close_ret` 或 `close.pct_change()` | 0.5 |

逻辑：

- 先在 DataFrame 级别批量算 ret20/ret60/amount_ma/deviation/vol20。
- 再逐 ETF 取最近值和历史序列做分位数。
- 拥挤度低于 `CrowdStart` 不惩罚。
- 高于 `CrowdEnd` 使用 `MinCrowdPenalty`。
- 中间区间线性插值。

### 7.7 权重合成 `compose_raw_weights`

建议新增函数：

```python
def compose_raw_weights(rp_weights, trend_gates, selected, rsrs_multipliers, crowd_penalties):
    raw = np.zeros(len(rp_weights))
    for i in range(len(raw)):
        if selected[i]:
            raw[i] = (
                rp_weights[i]
                * trend_gates[i]
                * rsrs_multipliers[i]
                * crowd_penalties[i]
            )
    return raw
```

目的：

- 从 `weekly_check()` 中拆出权重合成，方便测试。
- 后续新增 Multiplier 时，只修改合成函数或 multiplier 列表。

### 7.8 组合波动率缩放 `compute_portfolio_vol_scale`

类型：Portfolio Multiplier  
输出：`float`，范围 `(0, MaxPortfolioVolScale]`，默认不超过 1。

逻辑：

- 只对 `raw_weight > 0` 的 ETF 计算。
- 收益率按共同日期 inner join。
- 使用最近 `PortfolioVolWindow` 个共同交易日计算协方差矩阵。
- 年化组合波动率超过 `TargetVol` 时按比例缩小。
- 未超过目标时返回 1。

边界：

- 无持仓、数据不足、协方差异常时返回 1。
- 单资产时协方差矩阵必须转为二维矩阵。

### 7.9 仓位约束 `apply_weight_constraints`

输出：最终可执行目标权重。

规则：

1. 单资产权重超过 `MaxWeight` 时裁剪。
2. 单资产权重低于 `MinWeight` 时置 0。
3. 不重新归一化，剩余资金保留现金。
4. 如总权重超过 `MaxTotalWeight`，建议整体等比缩小到 `MaxTotalWeight`。

总仓位兜底建议：

```python
total = result.sum()
if total > params["MaxTotalWeight"] and total > 1e-8:
    result = result / total * params["MaxTotalWeight"]
```

当前主公式中所有乘数都不加仓，理论上总权重不应超过 1；但该兜底能保护未来扩展。

## 8. 交易执行层设计

### 8.1 执行流程

```text
execute_rebalance(context, pool, final_weights, params)
  -> 读取 account_value
  -> 读取 current_data
  -> 逐 ETF 计算 current_weight / target_weight / delta
  -> 生成 RebalancePlan
  -> 跳过无需调仓项
  -> 跳过停牌或不可交易项
  -> 调用 order_target_value
  -> 记录 order 成功或失败
```

### 8.2 下单触发规则

| 场景 | 行为 |
|---|---|
| 目标权重为 0 且当前权重为 0 | 跳过 |
| 权重偏离小于 `RebalanceThreshold` | 跳过 |
| ETF 停牌 | 跳过，warning |
| `current_data` 缺失 | 跳过，warning |
| 下单返回 `None` | error |
| 下单返回 Order | info |

### 8.3 审计日志

编排层日志：

- `TrendGate`
- `MomentumScore`
- `Selected`
- `RPWeight`
- `RSRSMultiplier`
- `CrowdPenalty`
- `RawWeight`
- `PortfolioVolScale`
- `FinalWeight`

执行层日志：

- `skip rebalance: security, reason, target_weight, current_weight`
- `skip paused ETF: security`
- `order failed: security, target_value, target_weight, current_weight`
- `order sent: security, target_value, target_weight, current_weight`

日志原则：

- 调仓日输出模块摘要。
- 不输出逐日 rolling 明细。
- profile/debug 结构日志只在云端冒烟阶段短期开启。

## 9. 扩展性设计

### 9.1 扩展资产池

新增 ETF 的步骤：

1. 在 `g.etf_pool` 和 `g.etf_names` 增加代码和名称。
2. 使用聚宽场内基金数据确认类型为 ETF/LOF，且上市时间满足最长窗口要求。
3. 本地合成数据测试 3/5/8 ETF。
4. 云端短回测验证取数、停牌、成交、日志。
5. 记录性能基线和回测结果。

资产池准入建议：

| 条件 | 要求 |
|---|---|
| 基金类型 | 优先 ETF，高流动 LOF 需单独验证 |
| 上市时长 | 覆盖最长窗口 + buffer |
| 日成交额 | 满足策略资金规模，避免低流动性 |
| 连续交易 | 长期停牌或退市风险低 |
| 资产相关性 | 扩池目标应提高组合分散度 |

### 9.2 新增 Gate

适用：上市时长、成交额、基金类型、可交易状态过滤。

接口：

```python
def compute_liquidity_gate(snapshot, pool, params):
    return np.array([...])  # 0/1
```

接入方式：

```python
trend_gate = compute_trend_gates(...)
liquidity_gate = compute_liquidity_gate(...)
combined_gate = trend_gate * liquidity_gate
```

要求：

- Gate 只能减少候选资产，不能增加仓位。
- Gate 输出必须是 0/1。
- Gate 失败默认取 0，除非明确是非关键数据缺失。

### 9.3 新增 Selector

适用：多因子排名、资产类别配额、相关性过滤。

要求：

- Selector 只决定入选集合，不直接给最终仓位。
- 输出长度等于资产池长度。
- 不改动风险平价和执行层。

### 9.4 新增 Allocator

适用：等权、风险预算、最小方差、目标风险贡献。

接口：

```python
def compute_base_weights(snapshot, pool, params, selected):
    return weights
```

要求：

- 未入选资产权重为 0。
- 入选资产权重和不超过 1。
- 异常时返回全 0 或可解释的保守权重。

### 9.5 新增 Multiplier

适用：流动性折扣、相关性升高折扣、外部风险开关。

接口：

```python
def compute_xxx_multipliers(snapshot, pool, params):
    return np.array([...])  # usually [0, 1]
```

接入方式：

```python
multipliers = [
    rsrs_multipliers,
    crowd_penalties,
    liquidity_penalties,
]
raw = rp_weights * trend_gates * selected_mask
for m in multipliers:
    raw = raw * m
```

要求：

- 默认只减不加，范围 `[0,1]`。
- 如果允许大于 1，必须通过 `MaxTotalWeight` 和 `MaxWeight` 双重兜底。
- 必须补缺失数据、极端值、边界值测试。

## 10. 性能实现方案

### 10.1 API 调用预算

默认 3 ETF、周频调仓：

| API | 次数 | 说明 |
|---|---:|---|
| `get_price` | 4 | `close/high/low/money` 各一次，整池拉取 |
| `get_current_data` | 1 | 每次调仓一次 |
| `order_target_value` | 0 至 N | 只对需要调仓且可交易 ETF 调用 |

硬性性能目标：

- 默认参数下，`weekly_check()` 中 `get_price` 调用次数保持 4。
- 扩展资产池不应增加 `get_price` 调用次数，只增加 DataFrame 列数。
- 新增数据字段必须说明是否会增加 API 调用。

### 10.2 计算复杂度

| 模块 | 复杂度 | 优化方式 |
|---|---|---|
| 趋势 | O(N * W) | 只取末尾窗口 |
| 动量 | O(N * K) | DataFrame 批量收益率 + rank |
| 风险平价 | O(N * W) | 复用 `close_ret` |
| RSRS | O(N * W) | rolling cov/var，避免逐日回归 |
| 拥挤度 | O(N * W) | DataFrame 级 rolling |
| 组合波动率 | O(N^2 * W) | 只对持仓资产计算 |
| 执行 | O(N) | 只对偏离超过阈值的资产下单 |

N 为 ETF 数量，W 为窗口长度。

### 10.3 缓存策略

允许：

- 单次 `weekly_check()` 内复用 `MarketSnapshot`。
- 单次 `weekly_check()` 内复用 `close_ret`。
- 单次 `weekly_check()` 内复用中间信号用于日志。

禁止：

- 跨交易日缓存 `get_price` 返回值。
- 在 `g` 中存放历史行情 DataFrame 作为长期缓存。
- 为了少算 rolling 而牺牲复权口径正确性。

原因：聚宽文档说明开启真实价格后，数据获取 API 返回的是基于当天日期的前复权价格，不同日期看到的历史前复权序列可能不同。

### 10.4 性能基线

本地指标：

| 指标 | 默认目标 |
|---|---|
| `get_price_call_count` | 4 |
| `weekly_check_seconds` | 记录基线，后续增加超过 50% 需解释 |
| `rsrs_seconds` | 记录基线，后续增加超过 50% 需解释 |
| `crowd_seconds` | 记录基线，后续增加超过 50% 需解释 |
| `pytest_total_seconds` | 记录基线，后续增加超过 50% 需解释 |

云端指标：

| 指标 | 默认目标 |
|---|---|
| 3 个月短回测 | 无异常完成 |
| 1 年回测 | 日志可读，无明显卡顿 |
| 长周期回测 | 耗时进入版本基线 |
| profile on/off | 正式长测关闭 profile 时不慢于开启 profile |

### 10.5 profile 策略

`enable_profile()` 只适合短周期定位性能瓶颈。

正式长周期回测建议：

- 上传关闭 profile 的版本。
- 或由上传脚本在策略首行控制是否包含 `enable_profile()`。
- profile 结果只用于性能诊断，不作为收益评价版本。

## 11. 测试与验证方案

详细测试矩阵以 [测试方案设计文档.md](tests/测试方案设计文档.md) <!-- pathref: strategy_tests(strategy=etf_factor_rotation)/测试方案设计文档.md --> 为准。本文只列实现方案必须覆盖的验收点。

### 11.1 本地测试

必须覆盖：

| 类型 | 用例 |
|---|---|
| 参数 | 默认参数存在、权重归一、窗口合法、复权口径参数化 |
| 数据 | `fetch_field` 传 `panel=False`、`skip_paused=True`、`fq`、`end_date` |
| 数据 | None、空表、缺列、MultiIndex 返回结构归一化 |
| 趋势 | 上行、下行、等于均线、数据不足 |
| 动量 | 多周期排名、TopK、趋势未通过不打分 |
| 风险平价 | 权重归一、低波动高权重、极低波动保护 |
| RSRS | 数据不足退化、弱结构减仓、强结构不加仓、数值异常 |
| 拥挤度 | 高拥挤惩罚、成交额缺失、窗口不足 |
| 组合波动率 | 超目标缩仓、低波动不缩、日期对齐 |
| 约束 | MaxWeight、MinWeight、MaxTotalWeight、不重新归一化 |
| 执行 | 停牌跳过、阈值跳过、下单失败、下单成功、账户为 0 |
| 性能 | `weekly_check` 取数调用次数为 4 |

推荐命令：

```powershell
.venv\Scripts\python.exe -m py_compile strategies\etf_factor_rotation\etf_factor_rotation.py
.venv\Scripts\python.exe -m pytest strategies\etf_factor_rotation\tests -q
python -m scripts.path_tools.refactor check
```

### 11.2 云端验证

必须执行：

| 阶段 | 回测 | 验证点 |
|---|---|---|
| C0 冒烟 | 1 至 3 个月 | 上传、初始化、run_weekly、取数、下单不报错 |
| C1 行为 | 1 年 | 趋势、动量、RSRS、拥挤度、组合缩放日志符合预期 |
| C1 复权 A/B | 同区间两组 | `use_real_price=True,fq='pre'` vs `use_real_price=False,fq=None` |
| C3 性能 | 默认长周期 | 耗时、日志量、profile 开销 |
| 扩池验证 | 5 至 8 ETF 短测 | API 调用次数不增加，耗时增长可解释 |

云端首次验证建议临时增加以下日志，验证后关闭：

- `get_price` 返回 `type(raw)`、`shape`、`columns` 摘要。
- `MarketSnapshot` 每个字段最后日期。
- 每次调仓 `context.previous_date`。

## 12. 实施路线

### 阶段 1：不改变策略行为的解耦改造

目标：代码结构更清晰，测试更稳定，不改变回测信号。

任务：

1. 新增 `snapshot_params()`。
2. 新增 `validate_params(params)`。
3. 新增 `normalize_field_frame(raw, field, pool)`。
4. 新增 `compute_history_count(params)`。
5. 新增 `compose_raw_weights(...)`。
6. `weekly_check()` 改为读取 `params` 后传递给下游，先允许部分函数仍读取 `g`。
7. 补新增函数单测。

验收：

- 本地 pytest 全部通过。
- 默认回测日志和关键信号与改造前一致。
- `get_price` 调用次数仍为 4。

### 阶段 2：核心函数纯函数化

目标：核心计算层不直接依赖 `g`。

任务：

1. 将 `compute_trend_gates(prices, pool)` 改为 `compute_trend_gates(snapshot, params)`。
2. 将动量、风险平价、RSRS、拥挤度、组合波动率、仓位约束逐步改为接收 `params`。
3. 所有模块输出统一 `np.array` 或 `list[bool]`。
4. 补函数签名变更后的测试。

验收：

- 本地测试无需修改 `strategy.g` 即可直接测试核心函数。
- 核心函数不调用聚宽 API。
- 核心函数不写日志。

### 阶段 3：性能和日期对齐增强

目标：消除扩池和停牌场景的性能与日期错位风险。

任务：

1. 组合波动率收益矩阵改为共同日期 inner join。
2. 横截面动量对缺失列和缺失日期增加显式降级。
3. RSRS 和拥挤度增加耗时基线测试。
4. 增加 3/5/8 ETF 合成数据性能测试。
5. 明确 profile 开关流程。

验收：

- 默认 3 ETF 本地性能不退化超过 50%。
- 8 ETF 合成数据无数量级性能跳变。
- 云端短回测不因返回结构或日期对齐报错。

### 阶段 4：扩展机制固化

目标：新增模块有固定接入方式。

任务：

1. 建立 Gate / Selector / Allocator / Multiplier 模块注释模板。
2. `compose_raw_weights()` 支持 multiplier 列表。
3. 增加 `MaxTotalWeight` 总仓位兜底。
4. 新增模块测试模板。

验收：

- 新增一个示例 multiplier 时，不改数据适配层和执行层。
- 新增一个示例 Gate 时，不改权重和执行层。

### 阶段 5：云端闭环

目标：本地技术方案在聚宽真实环境成立。

任务：

1. 跑 C0 冒烟回测。
2. 跑复权口径 A/B。
3. 跑 profile on/off。
4. 归档 `backtest_report.md`、`strategy-analysis.md`、`performance-analysis.md`。
5. 根据云端结果更新本文档和测试方案。

验收：

- 云端返回结构已确认。
- 复权口径有明确选择理由。
- 长周期正式回测关闭 profile 或记录开启原因。
- 回测产物完整归档。

## 13. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 聚宽批量 `get_price` 返回结构和本地 mock 不一致 | 云端报错 | `normalize_field_frame` 兼容宽表/MultiIndex；C0 冒烟验证 |
| 开盘调仓误读当日数据 | 未来函数 | 统一 `end_date=context.previous_date`，日志记录最后日期 |
| 场内基金复权口径影响信号 | 回测结果不可解释 | `use_real_price/fq` A/B 回测并记录结论 |
| 扩池后 rolling 变慢 | 云端超时 | 保持批量取数；扩池前跑性能基线 |
| 停牌导致日期错位 | 协方差计算错误 | 组合波动率按共同日期 inner join |
| 下单失败不可见 | 模拟交易不可审计 | 记录订单返回值、目标权重、当前权重、目标市值 |
| 参数错误静默运行 | 结果不可复现 | `validate_params` 启动时失败 |
| 日志过多 | 长回测慢且难读 | 只保留调仓日模块摘要，关闭临时结构日志 |

## 14. 最终验收标准

技术方案完成的判断标准：

| 目标 | 验收标准 |
|---|---|
| 解耦 | 除 `fetch_field/get_history_data/execute_rebalance/initialize` 外，核心函数不调用聚宽 API |
| 解耦 | 核心函数输入输出可在本地用 pandas/numpy 数据直接测试 |
| 扩展性 | 新增 Gate、Multiplier、Allocator 有固定接口和测试模板 |
| 扩展性 | 新增 ETF 不增加 `get_price` 调用次数，只增加 DataFrame 列数 |
| 性能 | 默认每次调仓 `get_price` 调用数为 4 |
| 性能 | RSRS、拥挤度、组合波动率有本地和云端性能基线 |
| 数据安全 | 所有历史日线取数显式截止到 `context.previous_date` |
| 数据安全 | 组合协方差使用共同日期收益率 |
| 交易审计 | 每个下单、跳过、失败都有可解释日志 |
| 云端闭环 | C0/C1/C3 回测完成并归档报告 |

## 15. 当前推荐结论

当前最优实现路线不是大规模重构，而是按以下顺序推进：

1. 保留聚宽单文件策略形态。
2. 先把参数快照、数据归一化、权重合成、历史窗口计算拆出来。
3. 再逐步让核心计算函数摆脱 `g`。
4. 保持整池批量取数，默认 4 次 `get_price`。
5. 用云端短回测确认返回结构、复权口径和 profile 开销。

这条路线能同时满足三个目标：

- 设计解耦：API、计算、执行分层清楚。
- 扩展性：新增因子和资产池有稳定接口。
- 性能：API 调用数稳定，长窗口计算可基线化和优化。
