# Strategy name: FeishuRelaySmoke
enable_profile()
STRATEGY_NAME = "FeishuRelaySmoke"
import FeishuRelayTools


def initialize(context):
    set_benchmark("510300.XSHG")
    set_option("use_real_price", True)
    g.feishu_smoke_ordered = False
    run_daily(smoke_order, time="09:35", reference_security="510300.XSHG")
    run_daily(smoke_snapshot, time="14:55", reference_security="510300.XSHG")


def smoke_order(context):
    if getattr(g, "feishu_smoke_ordered", False):
        return
    g.feishu_smoke_ordered = True
    order_target_value("510300.XSHG", 10000)
    log.info("FEISHU_SMOKE_ORDER_SUBMITTED security=510300.XSHG")


def smoke_snapshot(context):
    wrapped_count = getattr(FeishuRelayTools, "_wrapped_count", "NA")
    log.info("FEISHU_SMOKE_WRAPPED_COUNT %s" % wrapped_count)
