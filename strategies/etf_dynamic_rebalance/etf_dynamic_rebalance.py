# 策略名：ETF动态调仓
enable_profile()
STRATEGY_NAME = "ETF动态调仓"
import FeishuRelayTools

"""
============================================================
策略名称：ETF 动态调仓策略
策略类型：日线级别、场内基金、多资产动态配置
适用标的：黄金 ETF（518880）、AI ETF（159819）、纳指100 ETF（513100）

核心思想：
  黄金是防御资产（危机对冲），AI ETF 是高弹性进攻资产，纳指100 是核心成长资产。
  三类资产在不同宏观环境下表现分化——利用因子打分捕捉各资产当前所处的相对强弱
  状态，在风险平价框架上倾斜配置。

因子选择逻辑：
  - 黄金：趋势 + 相对强弱 + 风险厌恶（纳指下跌时黄金避险需求上升）
  - AI ETF：动量 + 趋势 - 波动率惩罚 - 回撤惩罚（高弹性资产需要同时奖励
    趋势强度和惩罚过度投机）
  - 纳指100：动量 + 趋势 + 风险偏好 - 波动率惩罚（中周期动量更稳定，
    风险偏好信号捕捉资金从防御转向成长的轮动）

核心公式：
  w_i ∝ (1 + k × s_i) / σ_i
  - k = 0.3，使最强/最弱资产权重比约 1.86（波动率相等时）
  - σ_i 为 60 日年化波动率，s_i ∈ [-1, 1] 为复合因子得分

权重约束（三级，按优先级）：
  1. 单资产上下限：黄金 10%~60%，AI 10%~50%（波动更大），纳指 10%~60%
  2. 单次调仓最大变化 ±10%
  3. 归一化使权重和为 1
  4. 偏离度阈值：当前权重与目标权重的绝对偏差之和超过阈值才触发调仓

调仓频率：每日开盘检查偏离度，偏离度超过阈值（默认 0.10）时调仓
============================================================
"""

import numpy as np
import pandas as pd
from jqlib.technical_analysis import BIAS, ROC


# ============================================================
# initialize — 策略初始化
# ============================================================
def initialize(context):
    """
    由聚宽框架在回测/模拟启动时自动调用一次。

    作用：
    - 向 g 对象写入全部策略参数
    - 设置交易费用（场内基金免印花税，佣金万分之一）
    - 设置固定滑点 0（ETF 流动性好，保守估计）
    - 注册每日开盘调仓检查任务
    """

    set_option('use_real_price', True)
    set_option("avoid_future_data", True)
    set_parameter(context)

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

    set_slippage(FixedSlippage(0.0), type='fund')

    run_daily(
        daily_check,
        time='open',
        reference_security='000300.XSHG'
    )


# ============================================================
# set_parameter — 策略参数集中设置
# ============================================================
def set_parameter(context):
    """
    将所有策略参数写入 g 全局对象，便于集中管理和回测参数扫描。

    涉及参数类别：资产池、波动率、因子权重、计算窗口、核心公式系数、
    权重约束、数据长度、基准。
    """

    # ETF 资产池
    g.etf_pool = [
        '518880.XSHG',   # 黄金 ETF
        '159819.XSHE',   # AI ETF
        '513100.XSHG',   # 纳指100 ETF
    ]
    g.etf_names = ['黄金ETF', 'AI ETF', '纳指100ETF']

    # 波动率
    g.volatility_window = 60
    g.annual_factor = 252

    # 黄金因子权重（和为 1）
    g.gold_trend_w = 0.5
    g.gold_rs_w = 0.3
    g.gold_riskoff_w = 0.2

    # AI 因子权重（和为 1）
    g.ai_momentum_w = 0.45
    g.ai_trend_w = 0.25
    g.ai_volpenalty_w = 0.20
    g.ai_drawdown_w = 0.10

    # 纳指因子权重（和为 1）
    g.nasdaq_momentum_w = 0.40
    g.nasdaq_trend_w = 0.20
    g.nasdaq_riskon_w = 0.20
    g.nasdaq_volpenalty_w = 0.20

    # 计算窗口
    g.trend_ma_window = 20
    g.momentum_window_short = 20   # AI ETF 用短周期动量（反应更灵敏）
    g.momentum_window_long = 60    # 纳指用中周期动量（避免噪音）
    g.vol_window_short = 20
    g.vol_window_long = 60
    g.drawdown_window = 60

    # 核心公式
    g.k = 0.3
    # k=0.3 → (1+0.3)/(1-0.3) ≈ 1.86，波动率相等时最强/最弱资产权重比

    # 权重约束
    g.weight_bounds = [
        (0.10, 0.60),  # 黄金
        (0.10, 0.50),  # AI（上限更低，控制高波动风险）
        (0.10, 0.60),  # 纳指
    ]
    g.max_weight_change = 0.10

    # 偏离度阈值
    g.rebalance_threshold = 0.10

    # 数据长度：100 日覆盖 60 日波动率 + 60 日动量 + 缓冲
    g.live_days = 100

    # 基准
    g.benchmark = '000300.XSHG'
    set_benchmark(g.benchmark)


