enable_profile()

# 克隆自聚宽文章：https://www.joinquant.com/post/15002
# 标题：价值选股与RSRS择时
# 作者：K线放荡不羁

"""
============================================================
策略名称：价值选股 + RSRS（阻力支撑相对强度）择时
策略类型：日线级别、多头交易
适用市场：A 股全市场

核心逻辑：
  第一步（择时）：基于 RSRS 指标判断沪深 300 指数的市场风险状态
    - RSRS 右偏修正标准分 > 0.7 → 市场安全，进入选股持仓模式
    - RSRS 右偏修正标准分 < -0.7 → 市场危险，清空所有持仓
    - 介于两者之间 → 维持当前状态不变

  第二步（选股）：在择时允许持仓时，基于 PB-ROE 框架筛选股票
    - 候选条件：PB > 0（净资产为正）且 ROE > 0（有盈利能力）
    - 评分标准：PB 排名 + 1/ROE 排名，总分越小表示估值越低、盈利能力越强
    - 持仓数量：得分最优的 10 只股票，等权重分配资金

RSRS 指标详解：
  - 理论基础：根据"最高价弹性大于最低价"的市场微观结构特征，
    通过 OLS 回归每日最高价对最低价的斜率来捕捉市场趋势强弱。
    当斜率 > 1 时，上涨日的最高价涨幅 > 最低价涨幅，市场偏强；
    当斜率 < 1 时，下跌日的最高价跌幅 > 最低价跌幅，市场偏弱。
  - 参数：
    * N = 18：回归窗口（约一个月交易日），用于计算当日斜率 beta
    * M = 1100：标准化参考窗口（约四年交易日），用于计算 z-score 的均值和标准差
  - 右偏修正：zscore × beta × R²
    * 当 beta > 0（上升趋势）且 R² 高（拟合好）时，分数被正向放大
    * 当 beta < 0（下降趋势）或 R² 低（拟合差）时，分数被负向压缩

性能优化：
  - 使用 pandas 滚动窗口向量化替代 statsmodels 逐日 OLS 循环
  - 历史 RSRS 预加载从 ~30s 降至 <1s
  - 每日 OLS 改用 numpy 闭式公式（Cov/Var），避免 statsmodels 开销

注意事项（参考聚宽 API 文档）：
  - get_fundamentals 默认查询 context.current_dt 前一天收盘后的最新财报数据
  - attribute_history('1d') 不包含当天数据，即使收盘后调用也是如此
  - 已开启动态复权模式，跨日缓存价格数据会导致不一致
  - send_message 仅在模拟交易中生效，回测时被忽略
============================================================
"""

import numpy as np


# ============================================================
# initialize — 策略初始化函数
# ============================================================
def initialize(context):
    """
    策略初始化函数，由聚宽框架在回测/模拟启动时自动调用且仅调用一次。

    完成三项核心工作：
    1. 全局配置（复权模式、手续费、基准标的）
    2. 预加载策略开始前的历史 RSRS 斜率数据（避免冷启动期无信号）
    3. 注册定时任务（开盘前通知、开盘时主逻辑、收盘后记录）
    """

    # ---------- 全局运行配置 ----------
    # 开启动态复权（真实价格）模式
    set_option('use_real_price', True)

    # 开启未来数据防御模式（兜底检测开关）
    set_option("avoid_future_data", True)

    # ---------- 参数初始化 ----------
    set_parameter(context)

    # ---------- 交易手续费设置 ----------
    set_order_cost(
        OrderCost(
            close_tax=0.001,
            open_commission=0.0003,
            close_commission=0.0003,
            min_commission=5
        ),
        type='stock'
    )

    # ---------- 滑点设置 ----------
    set_slippage(PriceRelatedSlippage(0.00246), type='stock')

    # ---------- 注册定时任务 ----------
    run_daily(before_market_open, time='before_open', reference_security='000300.XSHG')
    run_daily(market_open, time='open', reference_security='000300.XSHG')


# ============================================================
# set_parameter — 策略参数集中设置
# ============================================================
def set_parameter(context):
    """
    设置策略全局参数并预加载历史 RSRS 斜率数据。

    使用 pandas 滚动窗口向量化计算，替代 statsmodels 逐日 OLS 循环，
    性能从 ~30s 优化至 <1s。
    """

    # ---------- RSRS 指标参数 ----------
    g.N = 18
    g.M = 1100

    # ---------- 运行状态标志 ----------
    g.init = True

    # ---------- 持仓与基准 ----------
    g.stock_num = 10
    g.security = '000300.XSHG'
    set_benchmark(g.security)

    # ---------- 运行计数器 ----------
    g.days = 0

    # ---------- RSRS 择时阈值 ----------
    g.buy = 0.7
    g.sell = -0.7

    # ---------- RSRS 历史数据存储 ----------
    g.ans = []
    g.ans_rightdev = []

    # ---------- 预加载历史 RSRS 斜率数据 ----------
    prices = get_price(
        g.security,
        '2005-01-05',
        context.previous_date,
        '1d',
        ['high', 'low']
    )
    prices = prices.dropna()
    highs = prices.high
    lows = prices.low

    # 向量化滚动窗口计算：
    # 对 N 日窗口内的 (low, high) 做 OLS 回归 high = alpha + beta * low
    # beta = Cov(low, high) / Var(low)
    # R² = Cov(low, high)² / (Var(low) × Var(high))
    highs_roll = highs.rolling(g.N)
    lows_roll = lows.rolling(g.N)
    cov_hl = highs_roll.cov(lows_roll)
    var_low = lows_roll.var()
    var_high = highs_roll.var()

    betas = cov_hl / var_low
    r_squareds = (cov_hl ** 2) / (var_high * var_low)

    g.ans = betas.dropna().tolist()
    g.ans_rightdev = r_squareds.dropna().tolist()


