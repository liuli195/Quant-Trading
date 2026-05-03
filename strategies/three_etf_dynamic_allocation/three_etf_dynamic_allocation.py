enable_profile()

"""
============================================================
策略名称：三 ETF 动态配比策略
策略类型：日线级别、场内基金、多资产动态配置
适用标的：黄金 ETF、AI ETF、纳指100 ETF

核心逻辑：
  第一步：逐 ETF 获取历史收盘价（get_price 逐只调用，手动拼接宽表）
  第二步：计算对数收益率，滚动 60 日年化波动率（numpy 向量化）
  第三步：分别计算三类资产的复合因子得分（趋势 + 动量 + 波动率 + 回撤）
  第四步：套用核心权重公式 w_i ∝ (1 + k × s_i) / σ_i
  第五步：施加三级约束（单资产上下限 → 调仓幅度限制 → 归一化）
  第六步：执行调仓（order_target_value 按目标市值调整）

因子体系：
  - 黄金（防御资产）：0.5×趋势 + 0.3×相对强弱 + 0.2×风险厌恶
    趋势 = 价格相对 20 日均线偏离率 z-score
    相对强弱 = 黄金 20 日超额收益（相对纳指）z-score
    风险厌恶 = 纳指近 20 日收益 < 0 → 1.0

  - AI ETF（高弹性进攻资产）：0.45×动量 + 0.25×趋势 - 0.20×波动率 - 0.10×回撤
    动量 = 20 日累计简单收益率（ROC）z-score
    趋势 = 价格相对 20 日均线偏离率 z-score
    波动率 = 短/长期波动率比 z-score（比率升高 → 扣分）
    回撤 = 当前价格相对 60 日最高价的回撤幅度 z-score（回撤越大 → 扣分越多）

  - 纳指100（核心成长资产）：0.40×动量 + 0.20×趋势 + 0.20×风险偏好 - 0.20×波动率
    动量 = 60 日累计简单收益率（ROC）z-score
    趋势 = 价格相对 20 日均线偏离率 z-score
    风险偏好 = 纳指 20 日收益 > 0 且 > 黄金同期收益 → 1.0
    波动率 = 同 AI ETF 的波动率惩罚逻辑

核心公式：
  w_i = (1 + k × s_i) / σ_i  /  Σ_j (1 + k × s_j) / σ_j
  - k = 0.3（因子强度），σ_i = 60 日年化波动率，s_i = 因子得分 ∈ [-1, 1]

权重约束：
  - 黄金：10% ~ 60%
  - AI ETF：10% ~ 50%（波动更大，上限更严）
  - 纳指100：10% ~ 60%
  - 单次调仓最大变化：±10%
  - 施加顺序：上下限裁剪 → 幅度限制 → 归一化

调仓频率：每周第一个交易日开盘时

注意事项：
  - ETF 使用 type='fund' 手续费，免印花税
  - ETF 不复权（fq=None），聚宽建议场内基金不使用动态复权
  - get_price(etf, panel=False) 返回单 ETF Series，三只 ETF 分别调用后手动建宽表
  - send_message 仅在模拟交易中生效，回测时被忽略
============================================================
"""

import numpy as np
import pandas as pd
from jqlib.technical_analysis import BIAS, ROC


# ============================================================
# initialize — 策略初始化函数
# ============================================================
def initialize(context):
    """
    策略初始化函数，由聚宽框架在回测/模拟启动时自动调用且仅调用一次。

    完成五项核心工作：
    1. 全局配置（复权模式、未来数据防御、基准标的）
    2. 参数初始化与历史数据预加载
    3. 交易手续费设置（场内基金 fund 类型，免印花税）
    4. 滑点设置
    5. 注册每周定时调仓任务
    """

    # ---------- 全局运行配置 ----------
    # 开启动态复权（真实价格）模式
    set_option('use_real_price', True)

    # 开启未来数据防御模式（兜底检测开关）
    set_option("avoid_future_data", True)

    # ---------- 参数初始化与历史数据预加载 ----------
    set_parameter(context)

    # ---------- 交易手续费设置（场内基金，免印花税） ----------
    # 场内基金免收印花税（open_tax=0, close_tax=0）
    # 佣金按万分之一（0.0001），无最低佣金限制
    set_order_cost(
        OrderCost(
            open_tax=0,
            close_tax=0,
            open_commission=0.0001,
            close_commission=0.0001,
            min_commission=0
        ),
        type='fund'
    )

    # ---------- 滑点设置 ----------
    # ETF 流动性较好，使用固定滑点 0（保守估计）
    set_slippage(FixedSlippage(0.0), type='fund')

    # ---------- 注册每周定时调仓任务 ----------
    # 每周第一个交易日（周一）开盘时执行调仓
    run_weekly(
        weekly_rebalance,
        weekday=1,
        time='open',
        reference_security='000300.XSHG'
    )


