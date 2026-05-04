enable_profile()

"""
============================================================
策略名称：ETF 多因子轮动策略（线性乘数版）
策略类型：周线级别、场内基金、多因子动态配置
适用标的：AI ETF（159819）、纳指100 ETF（513100）、黄金 ETF（518880）

核心思想：
  趋势门槛判断"能不能买"，动量排序决定"买谁"，风险平价分配基础仓位，
  RSRS 线性修正和拥挤度线性惩罚在价格结构转弱或交易过热时平滑降仓，
  组合波动率控制缩放总仓位。剩余仓位保留现金，不重新归一化到满仓。

模块分工：
  - 趋势门槛（硬过滤）：120 日均线以上才可入选，0/1 离散
  - 动量选择（TopK）：多周期排名分数加权，选前 K 只
  - 风险平价（逆波动率）：σ 越小权重越大，波动率归一化
  - RSRS 修正（只减不加）：High~Low 回归 β 标准化 × R²，线性截断到 [0, 1]
  - 拥挤度惩罚（只减不加）：五指标分位数均值，超阈值线性打折
  - 组合波动率控制（只缩不放）：RawWeight 组合波动率超目标时等比缩放

核心公式：
  FinalWeight_i = RPWeight_i × TrendGate_i × RSRSMultiplier_i
                × CrowdPenalty_i × PortfolioVolScale

调仓频率：每周开盘检查一次
============================================================
"""

import numpy as np
import pandas as pd


