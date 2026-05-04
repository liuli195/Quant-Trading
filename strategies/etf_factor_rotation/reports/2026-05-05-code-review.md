# ETF Factor Rotation 代码评审与优化方案

评审日期：2026-05-05  
评审对象：[策略主文件](../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->、[单元测试](../tests/test_etf_factor_rotation.py) <!-- pathref: strategy_tests(strategy=etf_factor_rotation)/test_etf_factor_rotation.py -->、[策略方案说明书](../ETF轮动策略方案说明书.md) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/ETF轮动策略方案说明书.md -->

## 1. 评审依据

- [JoinQuant API 离线文档](../../../docs/joinquant-api.md) <!-- pathref: docs/joinquant-api.md -->
- [JoinQuant 场内基金数据文档](../../../docs/joinquant-data/JQ_场内基金数据.md) <!-- pathref: joinquant_data/JQ_场内基金数据.md -->
- [项目开发规范 CLAUDE.md](../../../CLAUDE.md) <!-- pathref: repo/CLAUDE.md -->
- 本地可执行校验：`py_compile`、`pathref check`

本评审只基于本地代码、离线文档和静态推导。涉及聚宽云端运行时返回结构、数据最后日期、复权口径的部分，本地无法完全确认，均标注为“依据不足”并给出下一步验证动作。

## 2. 总体结论

策略设计思路完整，模块边界较清晰，测试也覆盖了多数纯计算函数。但当前存在 3 类需要优先处理的问题：

1. RSRS 修正模块按现有取数长度基本不会生效，影响策略核心公式。
2. `get_price` 的多标的取数方式与本地 JoinQuant 文档约束冲突，并且未显式限制 `end_date=context.previous_date`。
3. 执行层缺少交易可行性检查、下单结果审计和关键风控日志。

建议先完成 P0 修复，再上传聚宽做短周期回归。未完成云端回归前，不建议直接把当前版本用于长期回测结论或模拟交易。

## 3. 主要问题清单

| ID | 严重度 | 问题 | 影响 | 建议优先级 |
|---|---|---|---|---|
| R1 | 高 | RSRS beta 滚动起点错误，导致乘数长期退化为 1 | 核心“价格结构转弱降仓”模块失效 | P0 |
| R2 | 高 | 多 ETF `get_price(..., skip_paused=True)` 未设置 `panel=False` | 云端可能返回结构不兼容或直接报错 | P0 |
| R3 | 中高 | 开盘调仓未显式传 `end_date=context.previous_date` | 可能引入当日收盘价未来数据 | P0 |
| R4 | 中 | 场内基金策略开启 `use_real_price=True` 需要复权口径验证 | 信号、下单价格和回测结果可能口径不一致 | P1 |
| R5 | 中 | 执行层缺少停牌、涨跌停、订单失败检查 | 实盘/模拟可审计性不足，失败原因不透明 | P1 |
| R6 | 中 | 测试未覆盖关键失败路径 | 单测通过也不能证明云端可运行 | P1 |
| R7 | 低 | `enable_profile()` 默认开启 | 长周期回测有额外性能开销 | P2 |

## 4. 详细评审意见

### R1. RSRS 修正模块当前基本不会生效

证据：

- `g.RSRS_M = 600`，`g.RSRS_N = 18`。
- `get_history_data()` 取数长度为 `max_window + 100`，当前约为 `700`。
- `compute_rsrs_multipliers()` 的 beta 计算循环从 `M + N - 1` 开始。
- 因此 700 天数据只能得到约 `700 - 617 = 83` 个 beta，随后 `len(betas) < M` 成立，乘数返回 `1.0`。

影响：

- 策略公式中 `RSRSMultiplier_i,t` 实际长期为 1。
- 方案说明书中的“价格结构转弱时平滑降仓”没有落地。

可落地修复：

```python
min_len = M + N - 1
if len(h) < min_len:
    multipliers[i] = 1.0
    continue

for t in range(N - 1, len(h)):
    h_window = h.iloc[t - N + 1:t + 1].values
    l_window = l.iloc[t - N + 1:t + 1].values
    ...

if len(betas) < M:
    multipliers[i] = 1.0
    continue

beta_series = np.array(betas[-M:])
```

验收标准：

- 构造 700 天数据时，RSRS 至少能得到 600 个 beta。
- 增加单测：在价格结构明显转弱的场景下，至少一只 ETF 的 `RSRSMultiplier < 1.0`。
- 云端短回测日志打印最近一期 `rsrs_z/latest_r2/multiplier`，确认不再恒为 1。

### R2. 批量 `get_price` 用法与 JoinQuant 文档冲突

证据：

- 代码对多 ETF 调用 `get_price(pool, ..., skip_paused=True)`，但未显式设置 `panel=False`。
- JoinQuant API 文档说明：当 `skip_paused=True` 且获取多个标的时，需要将 `panel=False`。
- 文档还说明 pandas 0.25 后多标的数据建议设置 `panel=False`。

影响：

- 云端可能返回 `Panel`、宽表、或因参数组合不支持而异常。
- 本地测试当前用自定义 `_MockPriceResult` 模拟了 `['close']` 访问方式，不能证明聚宽真实返回结构一致。

可落地修复方案 A，保守优先：

逐 ETF 拉取单字段数据，再按日期索引 inner join：

```python
def fetch_field(context, pool, field, count):
    series_map = {}
    for etf in pool:
        df = get_price(
            etf,
            count=count,
            end_date=context.previous_date,
            frequency='daily',
            fields=[field],
            panel=False,
            fq='pre'
        )
        if df is not None and len(df) > 0:
            series_map[etf] = df[field]
    return pd.DataFrame(series_map).dropna(how='all')
```

可落地修复方案 B，性能优先：

继续批量拉取，但统一设置 `panel=False`，然后写 `extract_field_frame(raw, field, pool)` 兼容不同返回结构。该方案必须先在聚宽云端短回测确认真实结构。

验收标准：

- 单测覆盖单标 DataFrame、批量 dict-like、批量 MultiIndex 三种返回形态。
- 云端日志记录 `type(raw)`、`raw.shape` 或字段结构，确认解析稳定。

### R3. 开盘调仓未显式限制历史行情截止日期

证据：

- 策略通过 `run_weekly(..., time='open')` 开盘运行。
- `get_price()` 未传 `end_date`。
- JoinQuant 文档说明：开盘使用 `get_price` 获取当天收盘价属于未来数据。

依据不足：

- 本地无法确认聚宽在 `time='open'`、`count`、`frequency='daily'`、`end_date=None` 组合下最后返回日期是昨日还是当日。
- 虽然代码设置了 `avoid_future_data=True`，但文档也说明该选项不是万能的。

可落地修复：

- 所有历史日线取数显式传入 `end_date=context.previous_date`。
- 在 `get_history_data()` 中加入数据新鲜度日志：

```python
last_dt = close_df.index[-1] if len(close_df) else None
log.info("history end_date=%s, context.previous_date=%s" % (last_dt, context.previous_date))
```

验收标准：

- 云端短回测中所有历史数据最后日期不晚于 `context.previous_date`。
- 增加单测：mock `get_price` 断言每次调用都包含 `end_date=context.previous_date`。

### R4. 场内基金复权与真实价格模式需要验证

证据：

- 策略资产池为场内基金：`159819.XSHE`、`513100.XSHG`、`518880.XSHG`。
- 代码开启 `set_option('use_real_price', True)`。
- JoinQuant 文档对场内基金提示：动态复权会生效，但因场内基金拆分/合并披露问题，不建议给含场内基金的策略开启动态复权。

依据不足：

- 本地无法判断这三只 ETF 在目标回测区间是否发生影响复权因子的折算、拆分、分红。
- 本地无法验证 `fq='pre'` 与实际成交价格之间对信号和下单数量的影响。

可落地验证：

1. 云端跑两组短回测：
   - A：`use_real_price=True`、`fq='pre'`
   - B：`use_real_price=False` 或 `fq=None`
2. 比较每个调仓日：
   - 趋势门槛
   - 动量排序
   - RSRS 乘数
   - 最终权重
   - 成交价格和成交数量

验收标准：

- 如果两组信号差异很小，保留当前口径并在策略说明书中记录理由。
- 如果差异显著，优先使用更能解释实盘成交的口径，并统一历史信号与交易价格的复权假设。

### R5. 执行层缺少可交易性检查和订单审计

证据：

- `execute_rebalance()` 直接调用 `order_target_value()`，没有使用 `get_current_data()` 检查停牌、涨跌停。
- `order_target_value()` 返回值未保存，也没有处理 `None`。
- CLAUDE.md 要求记录目标权重、当前权重、实际成交偏差。

影响：

- 下单失败时无法定位原因。
- 开盘涨跌停、停牌、未上市、退市后的状态没有前置过滤。
- 后续回测分析缺少足够审计字段。

可落地修复：

```python
current_data = get_current_data()
for i, etf in enumerate(pool):
    data = current_data[etf]
    if data.paused:
        log.warning("skip paused ETF: %s" % etf)
        continue

    order_obj = order_target_value(etf, target_value)
    if order_obj is None:
        log.error("order failed: %s target_value=%.2f target_weight=%.4f current_weight=%.4f" % (
            etf, target_value, final_weights[i], current_weight
        ))
    else:
        log.info("order sent: %s target_weight=%.4f current_weight=%.4f target_value=%.2f" % (
            etf, final_weights[i], current_weight, target_value
        ))
```

验收标准：

- 单测覆盖：停牌跳过、下单返回 `None` 时记录 error、权重偏离小于阈值时跳过。
- 回测日志能复现每次调仓的目标权重、当前权重、目标市值和订单结果。

### R6. 测试覆盖不足以暴露关键问题

证据：

- RSRS 测试目前主要验证长度和区间，没有验证乘数实际下降。
- `test_all_trend_gates_zero_goes_to_cash` 中计算了 `found`，但没有断言。
- 本地环境没有 `pytest`，当前无法运行测试套件。

可落地修复：

- 补 `test_rsrs_multiplier_can_reduce_position()`。
- 补 `test_get_history_data_passes_previous_date()`。
- 补 `test_get_history_data_handles_real_joinquant_shapes()`。
- 修复趋势全失效测试，明确断言持仓 ETF 被下单到 0。
- 在项目根目录增加依赖说明，至少明确本地测试需要 `pytest`。

验收标准：

- `python -m pytest strategies/etf_factor_rotation/tests -q` 可在标准环境运行。
- 测试失败时能指向具体策略约束，而不是只验证“不崩溃”。

### R7. `enable_profile()` 默认开启

证据：

- 策略第 1 行调用 `enable_profile()`。
- JoinQuant 文档说明不需要时不应调用，因为它会影响性能。

可落地方案：

- 开发调试版本保留，生产回测版本注释或通过上传脚本控制。
- 长周期回测前先用短周期 profile 定位性能瓶颈，再关闭 profile 跑正式回测。

## 5. 优化实施路线

### P0：先保证策略逻辑真实生效

1. 修复 RSRS beta 滚动起点。
2. 所有历史日线数据显式 `end_date=context.previous_date`。
3. 修复 `get_price` 多标的返回结构处理。
4. 补对应单测。

### P1：提升云端运行稳定性和可审计性

1. 增加 `get_current_data()` 交易状态检查。
2. 捕获 `order_target_value()` 返回值并记录失败原因。
3. 打印每次调仓的核心中间量：
   - `TrendGate`
   - `MomentumScore`
   - `Selected`
   - `RPWeight`
   - `RSRSMultiplier`
   - `CrowdPenalty`
   - `PortfolioVolScale`
   - `FinalWeight`

### P2：完成策略口径验证和文档闭环

1. 做 `use_real_price` 与 `fq` 组合对照回测。
2. 输出单次回测产物：
   - `backtest_report.md`
   - `strategy-analysis.md`
   - `performance-analysis.md`
3. 将复权口径、手续费、滑点、调仓频率写入方案说明书。

## 6. 下一轮云端回测检查清单

| 检查项 | 预期 |
|---|---|
| 历史数据最后日期 | 不晚于 `context.previous_date` |
| `get_price` 返回结构 | 能稳定解析为 `index=日期, columns=ETF代码` |
| RSRS 乘数 | 不应长期全为 1 |
| 趋势全失效 | 已有持仓应调到 0 或按阈值明确跳过 |
| 停牌或不可交易 | 记录 warning 并跳过 |
| 下单失败 | 记录 error，包含 ETF、目标市值、目标权重 |
| 复权口径 | 与策略说明书一致 |
| 回测产物 | 三份报告齐全 |

## 7. 本地验证记录

已执行：

```powershell
python -m py_compile strategies/etf_factor_rotation/etf_factor_rotation.py
python -m scripts.path_tools.refactor check
```

结果：

- 语法检查通过。
- pathref 检查通过，检查了 102 个引用。

未完成：

```powershell
python -m pytest strategies/etf_factor_rotation/tests -q
```

原因：当前 Python 环境没有 `pytest`，且当前 `python` 环境未提供 `pip`。下一步需要确认项目推荐 Python 环境，或安装测试依赖后重新运行。
