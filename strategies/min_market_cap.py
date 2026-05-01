# -*- coding: utf-8 -*-
# 市值最小策略（小市值效应）
# 每天买入市值最小的前 stocksnum 只股票，卖出不再符合条件的持仓
import datetime as dt
import pandas as pd

def initialize(context):
    # 设置要持有的股票数量
    g.stocksnum = 10
    # 止损阈值：当持仓亏损超过8%时卖出
    g.stop_loss_pct = -0.08
    # 止盈阈值：当持仓盈利超过15%时卖出
    g.stop_profit_pct = 0.15
    # 设置基准为沪深300
    set_benchmark('000300.XSHG')
    # 使用真实价格（不复权）交易
    set_option('use_real_price', True)
    # 当日已止盈止损的股票集合（跨函数共享，避免同日买回已止损股）
    g.stopped_today = set()
    g.stopped_date = None
    # 每分钟检查止盈止损（轻量级，仅遍历持仓算盈亏，不查基本面）
    run_daily(check_stop_loss, time='every_bar', reference_security='000300.XSHG')
    # 每个交易日开盘时执行一次调仓（止盈止损已移至 check_stop_loss）
    run_daily(rebalance, 'open')
    # 输出初始化完成日志
    log.info('市值最小策略初始化完成，持仓%d只，止损%.0f%%，止盈%.0f%%' %
             (g.stocksnum, abs(g.stop_loss_pct) * 100, g.stop_profit_pct * 100))


def get_valid_stocks(context):
    """获取有效股票池：排除ST、上市不足60天的新股、科创板（结果按日期缓存）"""
    # 获取当前回测日期
    current_dt = context.current_dt
    # 缓存：日期未变则直接返回缓存结果
    cache_date = getattr(g, '_valid_stocks_cache_date', None)
    if cache_date is not None and cache_date == current_dt.date():
        return g._valid_stocks_cache

    # 一次性获取全A股DataFrame（含display_name、start_date等列）
    all_stocks = get_all_securities(['stock'], date=current_dt)

    # pandas向量化筛选：排除科创板（688开头）
    not_kcb = ~all_stocks.index.str.startswith('688')

    # pandas向量化筛选：排除上市不足60天的新股
    cutoff_date = current_dt.date() - dt.timedelta(days=60)
    # start_date转为datetime便于统一比较
    start_dates = pd.to_datetime(all_stocks['start_date'])
    old_enough = start_dates <= pd.to_datetime(cutoff_date)

    # 先应用快速筛选（科创板、上市时间），缩小后续ST查询的数据量
    pre_filtered = all_stocks[not_kcb & old_enough]
    codes = pre_filtered.index.tolist()

    # 使用get_extras获取回测当日的准确ST状态：API文档明确说明display_name仅反映最新名称，
    # 判断ST须使用get_extras('is_st', ...)
    if len(codes) > 0:
        df_st = get_extras('is_st', codes,
                           start_date=current_dt.date(),
                           end_date=current_dt.date())
        # df_st行索引为日期（仅1行），列索引为股票代码，值为True/False
        st_series = df_st.iloc[0]
        # True表示是ST，False或NaN表示非ST
        is_st = st_series.fillna(False).astype(bool)
        valid = st_series[~is_st].index.tolist()
    else:
        valid = []

    # 缓存结果，供后续同一交易日复用
    g._valid_stocks_cache_date = current_dt.date()
    g._valid_stocks_cache = valid
    # 返回有效股票代码列表
    return valid


def check_stop_loss(context):
    """每分钟检查止盈止损（轻量级，仅遍历持仓计算盈亏，不查询基本面/财务数据）"""
    # 新的一天，清空上一日的止盈止损记录
    today = context.current_dt.date()
    if g.stopped_date != today:
        g.stopped_today = set()
        g.stopped_date = today

    # 单次获取实时行情数据，循环中复用
    current_data = get_current_data()

    for stock in list(context.portfolio.positions.keys()):
        pos = context.portfolio.positions[stock]
        # 跳过空仓
        if pos.total_amount == 0:
            continue
        # 今日已触发止盈止损的股票不再重复处理
        if stock in g.stopped_today:
            continue

        cost = pos.avg_cost
        cd = current_data[stock]
        price = cd.last_price
        pct_change = (price - cost) / cost if cost > 0 else 0

        # 止损：亏损超过阈值，且未跌停（跌停无法卖出）
        if pct_change <= g.stop_loss_pct and price > cd.low_limit:
            order_target(stock, 0)
            g.stopped_today.add(stock)
            log.info('止损卖出 %s，成本%.2f，现价%.2f，亏损%.2f%%' %
                     (stock, cost, price, pct_change * 100))
        # 止盈：盈利超过阈值，且未跌停
        elif pct_change >= g.stop_profit_pct and price > cd.low_limit:
            order_target(stock, 0)
            g.stopped_today.add(stock)
            log.info('止盈卖出 %s，成本%.2f，现价%.2f，盈利%.2f%%' %
                     (stock, cost, price, pct_change * 100))


def rebalance(context):
    # 获取配置的持仓数量
    stocksnum = g.stocksnum
    # 获取过滤后的有效股票池（已排除ST、上市不足60天的新股、科创板）
    stock_list = get_valid_stocks(context)
    # 获取当前实时行情数据，用于判断停牌和涨跌停
    current_data = get_current_data()

    # ====== 第一步：按市值排序，先取候选池再检查行情 ======
    # 核心优化：先用get_fundamentals按市值排序取前 stocksnum*5 只候选股，
    # 然后只对这些候选股检查停牌/涨跌停，避免对全部 22,000+ 股票逐股访问current_data
    candidate_count = stocksnum * 5
    q = query(valuation.code).filter(
        valuation.code.in_(stock_list)
    ).order_by(valuation.market_cap.asc()).limit(candidate_count)

    # 执行查询，获取市值最小的候选股票列表
    df = get_fundamentals(q)
    # 如果查询结果为空，直接返回不操作
    if df is None or len(df) == 0:
        return

    # 从候选池中过滤掉停牌、涨停、当日已止盈止损的股票
    tradeable = []
    for code in df['code']:
        # 排除当日已触发止盈止损的股票，避免卖出后立即买回
        if code in g.stopped_today:
            continue
        # 单次获取该股票的实时行情数据
        cd = current_data[code]
        # 排除停牌股票
        if cd.paused:
            continue
        # 排除已涨停的股票（当前价达到涨停价，无法买入）
        if cd.last_price >= cd.high_limit:
            continue
        # 通过过滤，加入可交易股票列表
        tradeable.append(code)

    # 取市值最小的 stocksnum 只作为最终目标
    target = tradeable[:stocksnum]

    # ====== 第二步：卖出不再符合条件的持仓 ======
    # 遍历当前所有持仓
    for s in list(context.portfolio.positions.keys()):
        # 跳过已在本轮止盈止损中卖出的股票
        if s in g.stopped_today:
            continue
        # 如果持仓股票不在目标列表中，则全部卖出
        if s not in target:
            order_target(s, 0)
            # 记录卖出日志
            log.info('卖出 %s' % s)

    # ====== 第三步：等权买入目标股票 ======
    # 如果目标列表不为空，等权买入
    if len(target) > 0:
        # 计算每只股票分配的目标市值（总资产 / 目标股票数），使用total_value而非
        # available_cash，避免满仓时available_cash接近0导致错误卖出全部持仓
        target_value = context.portfolio.total_value / len(target)
        # 遍历目标股票列表，逐一调整至目标市值
        for s in target:
            # 将每只股票的持仓市值调整为目标金额，实现等权配置
            order_target_value(s, target_value)