# ============================================================
# set_parameter — 策略参数集中设置与历史数据预加载
# ============================================================
def set_parameter(context):
    """
    集中设置所有策略参数，存入 g 全局对象，并预加载初始化所需的历史数据。

    参数按类别分组：
    - ETF 资产池定义
    - 波动率计算参数
    - 因子权重系数
    - 因子计算窗口
    - 核心公式参数
    - 权重约束参数
    - 调仓频率与数据配置
    """

    # ==================== ETF 资产池 ====================
    g.etf_pool = [
        '518880.XSHG',   # 黄金 ETF（防御资产，对冲风险）
        '159819.XSHE',   # AI ETF（高弹性进攻资产，波动高）
        '513100.XSHG',   # 纳指100 ETF（核心成长资产，风险偏好敏感）
    ]
    g.etf_names = ['黄金ETF', 'AI ETF', '纳指100ETF']  # 日志可读性

    # ==================== 波动率计算参数 ====================
    g.volatility_window = 60      # 波动率计算滚动窗口（交易日）
    g.annual_factor = 252         # 年化系数（A 股年均交易日数）

    # ==================== 因子权重系数 ====================
    # 黄金因子权重（三因子加和为 1）
    g.gold_trend_w = 0.5          # 趋势权重
    g.gold_rs_w = 0.3             # 相对强弱权重
    g.gold_riskoff_w = 0.2        # 风险厌恶权重

    # AI 因子权重（四因子加和为 1）
    g.ai_momentum_w = 0.45        # 动量权重
    g.ai_trend_w = 0.25           # 趋势权重
    g.ai_volpenalty_w = 0.20      # 波动率惩罚权重
    g.ai_drawdown_w = 0.10        # 回撤惩罚权重

    # 纳指因子权重（四因子加和为 1）
    g.nasdaq_momentum_w = 0.40    # 动量权重（使用中周期 60 日）
    g.nasdaq_trend_w = 0.20       # 趋势权重
    g.nasdaq_riskon_w = 0.20      # 风险偏好权重
    g.nasdaq_volpenalty_w = 0.20  # 波动率惩罚权重

    # ==================== 因子计算窗口参数 ====================
    g.trend_ma_window = 20        # 趋势计算中的均线窗口（交易日）
    g.momentum_window_short = 20  # 短期动量窗口（AI ETF 使用）
    g.momentum_window_long = 60   # 长期动量窗口（纳指使用）
    g.vol_window_short = 20       # 短期波动率窗口
    g.vol_window_long = 60        # 长期波动率窗口（用于波动率膨胀检测）
    g.drawdown_window = 60        # 回撤观察窗口

    # ==================== 核心公式参数 ====================
    g.k = 0.3                     # 因子强度系数
    # k=0.3 时，(1+0.3×1)/(1+0.3×(-1)) = 1.3/0.7 ≈ 1.86
    # 即最强资产权重最多是最弱资产的 1.86 倍（波动率相等时）

    # ==================== 权重约束参数 ====================
    g.weight_bounds = [
        (0.10, 0.60),  # 黄金 ETF：下限 10%，上限 60%
        (0.10, 0.50),  # AI ETF：下限 10%，上限 50%（波动大，上限更严格）
        (0.10, 0.60),  # 纳指100 ETF：下限 10%，上限 60%
    ]
    g.max_weight_change = 0.10    # 单次调仓权重最大变化幅度（±10%）
    # 三资产合计单周最大换手 = 3 × 10% = 30%

    # ==================== 调仓频率与数据配置 ====================
    g.live_days = 100             # 每次调仓获取的近期数据天数
    # live_days = 100 可支持 60 日波动率窗口 + 60 日动量窗口 + 安全缓冲

    # ==================== 基准设置 ====================
    g.benchmark = '000300.XSHG'   # 沪深 300 指数作为基准
    set_benchmark(g.benchmark)