# ============================================================
# daily_check — 每日检查与调仓主函数
# ============================================================
def daily_check(context):
    """
    由 run_daily 在每个交易日开盘时调用。

    流程：获取行情 → 计算波动率 → 计算因子得分 → 目标权重 →
          当前权重 → 偏离度检查 → (超阈值时) 施加约束 → 执行调仓
    """

    total_value = context.portfolio.total_value

    # 获取三只 ETF 近期收盘价
    # 逐 ETF 调用 get_price（panel=False 返回的 DataFrame 无法直接解析为多 ETF 宽表）
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

    if len(valid_etfs) < 3:
        log.info("【警告】部分 ETF 无价格数据，跳过本次调仓")
        return

    # 对齐不同上市时间的 ETF 价格序列：取最短长度尾部（最新日期对齐）
    valid_indices = [i for i, p in enumerate(prices_list) if p is not None]
    valid_prices = [prices_list[i] for i in valid_indices]
    min_len = min(len(p) for p in valid_prices)
    close_prices = pd.DataFrame({
        g.etf_pool[i]: valid_prices[j][-min_len:]
        for j, i in enumerate(valid_indices)
    })
    close_prices = close_prices.dropna()

    if len(close_prices) < 61:
        log.info("【警告】有效数据不足 61 日，跳过本次调仓")
        return

    # 计算 60 日年化波动率（对数收益率 → 样本标准差 → 年化）
    prices_array = close_prices.values
    log_returns = np.log(prices_array[1:] / prices_array[:-1])

    vol_window = min(g.volatility_window, len(log_returns))
    recent_returns = log_returns[-vol_window:]

    daily_std = np.std(recent_returns, axis=0, ddof=1)
    volatilities = daily_std * np.sqrt(g.annual_factor)

    log.info("年化波动率: G=%.4f, A=%.4f, N=%.4f" % (
        volatilities[0], volatilities[1], volatilities[2]
    ))

    # 分别计算三类资产的复合因子得分
    gold_prices = prices_array[:, 0]
    ai_prices = prices_array[:, 1]
    nasdaq_prices = prices_array[:, 2]

    check_date = context.previous_date
    gold_code, ai_code, nasdaq_code = g.etf_pool
    s_G = compute_gold_factors(gold_prices, nasdaq_prices, check_date,
                                gold_code=gold_code, nasdaq_code=nasdaq_code)
    s_A = compute_ai_factors(ai_prices, check_date, ai_code=ai_code)
    s_N = compute_nasdaq_factors(nasdaq_prices, gold_prices, check_date,
                                  nasdaq_code=nasdaq_code, gold_code=gold_code)

    factor_scores = np.clip(np.array([s_G, s_A, s_N]), -1.0, 1.0)

    log.info("因子得分: s_G=%.3f, s_A=%.3f, s_N=%.3f" % (
        factor_scores[0], factor_scores[1], factor_scores[2]
    ))

    # 计算目标权重
    inv_vol = 1.0 / (volatilities + 1e-10)
    rp_weights = inv_vol / np.sum(inv_vol)  # 纯风险平价（对照基准）

    raw_weights = compute_target_weights(volatilities, factor_scores, g.k)

    log.info("纯风险平价: G=%.3f, A=%.3f, N=%.3f" % (
        rp_weights[0], rp_weights[1], rp_weights[2]
    ))
    log.info("因子调整后: G=%.3f, A=%.3f, N=%.3f" % (
        raw_weights[0], raw_weights[1], raw_weights[2]
    ))

    # 获取当前持仓权重
    current_weights = np.zeros(3)
    for i, etf in enumerate(g.etf_pool):
        pos = context.portfolio.positions[etf]
        if pos is not None and pos.total_amount > 0:
            current_weights[i] = pos.value / total_value

    log.info("当前权重: G=%.3f, A=%.3f, N=%.3f" % (
        current_weights[0], current_weights[1], current_weights[2]
    ))

    # 偏离度检查：sum(|target_i - current_i|) 超过阈值才触发调仓
    deviation = np.sum(np.abs(raw_weights - current_weights))
    has_positions = np.sum(current_weights) > 1e-10

    if has_positions and deviation <= g.rebalance_threshold:
        log.info("偏离度 %.4f <= 阈值 %.2f，跳过本次调仓" % (
            deviation, g.rebalance_threshold
        ))
        return

    if has_positions:
        log.info("偏离度 %.4f > 阈值 %.2f，触发调仓" % (
            deviation, g.rebalance_threshold
        ))
    else:
        log.info("初始建仓：偏离度 %.4f，执行调仓" % deviation)

    # 施加约束并调仓
    final_weights = apply_weight_constraints(
        raw_weights,
        current_weights,
        g.weight_bounds,
        g.max_weight_change
    )

    log.info("最终权重: G=%.3f, A=%.3f, N=%.3f" % (
        final_weights[0], final_weights[1], final_weights[2]
    ))

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
# zscore_clip — z-score 标准化并裁剪
# ============================================================
def zscore_clip(current_value, historical_values, floor=-1.0, ceiling=1.0):
    """
    输入：
        current_value: 当前值
        historical_values: 历史值序列（numpy array，用于估算均值/标准差）
        floor, ceiling: 裁剪边界
    输出：
        标准化并裁剪到 [floor, ceiling] 的 z-score

    历史值不足 2 个或标准差接近 0 时，返回 0.0（中性信号），
    避免因样本不足导致极端值。
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
    s_G = 0.5 × Trend_G + 0.3 × RS_G + 0.2 × RiskOff

    黄金作为防御资产，核心逻辑：
    - 趋势权重最高（0.5）：黄金以趋势跟随为主
    - 相对强弱（0.3）：黄金跑赢纳指时通常是避险行情，应增配
    - 风险厌恶（0.2）：纳指下跌时避险需求升温，给黄金加分

    输入：黄金和纳指的价格序列（numpy array）
    输出：s_G ∈ [-1, 1]
    """

    min_len = g.trend_ma_window
    if len(gold_prices) <= min_len:
        return 0.0

    # 趋势：价格相对 20 日均线偏离率，z-score 标准化
    bias_result = BIAS([gold_code], check_date=check_date, N1=20)
    trend_current = bias_result[0].get(gold_code, 0.0) / 100.0

    gold_ma20 = np.convolve(gold_prices, np.ones(min_len)/min_len, mode='valid')
    gold_aligned = gold_prices[min_len-1:]
    trend_vals = (gold_aligned - gold_ma20) / gold_ma20
    trend_score = zscore_clip(trend_current, trend_vals)

    # 相对强弱：黄金 20 日超额收益（相对纳指），捕捉避险轮动
    if len(gold_prices) <= min_len or len(nasdaq_prices) <= min_len:
        rs_score = 0.0
    else:
        roc_g = ROC([gold_code], check_date=check_date, timeperiod=20)
        roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
        rs_current = (roc_g.get(gold_code, 0.0) - roc_n.get(nasdaq_code, 0.0)) / 100.0

        gold_20d_ret = gold_prices[min_len:] / gold_prices[:-min_len] - 1.0
        nasdaq_20d_ret = nasdaq_prices[min_len:] / nasdaq_prices[:-min_len] - 1.0
        rs_vals = gold_20d_ret - nasdaq_20d_ret
        rs_score = zscore_clip(rs_current, rs_vals)

    # 风险厌恶：纳指 20 日收益为负时激活
    if len(nasdaq_prices) > min_len:
        roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
        riskoff_score = 1.0 if roc_n.get(nasdaq_code, 0.0) < 0 else 0.0
    else:
        riskoff_score = 0.0

    s_G = (g.gold_trend_w * trend_score
           + g.gold_rs_w * rs_score
           + g.gold_riskoff_w * riskoff_score)

    return float(np.clip(s_G, -1.0, 1.0))