# ============================================================
# initialize — 策略初始化
# ============================================================
def initialize(context):
    """
    由聚宽框架在回测/模拟启动时自动调用一次。

    作用：
    - 向 g 对象写入全部策略参数
    - 设置交易费用（场内基金免印花税，佣金万分之一）
    - 设置固定滑点 0
    - 注册每周开盘调仓任务
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

    run_weekly(
        weekly_check,
        weekday=1,
        time='open',
        reference_security='000300.XSHG'
    )


# ============================================================
# set_parameter — 策略参数集中设置
# ============================================================
def set_parameter(context):
    """
    将所有策略参数写入 g 全局对象，便于集中管理和回测参数扫描。

    参数类别：资产池、趋势门槛、动量选择、风险平价、RSRS 修正、
    拥挤度惩罚、组合波动率控制、仓位交易约束。
    """

    # ---- 资产池 ----
    g.etf_pool = [
        '159819.XSHE',   # AI ETF
        '513100.XSHG',   # 纳指100 ETF
        '518880.XSHG',   # 黄金 ETF
    ]
    g.etf_names = ['AI ETF', '纳指100ETF', '黄金ETF']

    # ---- 趋势门槛 ----
    g.MA_long = 120

    # ---- 动量选择 ----
    g.MomShort = 20
    g.MomMid = 60
    g.MomLong = 120
    g.w20 = 0.2
    g.w60 = 0.3
    g.w120 = 0.5
    g.TopK = 2

    # ---- 风险平价 ----
    g.VolWindow = 60
    g.annual_factor = 252

    # ---- RSRS 修正 ----
    g.RSRS_N = 18        # 回归窗口
    g.RSRS_M = 600       # 标准化窗口
    g.RSRS_NegativeFullCut = 1.0
    g.RSRSMinMultiplier = 0.0
    g.RSRSMaxMultiplier = 1.0

    # ---- 拥挤度惩罚 ----
    g.CrowdWindow = 500
    g.CrowdRetShort = 20
    g.CrowdRetMid = 60
    g.AmountMAWindow = 20
    g.DeviationMAWindow = 20
    g.CrowdVolWindow = 20
    g.CrowdStart = 0.60
    g.CrowdEnd = 0.95
    g.MinCrowdPenalty = 0.30

    # ---- 组合波动率控制 ----
    g.PortfolioVolWindow = 60
    g.TargetVol = 0.12
    g.MaxPortfolioVolScale = 1.0

    # ---- 仓位与交易约束 ----
    g.MaxWeight = 0.60
    g.MinWeight = 0.05
    g.RebalanceThreshold = 0.03
    g.MaxTotalWeight = 1.0

    # ---- 数据与基准 ----
    g.live_days = max(
        g.MA_long, g.MomLong, g.RSRS_M,
        g.CrowdWindow, g.PortfolioVolWindow
    ) + 50
    g.benchmark = '000300.XSHG'


# ============================================================
# weekly_check — 周频调仓主函数
# ============================================================
def weekly_check(context):
    """每周开盘时执行一次完整的调仓流程。"""
    pool = g.etf_pool
    n = len(pool)

    # 1. 拉取历史数据
    prices = get_history_data(context, pool)

    # 2. 计算趋势门槛
    trend_gates = compute_trend_gates(prices, pool)

    # 3. 筛选趋势成立资产，计算动量分数
    momentum_scores = compute_momentum_scores(prices, pool, trend_gates)

    # 4. TopK 选择
    selected = select_topk(momentum_scores, trend_gates)

    # 5. 风险平价基础权重
    rp_weights = compute_rp_weights(prices, pool, selected)

    # 6. RSRS 线性修正乘数
    rsrs_multipliers = compute_rsrs_multipliers(prices, pool)

    # 7. 拥挤度线性惩罚乘数
    crowd_penalties = compute_crowd_penalties(prices, pool)

    # 8. 合成 RawWeight
    raw_weights = np.zeros(n)
    for i in range(n):
        if selected[i]:
            raw_weights[i] = (
                rp_weights[i]
                * trend_gates[i]
                * rsrs_multipliers[i]
                * crowd_penalties[i]
            )

    # 9. 组合波动率缩放
    portfolio_vol_scale = compute_portfolio_vol_scale(prices, pool, raw_weights)

    # 10. 最终权重
    final_weights = raw_weights * portfolio_vol_scale

    # 11. 应用交易约束
    final_weights = apply_weight_constraints(final_weights, n)

    # 12. 执行调仓
    execute_rebalance(context, pool, final_weights)


# ============================================================
# get_history_data — 拉取历史行情数据
# ============================================================
def get_history_data(context, pool):
    """
    拉取足够长的历史 OHLC + 成交额数据。

    返回 dict，键为 count 天，值为 DataFrame（columns 为各 ETF）。
    """
    max_window = max(
        g.MA_long, g.MomLong, g.RSRS_M,
        g.CrowdWindow, g.PortfolioVolWindow
    )
    needed = max_window + 100

    prices = {}

    close_df = get_price(
        pool,
        count=needed,
        frequency='daily',
        fields=['close'],
        skip_paused=True,
        fq='pre'
    )['close']

    high_df = get_price(
        pool,
        count=needed,
        frequency='daily',
        fields=['high'],
        skip_paused=True,
        fq='pre'
    )['high']

    low_df = get_price(
        pool,
        count=needed,
        frequency='daily',
        fields=['low'],
        skip_paused=True,
        fq='pre'
    )['low']

    amount_df = get_price(
        pool,
        count=needed,
        frequency='daily',
        fields=['money'],
        skip_paused=True,
        fq='pre'
    )['money']

    prices['close'] = close_df
    prices['high'] = high_df
    prices['low'] = low_df
    prices['amount'] = amount_df

    return prices


# ============================================================
# compute_trend_gates — 趋势门槛（硬过滤）
# ============================================================
def compute_trend_gates(prices, pool):
    """
    使用 120 日均线判断趋势方向。

    返回: list[float]，1.0 表示通过，0.0 表示剔除
    """
    close = prices['close']
    ma_window = g.MA_long

    gates = np.zeros(len(pool))
    for i, etf in enumerate(pool):
        if etf not in close.columns:
            continue
        series = close[etf].dropna()
        if len(series) < ma_window:
            continue
        ma = series.iloc[-ma_window:].mean()
        current_close = series.iloc[-1]
        if current_close > ma:
            gates[i] = 1.0
    return gates


# ============================================================
# compute_momentum_scores — 多周期排名动量分数
# ============================================================
def compute_momentum_scores(prices, pool, trend_gates):
    """
    在趋势成立的资产中，计算多周期排名动量分数。

    对每个周期（20/60/120 日）收益率做排名，转化为 0~1 分数，
    再按权重加总。

    返回: np.array，未通过趋势门槛的资产分数为 0
    """
    close = prices['close']
    n = len(pool)
    scores = np.zeros(n)

    windows = [g.MomShort, g.MomMid, g.MomLong]
    weights = [g.w20, g.w60, g.w120]

    # 收集趋势成立资产的各周期收益率
    active_indices = [i for i in range(n) if trend_gates[i] > 0]
    if not active_indices:
        return scores

    # 计算每只资产各周期收益率
    returns = np.zeros((n, 3))
    for i in range(n):
        etf = pool[i]
        if etf not in close.columns:
            continue
        series = close[etf].dropna()
        if len(series) < max(windows):
            continue
        for j, w in enumerate(windows):
            if len(series) > w:
                returns[i, j] = series.iloc[-1] / series.iloc[-(w + 1)] - 1

    # 对活跃资产在每个周期上排名打分
    for j in range(3):
        active_ret = [(i, returns[i, j]) for i in active_indices]
        active_ret.sort(key=lambda x: x[1], reverse=True)
        n_active = len(active_ret)
        if n_active == 1:
            scores[active_ret[0][0]] += weights[j]
        elif n_active > 1:
            for rank, (idx, _) in enumerate(active_ret):
                rank_score = (n_active - rank - 1) / (n_active - 1)
                scores[idx] += weights[j] * rank_score

    return scores


# ============================================================
# select_topk — TopK 入选
# ============================================================
def select_topk(momentum_scores, trend_gates):
    """
    在趋势成立资产中按动量分数从高到低选择前 TopK 只。

    返回: list[bool]，入选为 True
    """
    n = len(momentum_scores)
    selected = [False] * n

    active = [(i, momentum_scores[i]) for i in range(n) if trend_gates[i] > 0]
    active.sort(key=lambda x: x[1], reverse=True)

    k = min(g.TopK, len(active))
    for idx, _ in active[:k]:
        selected[idx] = True

    return selected


# ============================================================
# compute_rp_weights — 逆波动率风险平价
# ============================================================
def compute_rp_weights(prices, pool, selected):
    """
    对入选资产计算逆波动率风险平价权重。

    未入选资产权重为 0。
    如果只有一只入选，权重为 1。

    返回: np.array
    """
    close = prices['close']
    n = len(pool)
    vol_window = g.VolWindow
    annual_factor = g.annual_factor

    weights = np.zeros(n)
    selected_indices = [i for i in range(n) if selected[i]]

    if not selected_indices:
        return weights

    vols = np.zeros(n)
    for i in selected_indices:
        etf = pool[i]
        if etf not in close.columns:
            continue
        series = close[etf].dropna()
        if len(series) < vol_window + 1:
            continue
        daily_ret = series.pct_change().dropna().iloc[-vol_window:]
        if len(daily_ret) < 5:
            vols[i] = 1.0  # 数据不足，给等波动率
        else:
            vols[i] = daily_ret.std() * np.sqrt(annual_factor)
            if vols[i] < 1e-8:
                vols[i] = 1e-8

    inverse_vols = np.zeros(n)
    for i in selected_indices:
        if vols[i] > 0:
            inverse_vols[i] = 1.0 / vols[i]

    total_inv_vol = inverse_vols.sum()
    if total_inv_vol > 0:
        weights = inverse_vols / total_inv_vol

    return weights


# ============================================================
# compute_rsrs_multipliers — RSRS 线性修正乘数
# ============================================================
def compute_rsrs_multipliers(prices, pool):
    """
    对每只 ETF 计算 RSRS 截断线性乘数。

    步骤：
    1. 过去 RSRS_N 日 High ~ Low 回归，得 β 和 R²
    2. 过去 RSRS_M 日 β 标准化，得 RSRS_Z
    3. RSRS_Adj = RSRS_Z × R²
    4. RSRSMultiplier = clip(1 + RSRS_Adj / NegativeFullCut, 0, 1)

    只减仓，不加仓。

    返回: np.array
    """
    high = prices['high']
    low = prices['low']
    n = len(pool)

    N = g.RSRS_N
    M = g.RSRS_M
    full_cut = g.RSRS_NegativeFullCut

    multipliers = np.ones(n)

    for i, etf in enumerate(pool):
        if etf not in high.columns or etf not in low.columns:
            continue
        h = high[etf].dropna()
        l = low[etf].dropna()

        # 对齐索引
        common_idx = h.index.intersection(l.index)
        h = h.loc[common_idx]
        l = l.loc[common_idx]

        min_len = M + N
        if len(h) < min_len:
            multipliers[i] = 1.0
            continue

        # 滚动计算 β
        betas = []
        r2s = []
        for t in range(M + N - 1, len(h)):
            h_window = h.iloc[t - N + 1:t + 1].values
            l_window = l.iloc[t - N + 1:t + 1].values
            if len(h_window) < N or np.std(l_window) < 1e-10:
                betas.append(1.0)
                r2s.append(0.0)
                continue
            try:
                X = np.column_stack([np.ones(len(l_window)), l_window])
                coeffs, residuals, rank, _ = np.linalg.lstsq(X, h_window, rcond=None)
                betas.append(coeffs[1] if len(coeffs) > 1 else 1.0)

                ss_res = residuals[0] if len(residuals) > 0 else 0
                ss_tot = np.sum((h_window - np.mean(h_window)) ** 2)
                r2 = 1 - ss_res / ss_tot if ss_tot > 1e-10 else 0.0
                r2s.append(max(r2, 0.0))
            except Exception:
                betas.append(1.0)
                r2s.append(0.0)

        if len(betas) < M:
            multipliers[i] = 1.0
            continue

        # 取最近 M 个 β 做标准化
        beta_series = np.array(betas[-M:])
        mean_beta = np.mean(beta_series)
        std_beta = np.std(beta_series)

        if std_beta < 1e-10:
            rsrs_z = 0.0
        else:
            rsrs_z = (beta_series[-1] - mean_beta) / std_beta

        # 使用最近一期的 R²
        latest_r2 = r2s[-1] if r2s else 0.0
        rsrs_adj = rsrs_z * latest_r2

        # 截断线性乘数（只减不加）
        raw_mult = 1.0 + rsrs_adj / full_cut
        multipliers[i] = np.clip(raw_mult, g.RSRSMinMultiplier, g.RSRSMaxMultiplier)

    return multipliers


# ============================================================
# compute_crowd_penalties — 拥挤度线性惩罚乘数
# ============================================================
def compute_crowd_penalties(prices, pool):
    """
    对每只 ETF 计算拥挤度线性惩罚乘数。

    五类指标：20日涨幅分位、60日涨幅分位、成交额分位、
    偏离均线分位、短期波动率分位，取均值后线性映射到惩罚乘数。

    只减仓，不加仓。

    返回: np.array
    """
    close = prices['close']
    amount = prices['amount']
    n = len(pool)

    crowd_window = g.CrowdWindow
    start = g.CrowdStart
    end = g.CrowdEnd
    min_penalty = g.MinCrowdPenalty

    penalties = np.ones(n)

    for i, etf in enumerate(pool):
        if etf not in close.columns:
            continue

        c = close[etf].dropna()
        if len(c) < crowd_window:
            penalties[i] = 1.0
            continue

        # 取最近 crowd_window 日数据
        c_recent = c.iloc[-crowd_window:]

        # 存储各指标分位数
        indicators = []

        # 8.2.1 20日涨幅分位数
        ret20 = c_recent / c_recent.shift(g.CrowdRetShort) - 1
        indicators.append(percentile_rank(ret20.dropna().iloc[-1], ret20.dropna()))

        # 8.2.2 60日涨幅分位数
        ret60 = c_recent / c_recent.shift(g.CrowdRetMid) - 1
        indicators.append(percentile_rank(ret60.dropna().iloc[-1], ret60.dropna()))

        # 8.2.3 成交额分位数
        if etf in amount.columns:
            amt = amount[etf].dropna()
            amt = amt.loc[amt.index.intersection(c_recent.index)]
            if len(amt) >= g.AmountMAWindow:
                amt_ma20 = amt.rolling(g.AmountMAWindow).mean().dropna()
                if len(amt_ma20) > 0:
                    indicators.append(
                        percentile_rank(amt_ma20.iloc[-1], amt_ma20)
                    )
                else:
                    indicators.append(0.5)
            else:
                indicators.append(0.5)
        else:
            indicators.append(0.5)

        # 8.2.4 偏离均线程度分位数
        ma20 = c_recent.rolling(g.DeviationMAWindow).mean()
        deviation = c_recent / ma20 - 1
        deviation_valid = deviation.dropna()
        if len(deviation_valid) > 0:
            indicators.append(
                percentile_rank(deviation_valid.iloc[-1], deviation_valid)
            )
        else:
            indicators.append(0.5)

        # 8.2.5 短期波动率分位数
        vol20 = c_recent.pct_change().rolling(g.CrowdVolWindow).std() * np.sqrt(g.annual_factor)
        vol_valid = vol20.dropna()
        if len(vol_valid) > 0:
            indicators.append(
                percentile_rank(vol_valid.iloc[-1], vol_valid)
            )
        else:
            indicators.append(0.5)

        # 拥挤度总分
        crowd_score = np.mean(indicators)

        # 线性惩罚映射
        if crowd_score <= start:
            penalty = 1.0
        elif crowd_score >= end:
            penalty = min_penalty
        else:
            penalty = 1.0 - (crowd_score - start) / (end - start) * (1.0 - min_penalty)
            penalty = max(min_penalty, min(1.0, penalty))

        penalties[i] = penalty

    return penalties


# ============================================================
# percentile_rank — 计算分位数排名（0~1）
# ============================================================
def percentile_rank(value, series):
    """
    计算 value 在 series 中的分位数（0~1）。

    返回 0 表示 value 是序列中最小值，返回 1 表示最大值。
    """
    if len(series) == 0:
        return 0.5
    ranked = (series < value).mean()
    return float(ranked)


# ============================================================
# compute_portfolio_vol_scale — 组合波动率缩放系数
# ============================================================
def compute_portfolio_vol_scale(prices, pool, raw_weights):
    """
    根据 RawWeight 和协方差矩阵计算组合波动率，按目标波动率缩放。

    只缩不放（最大系数为 1.0）。

    返回: float
    """
    close = prices['close']
    vol_window = g.PortfolioVolWindow
    target_vol = g.TargetVol
    annual_factor = g.annual_factor

    n = len(pool)
    active_indices = [i for i in range(n) if raw_weights[i] > 1e-8]

    if not active_indices:
        return 1.0

    # 构建收益率矩阵 (vol_window, n_active)
    returns_list = []
    for i in active_indices:
        etf = pool[i]
        if etf not in close.columns:
            return 1.0
        series = close[etf].dropna().iloc[-(vol_window + 1):]
        ret = series.pct_change().dropna()
        if len(ret) < vol_window:
            return 1.0
        returns_list.append(ret.values[-vol_window:])

    if not returns_list:
        return 1.0

    ret_matrix = np.column_stack(returns_list)
    cov_daily = np.atleast_2d(np.cov(ret_matrix, rowvar=False))
    cov_annual = cov_daily * annual_factor

    active_weights = np.array([raw_weights[i] for i in active_indices])
    portfolio_var = active_weights @ cov_annual @ active_weights
    portfolio_vol = np.sqrt(max(portfolio_var, 0))

    if portfolio_vol <= target_vol or portfolio_vol < 1e-8:
        return 1.0

    scale = target_vol / portfolio_vol
    return min(scale, g.MaxPortfolioVolScale)


# ============================================================
# apply_weight_constraints — 应用仓位约束
# ============================================================
def apply_weight_constraints(final_weights, n):
    """
    应用单资产最大仓位和最小有效仓位约束。

    不重新归一化。
    """
    max_w = g.MaxWeight
    min_w = g.MinWeight

    result = np.copy(final_weights)

    for i in range(n):
        # 单资产最大仓位上限
        if result[i] > max_w:
            result[i] = max_w
        # 最小有效仓位裁剪
        if result[i] < min_w:
            result[i] = 0.0

    return result


# ============================================================
# execute_rebalance — 执行调仓
# ============================================================
def execute_rebalance(context, pool, final_weights):
    """
    根据最终目标权重执行调仓，应用最小调仓阈值。
    剩余仓位保留为现金。
    """
    account_value = context.portfolio.total_value

    for i, etf in enumerate(pool):
        target_value = account_value * final_weights[i]
        current_pos = context.portfolio.positions[etf]
        current_value = current_pos.total_amount * current_pos.price if current_pos.total_amount > 0 else 0
        current_weight = current_value / account_value if account_value > 0 else 0

        # 如果目标权重为 0 且当前仓位为 0，跳过
        if final_weights[i] == 0 and current_weight == 0:
            continue

        # 最小调仓阈值
        if abs(final_weights[i] - current_weight) < g.RebalanceThreshold:
            continue

        order_target_value(etf, target_value)