# ============================================================
# weekly_rebalance — 每周调仓主函数
# ============================================================
def weekly_rebalance(context):
    """
    每周调仓主函数，由 run_weekly 在每周第一个交易日开盘时调用。

    执行流程（7 步）：
    1. 批量获取三只 ETF 近期收盘价（单次 get_price，100 日）
    2. 计算对数收益率 → 60 日滚动年化波动率（numpy 向量化）
    3. 分别计算三类资产的复合因子得分 s_G, s_A, s_N
    4. 套用核心权重公式得到原始目标权重
    5. 从 portfolio.positions 计算当前持仓权重
    6. 施加三级约束（上下限 → 幅度限制 → 归一化）
    7. 执行调仓（order_target_value 按目标市值下单）
    """

    total_value = context.portfolio.total_value

    # ==================== 第一步：逐 ETF 获取行情数据 ====================
    # 批量 get_price(etf_list, panel=False) 在聚宽上返回的 DataFrame 列名仅含字段名
    # 不包含 ETF 代码，无法解析为宽表。改为逐 ETF 调用 get_price，收集后手动建宽表。
    prices_list = []
    valid_etfs = []
    for etf in g.etf_pool:
        prices_raw = get_price(
            etf,
            count=g.live_days,
            end_date=context.previous_date,
            frequency='daily',
            fields=['close'],
            panel=False,
            fq=None
        )
        if prices_raw is not None and len(prices_raw) > 0:
            prices_list.append(prices_raw['close'].values)
            valid_etfs.append(etf)
        else:
            prices_list.append(None)

    # 数据校验：所有 ETF 均需有数据才能继续
    if len(valid_etfs) < 3:
        log.info("【警告】部分 ETF 无价格数据，跳过本次调仓")
        return

    # 截取各 ETF 价格序列的最短长度，保证对齐
    # 注意：取 [-min_len:] 尾部而非 [:min_len] 头部
    # 各 ETF 上市时间不同会导致历史长度不同，但最新日期（end_date 相同）是对齐的
    valid_indices = [i for i, p in enumerate(prices_list) if p is not None]
    valid_prices = [prices_list[i] for i in valid_indices]
    min_len = min(len(p) for p in valid_prices)
    close_prices = pd.DataFrame({
        g.etf_pool[i]: valid_prices[j][-min_len:]
        for j, i in enumerate(valid_indices)
    })
    close_prices = close_prices.dropna()

    if len(close_prices) < 61:
        log.info("【警告】有效数据不足 61 日（需覆盖 60 日波动率/动量/回撤），跳过本次调仓")
        return

    # ==================== 第二步：计算年化波动率 ====================
    # 对数收益率 r_t = ln(P_t / P_{t-1})，numpy 向量化一次计算三列
    prices_array = close_prices.values      # shape: (n_days, 3)
    log_returns = np.log(prices_array[1:] / prices_array[:-1])

    # 取最近 g.volatility_window 日的对数收益率
    vol_window = min(g.volatility_window, len(log_returns))
    recent_returns = log_returns[-vol_window:]

    # 年化波动率 = 日收益率标准差 × √252
    # ddof=1 使用样本标准差（与 pandas std 默认行为一致）
    daily_std = np.std(recent_returns, axis=0, ddof=1)
    volatilities = daily_std * np.sqrt(g.annual_factor)  # shape: (3,)

    log.info("年化波动率: G=%.4f, A=%.4f, N=%.4f" % (
        volatilities[0], volatilities[1], volatilities[2]
    ))

    # ==================== 第三步：计算因子得分 ====================
    # 分别提取各 ETF 的价格数组（保持 numpy 数组以支持向量化运算）
    gold_prices = prices_array[:, 0]
    ai_prices = prices_array[:, 1]
    nasdaq_prices = prices_array[:, 2]

    check_date = context.previous_date  # 与 get_price 的 end_date 保持一致
    gold_code, ai_code, nasdaq_code = g.etf_pool  # 解包 ETF 代码用于因子函数
    s_G = compute_gold_factors(gold_prices, nasdaq_prices, check_date,
                                gold_code=gold_code, nasdaq_code=nasdaq_code)
    s_A = compute_ai_factors(ai_prices, check_date, ai_code=ai_code)
    s_N = compute_nasdaq_factors(nasdaq_prices, gold_prices, check_date,
                                  nasdaq_code=nasdaq_code, gold_code=gold_code)

    # 最终裁剪到 [-1, 1]（防御性编程，各子函数已裁剪但仍加一层保护）
    factor_scores = np.clip(np.array([s_G, s_A, s_N]), -1.0, 1.0)

    log.info("因子得分: s_G=%.3f, s_A=%.3f, s_N=%.3f" % (
        factor_scores[0], factor_scores[1], factor_scores[2]
    ))

    # ==================== 第四步：计算权重（纯风险平价 → 因子调整） ====================
    # 纯风险平价权重（仅基于波动率倒数，不受因子影响，作为对比基准）
    inv_vol = 1.0 / (volatilities + 1e-10)          # 波动率倒数
    rp_weights = inv_vol / np.sum(inv_vol)           # 归一化 → 纯风险平价

    # 因子调整权重（风险平价 × 因子调整项）
    raw_weights = compute_target_weights(volatilities, factor_scores, g.k)

    log.info("纯风险平价: G=%.3f, A=%.3f, N=%.3f" % (
        rp_weights[0], rp_weights[1], rp_weights[2]
    ))
    log.info("因子调整后: G=%.3f, A=%.3f, N=%.3f" % (
        raw_weights[0], raw_weights[1], raw_weights[2]
    ))

    # ==================== 第五步：获取当前持仓权重 ====================
    current_weights = np.zeros(3)
    for i, etf in enumerate(g.etf_pool):
        pos = context.portfolio.positions[etf]
        if pos is not None and pos.total_amount > 0:
            current_weights[i] = pos.value / total_value

    log.info("当前权重: G=%.3f, A=%.3f, N=%.3f" % (
        current_weights[0], current_weights[1], current_weights[2]
    ))

    # ==================== 第六步：施加约束 ====================
    final_weights = apply_weight_constraints(
        raw_weights,
        current_weights,
        g.weight_bounds,
        g.max_weight_change
    )

    log.info("最终权重: G=%.3f, A=%.3f, N=%.3f" % (
        final_weights[0], final_weights[1], final_weights[2]
    ))

    # ==================== 第七步：执行调仓 ====================
    for i, etf in enumerate(g.etf_pool):
        target_value = total_value * final_weights[i]
        order = order_target_value(etf, target_value)
        if order is None:
            log.error("【调仓失败】%s(%s): 目标市值 %.0f 下单失败，请检查账户状态" % (
                g.etf_names[i], etf, target_value
            ))
        else:
            log.info("调仓 %s(%s): 目标市值 %.0f, 目标权重 %.1f%%" % (
                g.etf_names[i], etf, target_value, final_weights[i] * 100
            ))


