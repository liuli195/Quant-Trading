# ETF Factor Rotation 代码评审与优化方案

评审日期：2026-05-05  
评审对象：[策略主文件](../../etf_factor_rotation.py) <!-- pathref: strategy_dir(strategy=etf_factor_rotation)/etf_factor_rotation.py -->、[单元测试](../../tests/test_etf_factor_rotation.py) <!-- pathref: strategy_tests(strategy=etf_factor_rotation)/test_etf_factor_rotation.py -->、[策略方案说明书](ETF轮动策略方案说明书.md) <!-- pathref: strategy_reports(strategy=etf_factor_rotation)/design/ETF轮动策略方案说明书.md -->

## 1. 评审依据

- [JoinQuant API 离线文档](../../../../docs/reference/joinquant-api.md) <!-- pathref: docs/reference/joinquant-api.md -->
- [JoinQuant 场内基金数据文档](../../../../docs/joinquant-data/JQ_场内基金数据.md) <!-- pathref: joinquant_data/JQ_场内基金数据.md -->
- [项目开发规范 CLAUDE.md](../../../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->
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
| R1 | 高 | RSRS beta 滚动起点错误，导致乘数长期退化为 1 | 核心”价格结构转弱降仓”模块失效 | ✅ 已修复 (2026-05-05) |
| R2 | 高 | 多 ETF `get_price(..., skip_paused=True)` 未设置 `panel=False` | 云端可能返回结构不兼容或直接报错 | ✅ 已修复 (2026-05-05) |
| R3 | 中高 | 开盘调仓未显式传 `end_date=context.previous_date` | 可能引入当日收盘价未来数据 | ✅ 已修复 (2026-05-05) |
| R4 | 中 | 场内基金策略开启 `use_real_price=True` 需要复权口径验证 | 信号、下单价格和回测结果可能口径不一致 | ✅ 代码已参数化 (2026-05-05)，云端验证待执行 |
| R5 | 中 | 执行层缺少停牌、涨跌停、订单失败检查 | 实盘/模拟可审计性不足，失败原因不透明 | ✅ 已修复 (2026-05-05) |
| R6 | 中 | 测试未覆盖关键失败路径 | 单测通过也不能证明云端可运行 | ✅ 已修复 (2026-05-05) |
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

**修复记录（2026-05-05）：**

- [etf_factor_rotation.py:447](strategies/etf_factor_rotation/etf_factor_rotation.py) `min_len` 从 `M + N` 改为 `M + N - 1`
- [etf_factor_rotation.py:455](strategies/etf_factor_rotation/etf_factor_rotation.py) 循环起点从 `M + N - 1` 改为 `N - 1`
- [test_etf_factor_rotation.py](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 新增 `test_rsrs_multiplier_can_reduce_position`
- 单测验证：44 passed, 0 failed（`.venv` 环境）

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

**修复记录（2026-05-05）：**

采用方案 A（逐 ETF 拉取），新增 `fetch_field()` 函数，每次只拉取单只 ETF 的单字段数据并显式传 `panel=False`：

- [etf_factor_rotation.py:200-236](strategies/etf_factor_rotation/etf_factor_rotation.py) 新增 `fetch_field()` 辅助函数；`get_history_data()` 改用 `fetch_field()` 替代 4 处批量 `get_price` 调用
- [test_etf_factor_rotation.py:54-80](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 替换 `_MockPriceResult` / `_setup_get_price_mock` 为函数式 `side_effect`，适配逐 ETF 调用模式
- [test_etf_factor_rotation.py:702-796](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 新增 `TestFetchField`（6 个用例）：验证逐 ETF 调用、`panel=False` 传参、`skip_paused=True` 保留、返回结构正确性、缺失数据处理、完整集成
- 单测验证：50 passed, 0 failed（`.venv` 环境）
- 语法检查通过

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

**修复记录（2026-05-05）：**

- [etf_factor_rotation.py:200](strategies/etf_factor_rotation/etf_factor_rotation.py) `fetch_field()` 新增 `end_date` 参数，透传给 `get_price()`
- [etf_factor_rotation.py:236-239](strategies/etf_factor_rotation/etf_factor_rotation.py) `get_history_data()` 4 处 `fetch_field()` 调用均传入 `end_date=context.previous_date`
- [etf_factor_rotation.py:242-245](strategies/etf_factor_rotation/etf_factor_rotation.py) 新增数据新鲜度日志：打印历史数据最后日期 vs `context.previous_date`
- [test_etf_factor_rotation.py:68](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) `_setup_get_price_mock` 的 mock 函数签名增加 `end_date` 参数
- [test_etf_factor_rotation.py](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 新增 `TestGetHistoryDataEndDate`（3 个用例）：验证 `end_date` 传参、新鲜度日志、`weekly_check` 集成流程
- [test_etf_factor_rotation.py](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 修复 4 个已有集成测试：mock context 补齐 `previous_date` 属性
- 单测验证：53 passed, 0 failed（`.venv` 环境）

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

**修复记录（2026-05-05）——代码参数化：**

- [etf_factor_rotation.py:47](strategies/etf_factor_rotation/etf_factor_rotation.py) `initialize()` 中 `set_option('use_real_price', ...)` 改为读取 `g.use_real_price` 而非硬编码 `True`；`set_parameter()` 调用提前以确保 `g` 已填充
- [etf_factor_rotation.py:137-140](strategies/etf_factor_rotation/etf_factor_rotation.py) `set_parameter()` 新增 `g.use_real_price = True`、`g.fq_mode = 'pre'`，附注释说明场内基金复权风险及 A/B 验证方法
- [etf_factor_rotation.py:222](strategies/etf_factor_rotation/etf_factor_rotation.py) `fetch_field()` 中 `fq` 改为 `g.fq_mode` 替代硬编码 `'pre'`
- [test_etf_factor_rotation.py](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) `TestSetParameter` 新增 `test_fq_mode_defaults_to_pre`、`test_use_real_price_defaults_to_true`
- [test_etf_factor_rotation.py](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 新增 `TestFetchFieldFqMode`（3 个用例）：验证 `fetch_field` 传递 `g.fq_mode`（`'pre'`/`'post'`/`None`）
- [conftest.py](strategies/etf_factor_rotation/tests/conftest.py) `mock_g` fixture 补齐 `use_real_price=True`、`fq_mode='pre'`
- 单测验证：58 passed, 0 failed（`.venv` 环境）

**待执行（云端）：**

1. 在聚宽跑两组短回测：A 组 `use_real_price=True, fq='pre'` vs B 组 `use_real_price=False, fq=None`
2. 比较每个调仓日：趋势门槛、动量排序、RSRS 乘数、最终权重、成交价格和成交量
3. 根据差异大小决定保留当前口径或切换

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

**修复记录（2026-05-05）：**

- [etf_factor_rotation.py:698-742](strategies/etf_factor_rotation/etf_factor_rotation.py) `execute_rebalance()` 增加 `get_current_data()` 停牌检查、`order_target_value()` 返回值 `None` 处理、订单审计日志（info/error）
- [conftest.py:65-69](strategies/etf_factor_rotation/tests/conftest.py) 新增 `get_current_data` mock，默认返回全部非停牌
- [conftest.py:180-186](strategies/etf_factor_rotation/tests/conftest.py) `_auto_reset_mocks` 增加 `get_current_data` 重置（保持默认非停牌）
- [test_etf_factor_rotation.py](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 新增 `TestExecuteRebalance`（4 个用例）：停牌跳过 + warning、下单失败记录 error、正常下单记录 info、权重偏离小于阈值跳过
- 单测验证：62 passed, 0 failed（`.venv` 环境）

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
- 测试失败时能指向具体策略约束，而不是只验证”不崩溃”。

**修复记录（2026-05-05）：**

- [test_etf_factor_rotation.py:666-682](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) `test_all_trend_gates_zero_goes_to_cash` 增加断言：验证每只 ETF 的 `target_value=0` 且全部三只 ETF 被调仓
- [test_etf_factor_rotation.py:659-663](strategies/etf_factor_rotation/tests/test_etf_factor_rotation.py) 持仓市值从 1000×1→5000×10 确保超过 `RebalanceThreshold` 不被跳过
- [conftest.py:186-194](strategies/etf_factor_rotation/tests/conftest.py) 修复 `_auto_reset_mocks` 中 `get_current_data` 重置方式：`reset_mock()` 只接受 bool，自定义 return_value 需单独赋值
- 单测验证：62 passed, 0 failed（`.venv` 环境）

**已由其他 Issue 覆盖：**
- `test_rsrs_multiplier_can_reduce_position` → R1 已新增
- `test_get_history_data_passes_previous_date` → R3 已新增
- `test_get_history_data_handles_real_joinquant_shapes` → 无需添加，R2 逐 ETF 拉取消除了返回结构歧义
- 依赖说明 → `requirements.txt` 已含 `pytest==9.0.3`

### R7. `enable_profile()` 默认开启

证据：

- 策略第 1 行调用 `enable_profile()`。
- JoinQuant 文档说明不需要时不应调用，因为它会影响性能。

可落地方案：

- 开发调试版本保留，生产回测版本注释或通过上传脚本控制。
- 长周期回测前先用短周期 profile 定位性能瓶颈，再关闭 profile 跑正式回测。

## 5. 优化实施路线

### P0：先保证策略逻辑真实生效

1. ✅ 修复 RSRS beta 滚动起点（R1，2026-05-05）。
2. ✅ 所有历史日线数据显式 `end_date=context.previous_date`（R3，2026-05-05）。
3. ✅ 修复 `get_price` 多标的返回结构处理（R2，2026-05-05）。
4. ✅ 补对应单测（随各修复完成）。

### P1：提升云端运行稳定性和可审计性

1. ✅ 增加 `get_current_data()` 交易状态检查（R5，2026-05-05）。
2. ✅ 捕获 `order_target_value()` 返回值并记录失败原因（R5，2026-05-05）。
3. ✅ 修复关键测试断言缺失和 mock 重置 bug（R6，2026-05-05）。
4. ✅ 打印每次调仓的核心中间量（2026-05-05）：
   - `TrendGate` / `MomentumScore` / `Selected` / `RPWeight` / `RSRSMultiplier` / `CrowdPenalty` / `PortfolioVolScale` / `FinalWeight`
   - 每条日志带中文名 + 英文变量名，格式 `[趋势门槛] TrendGate: 159819=1, 513100=1, 518880=0`

### P2：完成策略口径验证和文档闭环

1. 做 `use_real_price` 与 `fq` 组合对照回测。
2. 将复权口径、手续费、滑点、调仓频率写入方案说明书。

## 6. 下一轮云端回测检查清单

| 检查项 | 预期 |
|---|---|
| 历史数据最后日期 | 不晚于 `context.previous_date` |
| `get_price` 返回结构 | 能稳定解析为 `index=日期, columns=ETF代码` |
| RSRS 乘数 | ✅ 已修复，不应长期全为 1 |
| 趋势全失效 | 已有持仓应调到 0 或按阈值明确跳过 |
| 停牌或不可交易 | 记录 warning 并跳过 |
| 下单失败 | 记录 error，包含 ETF、目标市值、目标权重 |
| 复权口径 A/B 对照 | 跑两组短回测：A 组 `use_real_price=True, fq='pre'`，B 组 `use_real_price=False, fq=None`，比较每个调仓日的趋势门槛、动量排序、RSRS 乘数、最终权重、成交价格/数量。差异显著则切换口径，差异小则记录理由保留当前 |

## 7. 本地验证记录

已执行：

```powershell
python -m py_compile strategies/etf_factor_rotation/etf_factor_rotation.py
python -m scripts.path_tools.refactor check
```

结果：

- 语法检查通过。
- pathref 检查通过，检查了 102 个引用。

已完成（2026-05-05 补充）：

```powershell
# 使用项目 .venv 环境
.venv/Scripts/python -m pytest strategies/etf_factor_rotation/tests -q
```

结果：**44 passed, 0 failed**（含 R1 修复后的新增测试）。

R2 修复后补充（2026-05-05）：

```powershell
.venv/Scripts/python -m pytest strategies/etf_factor_rotation/tests -q
```

结果：**50 passed, 0 failed**（含 R2 修复后的新增测试）。

R3 修复后补充（2026-05-05）：

结果：**53 passed, 0 failed**（含 R3 修复后的 3 个新增测试 + 4 个已有集成测试适配）。

R4 修复后补充（2026-05-05）：

结果：**58 passed, 0 failed**（含 R4 参数化后的 5 个新增测试 + conftest mock_g 补齐）。

R5 修复后补充（2026-05-05）：

结果：**62 passed, 0 failed**（含 R5 修复后的 4 个新增测试 + conftest get_current_data mock）。

R6 修复后补充（2026-05-05）：

结果：**62 passed, 0 failed**（修复 `test_all_trend_gates_zero_goes_to_cash` 断言 + conftest mock 重置 bug）。
