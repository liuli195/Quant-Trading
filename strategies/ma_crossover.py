# 双均线交叉策略
3# 当短期均线上穿长期均线时买入，下穿时卖出

def initialize(context):
    g.stock_pool = ['000300.XSHG']  # 沪深300ETF
    g.short_period = 5   # 短期均线周期
    g.long_period = 20   # 长期均线周期
    set_benchmark('000300.XSHG')
    set_option('use_real_price', True)
    log.info('策略初始化完成')

def handle_data(context, data):
    stock = g.stock_pool[0]

    # 获取历史收盘价
    prices = attribute_history(stock, g.long_period + 1, '1d', ['close'])
    if len(prices) < g.long_period:
        return

    # 计算均线
    short_ma = prices['close'][-g.short_period:].mean()
    long_ma = prices['close'][-g.long_period:].mean()

    # 获取当前持仓
    position = context.portfolio.positions[stock]

    # 金叉买入
    if short_ma > long_ma and position.total_amount == 0:
        order_target_value(stock, context.portfolio.available_cash * 0.95)
        log.info(f'金叉买入 {stock}，短均={short_ma:.2f}，长均={long_ma:.2f}')

    # 死叉卖出
    elif short_ma < long_ma and position.total_amount > 0:
        order_target(stock, 0)
        log.info(f'死叉卖出 {stock}，短均={short_ma:.2f}，长均={long_ma:.2f}')