# ============================================================
# compute_ai_factors — AI ETF 复合因子得分
# ============================================================
def compute_ai_factors(ai_prices, check_date, ai_code='159819.XSHE'):
    """
    s_A = 0.45×Momentum + 0.25×Trend - 0.20×VolPenalty - 0.10×Drawdown

    AI ETF 属于高弹性进攻资产，核心逻辑：
    - 动量权重最高（0.45）：高弹性资产趋势一旦形成往往持续
    - 需要波动率惩罚和回撤惩罚：短期波动率快速膨胀或深度回撤通常
      预示高弹性资产即将回调，这两个惩罚项是风控核心

    输入：AI ETF 价格序列（numpy array）
    输出：s_A ∈ [-1, 1]
    """

    if len(ai_prices) < g.trend_ma_window + 1:
        return 0.0

    ai_log_returns = np.log(ai_prices[1:] / ai_prices[:-1])

    # 动量：20 日收益率 z-score（短周期，快速捕捉趋势）
    mom_w = g.momentum_window_short
    if len(ai_prices) > mom_w:
        roc_result = ROC([ai_code], check_date=check_date, timeperiod=20)
        roc20_current = roc_result.get(ai_code, 0.0) / 100.0

        roc20_series = ai_prices[mom_w:] / ai_prices[:-mom_w] - 1.0
        mom_score = zscore_clip(roc20_current, roc20_series)
    else:
        mom_score = 0.0

    # 趋势：价格相对 20 日均线偏离率
    min_len = g.trend_ma_window
    bias_result = BIAS([ai_code], check_date=check_date, N1=20)
    trend_current = bias_result[0].get(ai_code, 0.0) / 100.0

    ai_ma20 = np.convolve(ai_prices, np.ones(min_len)/min_len, mode='valid')
    ai_aligned = ai_prices[min_len-1:]
    trend_vals = (ai_aligned - ai_ma20) / ai_ma20
    trend_score = zscore_clip(trend_current, trend_vals)

    # 波动率惩罚：短期/长期波动率比
    # 比率升高意味着波动率在快速膨胀（投机过热），应降仓
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

    # 回撤惩罚：当前价格相对 60 日最高价的回撤幅度
    # 回撤越大扣分越多（floor=0 表示不奖励低回撤，只惩罚高回撤）
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
    s_N = 0.40×Momentum + 0.20×Trend + 0.20×RiskOn - 0.20×VolPenalty

    纳指作为核心成长资产，核心逻辑：
    - 动量用 60 日中周期（0.40），避免短周期噪音
    - 风险偏好信号（0.20）：纳指跑赢黄金时资金从防御转向成长
    - 波动率惩罚（0.20）：与 AI ETF 相同的逻辑，但权重更低（纳指波动
      本身小于 AI ETF，惩罚需求较弱）

    输入：纳指和黄金的价格序列（numpy array）
    输出：s_N ∈ [-1, 1]
    """

    if len(nasdaq_prices) < g.trend_ma_window + 1:
        return 0.0

    n_log_returns = np.log(nasdaq_prices[1:] / nasdaq_prices[:-1])

    # 动量：60 日收益率 z-score（中周期，比 AI 的 20 日更平滑）
    mom_long_w = g.momentum_window_long
    if len(nasdaq_prices) > mom_long_w:
        roc_result = ROC([nasdaq_code], check_date=check_date, timeperiod=60)
        roc60_current = roc_result.get(nasdaq_code, 0.0) / 100.0

        roc60_series = nasdaq_prices[mom_long_w:] / nasdaq_prices[:-mom_long_w] - 1.0
        mom_score = zscore_clip(roc60_current, roc60_series)
    else:
        mom_score = 0.0

    # 趋势：价格相对 20 日均线偏离率
    min_len = g.trend_ma_window
    bias_result = BIAS([nasdaq_code], check_date=check_date, N1=20)
    trend_current = bias_result[0].get(nasdaq_code, 0.0) / 100.0

    n_ma20 = np.convolve(nasdaq_prices, np.ones(min_len)/min_len, mode='valid')
    n_aligned = nasdaq_prices[min_len-1:]
    trend_vals = (n_aligned - n_ma20) / n_ma20
    trend_score = zscore_clip(trend_current, trend_vals)

    # 波动率惩罚：短期/长期波动率比
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

    # 风险偏好：纳指 20 日收益 > 0 且跑赢黄金 → 资金转向成长
    if len(nasdaq_prices) > min_len and len(gold_prices) > min_len:
        roc_n = ROC([nasdaq_code], check_date=check_date, timeperiod=20)
        roc_g = ROC([gold_code], check_date=check_date, timeperiod=20)
        n_20d_ret = roc_n.get(nasdaq_code, 0.0) / 100.0
        g_20d_ret = roc_g.get(gold_code, 0.0) / 100.0
        riskon_score = 1.0 if (n_20d_ret > 0 and n_20d_ret > g_20d_ret) else 0.0
    else:
        riskon_score = 0.0

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
    w_i ∝ (1 + k × s_i) / σ_i

    核心思路：以风险平价（1/σ_i）为基础，用因子得分 s_i 做倾斜。
    - s_i > 0 时，资产获得高于风险平价的配置
    - s_i < 0 时，低于风险平价的配置

    调整项 (1 + k×s_i) 下界裁剪到 0.01，防止极端负因子导致负权重。
    权重之和接近 0 时回退到等权分配。
    """

    adjusted_factor = 1.0 + k * factor_scores
    adjusted_factor = np.maximum(adjusted_factor, 0.01)

    eps = 1e-10
    raw_weights = adjusted_factor / (volatilities + eps)

    total = np.sum(raw_weights)
    if total > eps:
        weights = raw_weights / total
    else:
        weights = np.ones(3) / 3.0

    return weights