# ============================================================
# zscore_clip — z-score 标准化并裁剪到指定区间
# ============================================================
def zscore_clip(current_value, historical_values, floor=-1.0, ceiling=1.0):
    """
    计算当前值在历史值序列中的 z-score，并裁剪到 [floor, ceiling] 区间。

    参数:
        current_value: float，当前待标准化的值
        historical_values: numpy array，历史值序列（用于估算均值和标准差）
        floor: float，裁剪下界
        ceiling: float，裁剪上界

    返回:
        float，标准化并裁剪后的 z-score

    防御处理:
        - 历史值不足 2 个或标准差接近 0 时，返回 0.0（中性信号）
    """
    if len(historical_values) < 2:
        return 0.0

    mu = np.mean(historical_values)
    sigma = np.std(historical_values, ddof=1)

    if sigma < 1e-10:
        return 0.0

    z = (current_value - mu) / sigma
    return float(np.clip(z, floor, ceiling))


# ============================================================
# compute_gold_factors — 黄金 ETF 复合因子得分
# ============================================================
def compute_gold_factors(gold_prices, nasdaq_prices, check_date,
                          gold_code='518880.XSHG', nasdaq_code='513100.XSHG'):
    """
    计算黄金 ETF 的复合因子得分 s_G。

    s_G = 0.5 × Trend_G + 0.3 × RS_G + 0.2 × RiskOff

    子因子定义:
        Trend_G: 价格相对 20 日均线偏离率（BIAS20）的 z-score，裁剪到 [-1, 1]
        RS_G: 黄金相对纳指 20 日超额收益的 z-score，裁剪到 [-1, 1]
        RiskOff: 二值信号（纳指 20 日收益 < 0 → 1.0）

    参数:
        gold_prices: numpy array，黄金 ETF 收盘价序列
        nasdaq_prices: numpy array，纳指 ETF 收盘价序列
        check_date: datetime，当前调仓日期（用于内置指标查询）
        gold_code: str，黄金 ETF 代码（默认 '518880.XSHG'）
        nasdaq_code: str，纳指 ETF 代码（默认 '513100.XSHG'）
    """

    min_len = g.trend_ma_window
    if len(gold_prices) <= min_len:
        return 0.0

    # ---------- 子因子 1：趋势（Trend_G） ----------
    # 当前乖离率 → 内置 BIAS 指标（BIAS20 = (close-MA20)/MA20 * 100）
    bias_result = BIAS([gold_code], check_date=check_date, N1=20)
    trend_current = bias_result[0].get(gold_code, 0.0) / 100.0

    # 历史乖离率序列 → 从价格计算（用于 z-score 标准化）
    gold_ma20 = np.convolve(gold_prices, np.ones(min_len)/min_len, mode='valid')
    gold_aligned = gold_prices[min_len-1:]
    trend_vals = (gold_aligned - gold_ma20) / gold_ma20
    trend_score = zscore_clip(trend_current, trend_vals)

    # ---------- 子因子 2：相对强弱（RS_G） ----------
    if len(gold_prices) <= min_len or len(nasdaq_prices) <= min_len:
        rs_score = 0.0
    else:
        # 当前 20 日收益率 → 内置 ROC 指标
        roc_g = ROC([gold_code], check_date=check_date, timeperiod=20)
        roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
        rs_current = (roc_g.get(gold_code, 0.0) - roc_n.get(nasdaq_code, 0.0)) / 100.0

        # 历史超额收益序列（用于 z-score）
        gold_20d_ret = gold_prices[min_len:] / gold_prices[:-min_len] - 1.0
        nasdaq_20d_ret = nasdaq_prices[min_len:] / nasdaq_prices[:-min_len] - 1.0
        rs_vals = gold_20d_ret - nasdaq_20d_ret
        rs_score = zscore_clip(rs_current, rs_vals)

    # ---------- 子因子 3：风险厌恶（RiskOff） ----------
    if len(nasdaq_prices) > min_len:
        roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
        riskoff_score = 1.0 if roc_n.get(nasdaq_code, 0.0) < 0 else 0.0
    else:
        riskoff_score = 0.0

    # ---------- 复合因子得分 ----------
    s_G = (g.gold_trend_w * trend_score
           + g.gold_rs_w * rs_score
           + g.gold_riskoff_w * riskoff_score)

    return float(np.clip(s_G, -1.0, 1.0))


