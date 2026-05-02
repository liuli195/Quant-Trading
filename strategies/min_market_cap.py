# -*- coding: utf-8 -*-
# 市值最小策略（小市值效应）
# 每天买入市值最小的前 stocksnum 只股票，卖出不再符合条件的持仓
enable_profile()
import datetime as dt
import pandas as pd

def initialize(context):
    # 设置要持有的股票数量
    g.stocksnum = 10
    # 调仓间隔（交易日）：每多少天执行一次调仓，默认每7个交易日调仓一次
    g.rebalance_interval = 7
    # 记录上一次调仓日期，用于跳过未到间隔的交易日的调仓
    g.last_rebalance_date = None
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


def get_prefiltered_stocks(context):
    """获取预过滤股票池（仅排除科创板、上市不足60天新股，不做ST检查；缓存30天）
    性能优化：ST检查移至rebalance中市值排序之后，只对候选池（~200只）执行，
    避免对全市场~5000只股票逐一查ST（get_extras原是最大性能瓶颈占81.5%耗时）"""
    current_dt = context.current_dt
    # 缓存30天：证券列表（新股上市、代码变更）变化缓慢，30天刷新一次足够
    cache_date = getattr(g, '_prefiltered_cache_date', None)
    if cache_date is not None and (current_dt.date() - cache_date).days < 30:
        return g._prefiltered_cache

    # 一次性获取全A股DataFrame（含display_name、start_date等列）
    all_stocks = get_all_securities(['stock'], date=current_dt)

    # pandas向量化筛选：排除科创板（688开头）
    not_kcb = ~all_stocks.index.str.startswith('688')

    # pandas向量化筛选：排除上市不足60天的新股
    cutoff_date = current_dt.date() - dt.timedelta(days=60)
    start_dates = pd.to_datetime(all_stocks['start_date'])
    old_enough = start_dates <= pd.to_datetime(cutoff_date)

    # 应用快速筛选（科创板、上市时间），返回set便于O(1)成员检查
    pre_filtered = all_stocks[not_kcb & old_enough]
    codes = set(pre_filtered.index.tolist())

    # 缓存结果，30天内复用
    g._prefiltered_cache_date = current_dt.date()
    g._prefiltered_cache = codes
    return codes


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
    # ====== 调仓间隔控制：未到间隔时跳过本次调仓 ======
    today = context.current_dt.date()
    if g.last_rebalance_date is not None:
        days_since = (today - g.last_rebalance_date).days
        # 间隔不足时跳过调仓（止盈止损由 check_stop_loss 每分钟独立处理，不受影响）
        if days_since < g.rebalance_interval:
            return
    # 记录本次调仓日期
    g.last_rebalance_date = today

    stocksnum = g.stocksnum
    current_dt = context.current_dt
    current_data = get_current_data()
    # 获取预过滤股票池（科创板、新股；无ST检查；缓存30天）— 返回set
    pre_filtered = get_prefiltered_stocks(context)

    # ====== 第一步：全市场按市值排序取候选池，再做昂贵过滤 ======
    # 性能优化：不再对全量股票做.in_()过滤和ST检查，而是先取市值最小的top N，
    # 然后在Python中交叉过滤（pre_filtered、ST），将get_extras从~5000只降到~200只
    candidate_count = stocksnum * 20
    q = query(valuation.code).order_by(
        valuation.market_cap.asc()
    ).limit(candidate_count)

    df = get_fundamentals(q)
    if df is None or len(df) == 0:
        return

    # 在Python中过滤：只保留预过滤池中的股票（科创板、新股已排除）
    codes = [c for c in df['code'] if c in pre_filtered]

    # ====== 第二步：对候选池查ST（性能关键：只查~200只，原为~5000只）======
    if len(codes) > 0:
        df_st = get_extras('is_st', codes,
                           start_date=current_dt.date(),
                           end_date=current_dt.date())
        st_series = df_st.iloc[0]
        is_st_map = st_series.fillna(False).astype(bool)
    else:
        is_st_map = pd.Series(dtype=bool)

    # ====== 第三步：过滤ST、停牌、涨停、当日已止盈止损 ======
    tradeable = []
    for code in codes:
        if code in g.stopped_today:
            continue
        # 排除ST股票（关键：此处而非全市场过滤，大幅减少get_extras开销）
        if is_st_map.get(code, False):
            continue
        cd = current_data[code]
        # 排除停牌股票
        if cd.paused:
            continue
        # 排除已涨停的股票（当前价达到涨停价，无法买入）
        if cd.last_price >= cd.high_limit:
            continue
        tradeable.append(code)

    # 取市值最小的 stocksnum 只作为最终目标
    target = tradeable[:stocksnum]

    # ====== 第四步：卖出不再符合条件的持仓 ======
    for s in list(context.portfolio.positions.keys()):
        if s in g.stopped_today:
            continue
        if s not in target:
            order_target(s, 0)
            log.info('卖出 %s' % s)

    # ====== 第五步：等权买入目标股票 ======
    if len(target) > 0:
        # 计算每只股票分配的目标市值（总资产 / 目标股票数），使用total_value而非
        # available_cash，避免满仓时available_cash接近0导致错误卖出全部持仓
        target_value = context.portfolio.total_value / len(target)
        for s in target:
            order_target_value(s, target_value)
