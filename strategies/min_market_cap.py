# 市值最小策略（小市值效应）
# 每天买入市值最小的前 stocksnum 只股票，卖出不再符合条件的持仓

def initialize(context):
    # 设置要持有的股票数量
    g.stocksnum = 10
    # 止损阈值：当持仓亏损超过8%时卖出
    g.stop_loss_pct = -0.08
    # 止盈阈值：当持仓盈利超过30%时卖出
    g.stop_profit_pct = 0.15
    # 设置基准为沪深300
    set_benchmark('000300.XSHG')
    # 使用真实价格（不复权）交易
    set_option('use_real_price', True)
    # 每个交易日开盘时执行一次调仓
    run_daily(rebalance, 'open')
    # 输出初始化完成日志
    log.info('市值最小策略初始化完成，持仓%d只，止损%.0f%%，止盈%.0f%%' %
             (g.stocksnum, abs(g.stop_loss_pct) * 100, g.stop_profit_pct * 100))


def get_valid_stocks(context):
    """获取有效股票池：排除ST、上市不足60天的新股"""
    # 获取当前回测日期
    current_dt = context.current_dt
    # 获取当前日期所有A股股票列表
    all_stocks = get_all_securities(['stock'], current_dt)

    # 用于存放有效股票代码的列表
    valid = []
    # 遍历所有股票，过滤不合规的股票
    for code in all_stocks.index:
        # 获取该股票的信息（含名称、上市日期等）
        info = all_stocks.loc[code]
        # 排除名称中含'ST'的股票（ST、*ST等）
        if 'ST' in info['display_name']:
            continue
        # 排除上市不足60天的新股（避免新股波动过大）
        if (current_dt - info['start_date']).days < 60:
            continue
        # 排除科创板股票（688开头，市价单需保护限价，order_target_value无法处理）
        if code.startswith('688'):
            continue
        # 通过过滤，加入有效股票列表
        valid.append(code)
    # 返回有效股票代码列表
    return valid


def rebalance(context):
    # 获取配置的持仓数量
    stocksnum = g.stocksnum
    # 获取过滤后的有效股票池（已排除ST和上市不足60天的新股）
    stock_list = get_valid_stocks(context)
    # 获取当前实时行情数据，用于判断停牌和涨跌停
    current_data = get_current_data()

    # ====== 第一步：检查止盈止损条件，卖出触发条件的持仓 ======
    # 记录已触发止盈止损的股票，当日不再买入
    stopped = set()
    # 遍历当前所有持仓
    for stock in list(context.portfolio.positions.keys()):
        # 获取该股票的头寸信息
        pos = context.portfolio.positions[stock]
        # 跳过空仓（total_amount为0表示已无持仓）
        if pos.total_amount == 0:
            continue
        # 获取持仓均价（聚宽自动计算，已考虑买卖手续费）
        cost = pos.avg_cost
        # 获取当日实时价格
        price = current_data[stock].last_price
        # 计算持仓盈亏比例
        pct_change = (price - cost) / cost if cost > 0 else 0

        # 止损判断：亏损超过阈值，且未跌停（跌停无法卖出）
        if pct_change <= g.stop_loss_pct and price > current_data[stock].low_limit:
            order_target(stock, 0)
            stopped.add(stock)
            log.info('止损卖出 %s，成本%.2f，现价%.2f，亏损%.2f%%' %
                     (stock, cost, price, pct_change * 100))
        # 止盈判断：盈利超过阈值，且未跌停
        elif pct_change >= g.stop_profit_pct and price > current_data[stock].low_limit:
            order_target(stock, 0)
            stopped.add(stock)
            log.info('止盈卖出 %s，成本%.2f，现价%.2f，盈利%.2f%%' %
                     (stock, cost, price, pct_change * 100))

    # ====== 第二步：构建可交易股票列表 ======
    tradeable = []
    for code in stock_list:
        # 排除停牌股票（paused 为 True 表示停牌）
        if current_data[code].paused:
            continue
        # 排除已涨停的股票（当前价达到涨停价，无法买入）
        if current_data[code].last_price >= current_data[code].high_limit:
            continue
        # 排除当日已触发止盈止损的股票，避免卖出后立即买回
        if code in stopped:
            continue
        # 通过过滤，加入可交易股票列表
        tradeable.append(code)

    # ====== 第三步：按市值排序选出目标股票 ======
    # 构建基本面查询：按市值升序排列，取市值最小的 stocksnum 只
    q = query(valuation.code).filter(
        valuation.code.in_(tradeable)
    ).order_by(valuation.market_cap.asc()).limit(stocksnum)

    # 执行查询，获取市值最小的股票列表
    df = get_fundamentals(q)
    # 如果查询结果为空，直接返回不操作
    if df is None or len(df) == 0:
        return
    # 提取目标股票代码列表
    target = list(df['code'])

    # ====== 第四步：卖出不再符合条件的持仓 ======
    # 遍历当前所有持仓
    for s in list(context.portfolio.positions.keys()):
        # 跳过已在本轮止盈止损中卖出的股票
        if s in stopped:
            continue
        # 如果持仓股票不在目标列表中，则全部卖出
        if s not in target:
            order_target(s, 0)
            # 记录卖出日志
            log.info('卖出 %s' % s)

    # ====== 第五步：等权买入目标股票 ======
    # 如果目标列表不为空，等权买入
    if len(target) > 0:
        # 计算每只股票分配的买入金额（可用资金 / 目标股票数）
        cash_each = context.portfolio.available_cash / len(target)
        # 遍历目标股票列表，逐一买入
        for s in target:
            # 将每只股票的持仓市值调整为目标金额
            order_target_value(s, cash_each)