# ============================================================
# compute_ai_factors — AI ETF 复合因子得分
# ============================================================
def compute_ai_factors(ai_prices, check_date, ai_code='159819.XSHE'):
    """
    计算 AI ETF 的复合因子得分 s_A。

    s_A = 0.45 × Momentum_A + 0.25 × Trend_A - 0.20 × Vol_A - 0.10 × Drawdown_A

    子因子定义:
        Momentum_A: 20 日收益率（ROC20）的 z-score，裁剪到 [-1, 1]
        Trend_A: 价格相对 20 日均线偏离率（BIAS20）的 z-score，裁剪到 [-1, 1]
        Vol_A: 短期/长期波动率比的 z-score，裁剪到 [-1, 1]
        Drawdown_A: 当前价格相对 60 日最高价回撤幅度的 z-score，裁剪到 [0, 1]

    参数:
        ai_prices: numpy array，AI ETF 收盘价序列
        check_date: datetime，当前调仓日期（用于内置指标查询）
        ai_code: str，AI ETF 代码（默认 '159819.XSHE'）
    """

    if len(ai_prices) < g.trend_ma_window + 1:
        return 0.0

    ai_log_returns = np.log(ai_prices[1:] / ai_prices[:-1])

    # ---------- 子因子 1：动量（Momentum_A） ----------
    mom_w = g.momentum_window_short
    if len(ai_prices) > mom_w:
        # 当前 20 日收益率 → 内置 ROC 指标（=(close-close_20d)/close_20d）
        roc_result = ROC([ai_code], check_date=check_date, timeperiod=20)
        roc20_current = roc_result.get(ai_code, 0.0) / 100.0

        # 历史 20 日简单收益率序列（与 ROC 公式一致，用于 z-score）
        roc20_series = ai_prices[mom_w:] / ai_prices[:-mom_w] - 1.0
        mom_score = zscore_clip(roc20_current, roc20_series)
    else:
        mom_score = 0.0

    # ---------- 子因子 2：趋势（Trend_A） ----------
    min_len = g.trend_ma_window
    # 当前乖离率 → 内置 BIAS 指标
    bias_result = BIAS([ai_code], check_date=check_date, N1=20)
    trend_current = bias_result[0].get(ai_code, 0.0) / 100.0

    # 历史乖离率序列（用于 z-score）
    ai_ma20 = np.convolve(ai_prices, np.ones(min_len)/min_len, mode='valid')
    ai_aligned = ai_prices[min_len-1:]
    trend_vals = (ai_aligned - ai_ma20) / ai_ma20
    trend_score = zscore_clip(trend_current, trend_vals)

    # ---------- 子因子 3：波动率惩罚（Vol_A） ----------
    short_w = g.vol_window_short
    long_w = g.vol_window_long

    if len(ai_log_returns) >= long_w:
        short_vols = np.array([
            np.std(ai_log_returns[i:i+short_w], ddof=1)
            for i in range(len(ai_log_returns) - short_w + 1)
        ])
        long_vols = np.array([
            np.std(ai_log_returns[i:i+long_w], ddof=1)
            for i in range(len(ai_log_returns) - long_w + 1)
        ])
        common_len = min(len(short_vols), len(long_vols))
        if common_len > 1:
            vol_ratios = short_vols[-common_len:] / np.maximum(long_vols[-common_len:], 1e-10)
            vol_current = vol_ratios[-1]
            vol_score = zscore_clip(vol_current, vol_ratios)
        else:
            vol_score = 0.0
    else:
        vol_score = 0.0

    # ---------- 子因子 4：回撤惩罚（Drawdown_A） ----------
    dd_window = g.drawdown_window
    if len(ai_prices) >= dd_window:
        ai_max60 = np.array([
            np.max(ai_prices[i:i+dd_window])
            for i in range(len(ai_prices) - dd_window + 1)
        ])
        ai_aligned_dd = ai_prices[dd_window-1:]
        dd_vals = 1.0 - ai_aligned_dd / ai_max60
        dd_current = dd_vals[-1]
        dd_score = zscore_clip(dd_current, dd_vals, floor=0.0, ceiling=1.0)
    else:
        dd_score = 0.0

    # ---------- 复合因子得分 ----------
    s_A = (g.ai_momentum_w * mom_score
           + g.ai_trend_w * trend_score
           - g.ai_volpenalty_w * vol_score
           - g.ai_drawdown_w * dd_score)

    return float(np.clip(s_A, -1.0, 1.0))