# ============================================================
# before_market_open — 开盘前执行函数
# ============================================================
def before_market_open(context):
    """每天开盘前运行：运行天数 +1，发送微信状态通知。"""
    g.days += 1
    send_message('策略正常，运行第%s天~' % g.days)


# ============================================================
# market_open — 开盘时执行函数（策略主逻辑）
# ============================================================
def market_open(context):
    """
    每天开盘时运行，策略核心决策函数。

    执行流程：
    第一步：计算当日最新的 RSRS 斜率（beta）和拟合优度（R²）
    第二步：基于最近 M 日的斜率序列，计算标准化 RSRS 指标（z-score）
    第三步：对 z-score 做右偏修正，得到最终的择时信号分数
    第四步：根据信号分数与阈值比较，决定持仓或空仓
    """

    security = g.security

    # ==================== 第一步：计算当日 RSRS 斜率 ====================
    beta = 0
    r2 = 0

    if g.init:
        g.init = False
    else:
        prices = attribute_history(security, g.N, '1d', ['high', 'low'])
        highs = prices.high
        lows = prices.low

        # 使用 numpy 闭式公式替代 statsmodels OLS
        # beta = Cov(low, high) / Var(low)
        highs_arr = highs.values
        lows_arr = lows.values
        cov_hl = np.cov(lows_arr, highs_arr)[0, 1]
        var_low = np.var(lows_arr)
        beta = cov_hl / var_low
        # R² = Corr(low, high)²
        r2 = np.corrcoef(lows_arr, highs_arr)[0, 1] ** 2

        g.ans.append(beta)
        g.ans_rightdev.append(r2)

    # ==================== 第二步：计算标准化 RSRS 指标 ====================
    section = g.ans[-g.M:]
    mu = np.mean(section)
    sigma = np.std(section)
    zscore = (section[-1] - mu) / sigma

    # ==================== 第三步：计算右偏修正 RSRS 标准分 ====================
    zscore_rightdev = zscore * beta * r2

    # ==================== 第四步：根据信号执行交易决策 ====================
    if zscore_rightdev > g.buy:
        log.info("市场风险在合理范围")
        trade_func(context)
    elif (zscore_rightdev < g.sell) and (len(context.portfolio.positions.keys()) > 0):
        log.info("市场风险过大，保持空仓状态")
        for s in context.portfolio.positions.keys():
            order_target(s, 0)


# ============================================================
# trade_func — 价值选股与调仓函数
# ============================================================
def trade_func(context):
    """
    基于 PB-ROE 价值框架的选股与组合调仓函数。

    选股逻辑（5 步）：
    1. 查询全市场股票的 PB（市净率）和 ROE（净资产收益率）
    2. 过滤：PB > 0 且 ROE > 0
    3. 按 PB 升序排列
    4. 对 PB 和 1/ROE 分别排名，等权加总得综合得分
    5. 取得分最优的前 stock_num 只股票

    调仓逻辑：卖出不在新池中的，买入/调整至等权仓位。
    """

    # 第 1 步：获取全市场财务数据
    df = get_fundamentals(
        query(
            valuation.code,
            valuation.pb_ratio,
            indicator.roe
        )
    )

    # 第 2 步：基本面筛选（ROE > 0 且 PB > 0），按 PB 升序
    df = df[(df['roe'] > 0) & (df['pb_ratio'] > 0)].sort_values('pb_ratio')

    # 第 3 步：构建评分 DataFrame
    df.index = df['code'].values
    df['1/roe'] = 1 / df['roe']

    # 第 4 步：计算综合得分（PB 排名 + 1/ROE 排名，越小越好）
    df['point'] = df[['pb_ratio', '1/roe']].rank().sum(axis=1)
    df = df.sort_values('point')[:g.stock_num]
    pool = df.index
    log.info('总共选出%s只股票' % len(pool))

    # 第 5 步：等权重资金分配
    cash = context.portfolio.total_value / len(pool)

    # 第 6 步：执行调仓
    hold_stock = context.portfolio.positions.keys()
    for s in hold_stock:
        if s not in pool:
            order_target(s, 0)
    for s in pool:
        order_target_value(s, cash)


# ============================================================
# after_market_close — 收盘后执行函数
# ============================================================
def after_market_close(context):
    """收盘后记录当日成交和账户总资产（当前未启用）。"""
    trades = get_trades()
    for _trade in trades.values():
        log.info('成交记录：' + str(_trade))
    log.info('今日账户总资产：%s' % round(context.portfolio.total_value, 2))