# ============================================================
# apply_weight_constraints — 三级权重约束
# ============================================================
def apply_weight_constraints(target_weights, current_weights, bounds, max_change):
    """
    对目标权重施加硬约束，返回满足全部条件的最终权重。

    约束（按优先级）：
    1. 上下限 [lower_i, upper_i]（安全约束，不可违反）
    2. 调仓幅度 |w_i - current_i| ≤ max_change（换手控制）
    3. 权重和为 1

    实现方式：Duchi 有界单纯形投影。
    先将 max_change 与 bounds 合并为有效边界，再通过二分查找找到 θ 使
    Σ clip(w_i - θ, l_i, u_i) = 1。一次收敛到精确解，无需迭代逼近。

    当 max_change 与 bounds 冲突时（如当前持仓已超出 bounds），
    bounds 优先，max_change 被放宽。
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

    # 处理冲突：有效下界 > 有效上界时，hard bounds 优先
    for i in range(3):
        if effective_lower[i] > effective_upper[i]:
            effective_lower[i] = lower_bounds[i]
            effective_upper[i] = upper_bounds[i]

    # 含 max_change 无可行解时，放宽到仅用 hard bounds
    if np.sum(effective_lower) > 1.0 + 1e-10 or np.sum(effective_upper) < 1.0 - 1e-10:
        log.warning("【权重约束】含 max_change 无可行解（下界和=%.4f, 上界和=%.4f），"
                    "放宽至 hard bounds 重试" % (np.sum(effective_lower), np.sum(effective_upper)))
        effective_lower = lower_bounds
        effective_upper = upper_bounds

        # hard bounds 本身不可行 → 退到等权
        if np.sum(effective_lower) > 1.0 + 1e-10 or np.sum(effective_upper) < 1.0 - 1e-10:
            log.warning("【权重约束】hard bounds 亦不可行，回退到等权分配")
            w_fallback = np.clip(np.ones(3) / 3.0, effective_lower, effective_upper)
            return w_fallback / np.sum(w_fallback)

    # Duchi 有界单纯形投影
    w = np.clip(target_weights, effective_lower, effective_upper)
    total = np.sum(w)

    if abs(total - 1.0) < 1e-12:
        return w

    if total < 1e-12:
        w = np.clip(np.ones(3) / 3.0, effective_lower, effective_upper)
        return w / np.sum(w)

    # 二分查找 θ 使 Σ clip(w_i - θ, l_i, u_i) = 1
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

    return np.clip(w - theta, effective_lower, effective_upper)