# ============================================================
# compute_nasdaq_factors — 纳指100 ETF 复合因子得分
# ============================================================
def compute_nasdaq_factors(nasdaq_prices, gold_prices, check_date,
                            nasdaq_code='513100.XSHG', gold_code='518880.XSHG'):
    """
    计算纳指100 ETF 的复合因子得分 s_N。

    s_N = 0.40 × Momentum_N + 0.20 × Trend_N + 0.20 × RiskOn - 0.20 × Vol_N

    子因子定义:
        Momentum_N: 60 日收益率（ROC60）的 z-score，裁剪到 [-1, 1]
        Trend_N: 价格相对 20 日均线偏离率（BIAS20）的 z-score，裁剪到 [-1, 1]
        RiskOn: 纳指 20 日收益 > 0 且 > 黄金同期收益 → 1.0
        Vol_N: 短期/长期波动率比的 z-score

    参数:
        nasdaq_prices: numpy array，纳指 ETF 收盘价序列
        gold_prices: numpy array，黄金 ETF 收盘价序列
        check_date: datetime，当前调仓日期（用于内置指标查询）
        nasdaq_code: str，纳指 ETF 代码（默认 '513100.XSHG'）
        gold_code: str，黄金 ETF 代码（默认 '518880.XSHG'）
    """

    if len(nasdaq_prices) < g.trend_ma_window + 1:
        return 0.0

    n_log_returns = np.log(nasdaq_prices[1:] / nasdaq_prices[:-1])

    # ---------- 子因子 1：动量（Momentum_N） ----------
    mom_long_w = g.momentum_window_long
    if len(nasdaq_prices) > mom_long_w:
        # 当前 60 日收益率 → 内置 ROC 指标（=(close-close_60d)/close_60d）
        roc_result = ROC([nasdaq_code], check_date=check_date, timeperiod=60)
        roc60_current = roc_result.get(nasdaq_code, 0.0) / 100.0

        # 历史 60 日简单收益率序列（与 ROC 公式一致，用于 z-score）
        roc60_series = nasdaq_prices[mom_long_w:] / nasdaq_prices[:-mom_long_w] - 1.0
        mom_score = zscore_clip(roc60_current, roc60_series)
    else:
        mom_score = 0.0

    # ---------- 子因子 2：趋势（Trend_N） ----------
    min_len = g.trend_ma_window
    # 当前乖离率 → 内置 BIAS 指标
    bias_result = BIAS([nasdaq_code], check_date=check_date, N1=20)
    trend_current = bias_result[0].get(nasdaq_code, 0.0) / 100.0

    # 历史乖离率序列（用于 z-score）
    n_ma20 = np.convolve(nasdaq_prices, np.ones(min_len)/min_len, mode='valid')
    n_aligned = nasdaq_prices[min_len-1:]
    trend_vals = (n_aligned - n_ma20) / n_ma20
    trend_score = zscore_clip(trend_current, trend_vals)

    # ---------- 子因子 3：波动率惩罚（Vol_N） ----------
    short_w = g.vol_window_short
    long_w = g.vol_window_long

    if len(n_log_returns) >= long_w:
        short_vols = np.array([
            np.std(n_log_returns[i:i+short_w], ddof=1)
            for i in range(len(n_log_returns) - short_w + 1)
        ])
        long_vols = np.array([
            np.std(n_log_returns[i:i+long_w], ddof=1)
            for i in range(len(n_log_returns) - long_w + 1)
        ])
        common_len = min(len(short_vols), len(long_vols))
        if common_len > 1:
            vol_ratios = short_vols[-common_len:] / np.maximum(long_vols[-common_len:], 1e-10)
            vol_current = vol_ratios[-1]
            vol_score = zscore_clip(vol_current, vol_ratios)
        else:
            vol_score = 0.0
    else:
        vol_score = 0.0

    # ---------- 子因子 4：风险偏好（RiskOn） ----------
    if len(nasdaq_prices) > min_len and len(gold_prices) > min_len:
        roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
        roc_g = ROC([gold_code], check_date=check_date, timeperiod=20)
        n_20d_ret = roc_n.get(nasdaq_code, 0.0) / 100.0
        g_20d_ret = roc_g.get(gold_code, 0.0) / 100.0
        riskon_score = 1.0 if (n_20d_ret > 0 and n_20d_ret > g_20d_ret) else 0.0
    else:
        riskon_score = 0.0

    # ---------- 复合因子得分 ----------
    s_N = (g.nasdaq_momentum_w * mom_score
           + g.nasdaq_trend_w * trend_score
           + g.nasdaq_riskon_w * riskon_score
           - g.nasdaq_volpenalty_w * vol_score)

    return float(np.clip(s_N, -1.0, 1.0))


# ============================================================
# compute_target_weights — 核心权重公式
# ============================================================
def compute_target_weights(volatilities, factor_scores, k):
    """
    根据核心公式计算目标权重。

    公式:
        raw_i = (1 + k × s_i) / (σ_i + ε)
        w_i = raw_i / Σ_j raw_j

    参数:
        volatilities: numpy array，长度 3，年化波动率 [σ_G, σ_A, σ_N]
        factor_scores: numpy array，长度 3，因子得分 [s_G, s_A, s_N]
        k: float，因子强度系数

    返回:
        numpy array，长度 3，归一化后的原始目标权重（和为 1）

    防御处理:
        - 当 1 + k×s_i < 0.01 时，裁剪为 0.01（避免负权重或零权重）
        - 波动率加 ε 防止除零
        - 所有权重之和 < ε 时回退到等权分配
    """

    # 调整因子项：1 + k × s_i，下界保护避免负值
    adjusted_factor = 1.0 + k * factor_scores
    adjusted_factor = np.maximum(adjusted_factor, 0.01)

    # 风险调整：除以波动率（加微小常数防除零）
    eps = 1e-10
    raw_weights = adjusted_factor / (volatilities + eps)

    # 归一化使总权重为 1
    total = np.sum(raw_weights)
    if total > eps:
        weights = raw_weights / total
    else:
        # 极端退化为等权分配
        weights = np.ones(3) / 3.0

    return weights


# ============================================================
# apply_weight_constraints — 三级权重约束
# ============================================================
def apply_weight_constraints(target_weights, current_weights, bounds, max_change):
    """
    对目标权重施加硬约束，通过 Duchi 有界单纯形投影确保全部条件同时满足。

    约束条件（必须全部满足）：
    1. 单资产上下限：w_i ∈ [lower_i, upper_i]
    2. 调仓幅度限制：|w_i - current_i| ≤ max_change（首日无持仓时跳过）
    3. 权重和为 1：Σ w_i = 1

    优先级：
        hard bounds（约束1）为最高优先级的安全约束，必须满足；
        max_change（约束2）为换手率控制，当与 hard bounds 冲突时被放宽。
        典型冲突场景：当前持仓已违反 hard bounds，需多周逐步修复。

    实现方式：
        将 max_change 与 bounds 合并为有效边界（effective bounds），
        然后通过 Duchi 二分查找投影到有界单纯形。
        算法保证一次收敛到满足所有约束的精确解，无需迭代。

    参数:
        target_weights: numpy array [3]，未施加约束的原始目标权重
        current_weights: numpy array [3]，当前各 ETF 的持仓权重
        bounds: list of (lower, upper) tuples，各资产权重范围
        max_change: float，单次调仓最大变化幅度（绝对值）

    返回:
        numpy array [3]，同时满足全部约束的最终目标权重
    """

    lower_bounds = np.array([b[0] for b in bounds])
    upper_bounds = np.array([b[1] for b in bounds])
    has_position = np.sum(current_weights) > 1e-10

    # 合并 max_change 与 bounds → 有效边界
    if has_position:
        effective_lower = np.maximum(lower_bounds, current_weights - max_change)
        effective_upper = np.minimum(upper_bounds, current_weights + max_change)
    else:
        effective_lower = lower_bounds
        effective_upper = upper_bounds

    # 解决 max_change 与 hard bounds 的矛盾（当前持仓已违反 hard bounds 的场景）
    # hard bounds 优先级高于 max_change，放宽矛盾资产的有效边界
    for i in range(3):
        if effective_lower[i] > effective_upper[i]:
            effective_lower[i] = lower_bounds[i]
            effective_upper[i] = upper_bounds[i]

    # 防御：有效下界之和 > 1 或有效上界之和 < 1 时无可行解
    # 此时放宽 max_change，仅使用 hard bounds 再次尝试
    if np.sum(effective_lower) > 1.0 + 1e-10 or np.sum(effective_upper) < 1.0 - 1e-10:
        log.warning("【权重约束】含 max_change 无可行解（下界和=%.4f, 上界和=%.4f），"
                    "放宽至 hard bounds 重试" % (np.sum(effective_lower), np.sum(effective_upper)))
        effective_lower = lower_bounds
        effective_upper = upper_bounds

        # hard bounds 本身仍不可行则回退到等权分配
        if np.sum(effective_lower) > 1.0 + 1e-10 or np.sum(effective_upper) < 1.0 - 1e-10:
            log.warning("【权重约束】hard bounds 亦不可行，回退到等权分配")
            w_fallback = np.clip(np.ones(3) / 3.0, effective_lower, effective_upper)
            return w_fallback / np.sum(w_fallback)

    # 初始裁剪到有效边界内
    w = np.clip(target_weights, effective_lower, effective_upper)
    total = np.sum(w)

    # 已在单纯形上，直接返回
    if abs(total - 1.0) < 1e-12:
        return w

    # 防御：全零或接近零的退化情况
    if total < 1e-12:
        w = np.clip(np.ones(3) / 3.0, effective_lower, effective_upper)
        return w / np.sum(w)

    # Duchi 有界单纯形投影：二分查找阈值 θ
    # 使 Σ clip(w_i - θ, l_i, u_i) = 1
    theta_low = np.min(w) - np.max(upper_bounds)
    theta_high = np.max(w) - np.min(effective_lower)

    for _ in range(50):
        theta = (theta_low + theta_high) / 2.0
        w_proj = np.clip(w - theta, effective_lower, effective_upper)
        total_proj = np.sum(w_proj)

        if abs(total_proj - 1.0) < 1e-12:
            return w_proj

        if total_proj < 1.0:
            theta_high = theta
        else:
            theta_low = theta

    # 最终收敛值（50 次迭代后取最后一次投影结果）
    return np.clip(w - theta, effective_lower, effective_upper)
