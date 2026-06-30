import base64
import hashlib
import hmac
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts" / "joinquant_tools" / "FeishuRelayTools.py"


class FakeTimer:
    scheduled = []

    def __init__(self, delay, callback, args=None, kwargs=None):
        self.delay = delay
        self.callback = callback
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.cancelled = False
        FakeTimer.scheduled.append(self)

    def start(self):
        return None

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.callback(*self.args, **self.kwargs)


def load_module(
    monkeypatch,
    name="feishu_relay_under_test",
    read_text="",
    request=None,
    preinject_file_api=True,
    kuanke_file_api=None,
):
    FakeTimer.scheduled = []
    request = request or Mock()
    fake_requests = types.SimpleNamespace(post=request)
    monkeypatch.setitem(sys.modules, "requests", fake_requests)
    monkeypatch.setattr("threading.Timer", FakeTimer)
    monkeypatch.setattr("atexit.register", lambda func: func)

    writes = []

    def fake_read_file(path):
        return read_text

    def fake_write_file(path, content, append=False):
        writes.append((path, content, append))

    if kuanke_file_api is not None:
        monkeypatch.setitem(sys.modules, "kuanke", types.SimpleNamespace())
        monkeypatch.setitem(sys.modules, "kuanke.user_space_api", kuanke_file_api)

    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    if preinject_file_api is True:
        module.read_file = fake_read_file
        module.write_file = fake_write_file
    elif preinject_file_api == "non_callable":
        module.read_file = "not callable"
        module.write_file = "not callable"
    spec.loader.exec_module(module)
    module.WEBHOOK_SECRET = "unit-test-secret"
    module._test_writes = writes
    return module


def test_sign_feishu_payload_uses_timestamp_newline_secret(monkeypatch):
    module = load_module(monkeypatch)
    secret = "unit-test-secret"
    expected = base64.b64encode(
        hmac.new(b"1700000000\nunit-test-secret", digestmod=hashlib.sha256).digest()
    ).decode("utf-8")

    assert module._make_signature(1700000000, secret) == expected


def test_build_payload_includes_signature_when_secret_exists(monkeypatch):
    module = load_module(monkeypatch)

    payload = module._build_feishu_payload("hello", secret="unit-test-secret", timestamp=1700000000)

    assert payload["timestamp"] == "1700000000"
    assert payload["sign"] == module._make_signature(1700000000, "unit-test-secret")
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "hello"


def test_build_payload_omits_signature_when_secret_missing(monkeypatch):
    module = load_module(monkeypatch)

    payload = module._build_feishu_payload("hello", secret="", timestamp=1700000000)

    assert "timestamp" not in payload
    assert "sign" not in payload
    assert payload["content"]["text"] == "hello"


class FakeOrder:
    security = "513100.XSHG"
    is_buy = True
    amount = 200
    price = 1.234
    add_time = None


class FakeSellOrder:
    security = "518880.XSHG"
    is_buy = False
    amount = 1600
    price = 9.21
    value = 232424.23
    add_time = "2026-03-24 09:30:00"


def test_strategy_name_reads_first_line(monkeypatch, tmp_path):
    strategy_file = tmp_path / "user_code.py"
    strategy_file.write_text("# 策略名：ETF轮动模拟盘\n", encoding="utf-8")
    module = load_module(monkeypatch)

    assert module._get_strategy_name(str(strategy_file)) == "ETF轮动模拟盘"


def test_strategy_name_reads_user_code_global_before_file(monkeypatch, tmp_path):
    strategy_file = tmp_path / "user_code.py"
    strategy_file.write_text("# 策略名：COMMENT_NAME\n", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "user_code", types.SimpleNamespace(STRATEGY_NAME="CODE_NAME"))
    module = load_module(monkeypatch)

    assert module._get_strategy_name(str(strategy_file)) == "CODE_NAME"


def test_strategy_name_falls_back_when_file_missing(monkeypatch):
    module = load_module(monkeypatch)

    assert module._get_strategy_name("missing.py") == "未命名策略"


def test_order_summary_degrades_when_display_name_missing(monkeypatch):
    module = load_module(monkeypatch)
    order = FakeOrder()
    summary = module._summarize_order(order, strategy_name="ETF轮动模拟盘", get_security_info_func=None)

    assert summary["security"] == "513100.XSHG"
    assert summary["action"] == "买入"
    assert summary["amount"] == 200
    assert summary["price"] == 1.234
    assert summary["strategy"] == "ETF轮动模拟盘"
    assert "ETF轮动模拟盘" in module._format_order_summary(summary)
    assert "513100.XSHG" in module._format_order_summary(summary)


def test_order_summary_reads_security_name_from_kuanke_api_module(monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.setitem(
        sys.modules,
        "kuanke.user_space_api",
        types.SimpleNamespace(
            get_security_info=lambda security: types.SimpleNamespace(display_name="黄金易方达ETF")
        ),
    )

    summary = module._summarize_order(FakeSellOrder(), strategy_name="ETF动态调仓")

    assert summary["name"] == "黄金易方达ETF"
    assert "黄金易方达ETF-518880.XSHG" in module._format_order_summary(summary)


def test_order_summary_formats_trade_value_target_weight_and_sell_sign(monkeypatch):
    module = load_module(monkeypatch)
    order = FakeSellOrder()
    summary = module._summarize_order(
        order,
        strategy_name="ETF多因子轮动",
        get_security_info_func=lambda security: types.SimpleNamespace(display_name="黄金易方达ETF"),
        call_context={"target_weight": 0.2476},
    )

    assert module._format_order_summary(summary) == (
        "[2026-03-24 09:30:00] 【ETF多因子轮动】【卖出】 "
        "“黄金易方达ETF-518880.XSHG” 数量：-1600股，价格：9.21，总金额：-232424.23，目标仓位：24.76%"
    )


def test_wrapped_order_target_value_infers_target_weight_from_caller_context(monkeypatch):
    module = load_module(monkeypatch)
    reported = []
    user_code = types.SimpleNamespace(order_target_value=Mock(return_value=FakeSellOrder()))
    monkeypatch.setitem(sys.modules, "user_code", user_code)

    def report(order, call_context=None):
        reported.append(module._summarize_order(order, strategy_name="S", call_context=call_context))

    module._install_wrappers(report)

    def place_order(context):
        return user_code.order_target_value("518880.XSHG", 247600)

    context = types.SimpleNamespace(portfolio=types.SimpleNamespace(total_value=1000000))
    place_order(context)

    assert reported[0]["target_weight"] == 0.2476


def test_report_signal_plan_sends_signal_notice_with_existing_sender(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    monkeypatch.setattr(
        module._sender,
        "send",
        lambda message, batch_id=None, orders=None: sent.append((message, batch_id, orders)) or True,
    )

    result = module.report_signal_plan({
        "batch_id": "signal-batch-1",
        "signal_date": "2026-05-15",
        "trade_date": "next_open",
        "pool": ["513100.XSHG", "518880.XSHG"],
        "target_weights": [0.2476, 0.0],
        "target_values": [247600.0, 0.0],
        "params": {"ExecutionTimingMode": "weekend-close-signal-next-open"},
    })

    assert result is True
    message, batch_id, orders = sent[0]
    assert batch_id == "signal-batch-1"
    assert "信号日期：2026-05-15" in message
    assert "计划交易日：next_open" in message
    assert "513100.XSHG" in message
    assert orders[0]["action"] == "信号"
    assert orders[0]["target_weight"] == 0.2476
    assert orders[0]["trade_value"] == 247600.0


def test_report_signal_plan_treats_outbox_pending_as_notice_accepted(monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.setattr(module._sender, "send", lambda message, batch_id=None, orders=None: False)

    result = module.report_signal_plan({
        "batch_id": "signal-batch-1",
        "signal_date": "2026-05-15",
        "pool": ["513100.XSHG"],
        "target_weights": [0.2476],
    })

    assert result is True


def test_suppressed_execution_notice_skips_order_buffer(monkeypatch):
    module = load_module(monkeypatch)
    buffered = []
    monkeypatch.setattr(module._buffer, "add", lambda summary: buffered.append(summary))

    module.suppress_execution_notice(batch_id="signal-batch-1", reason="signal_notice_already_sent")
    module._report_order(FakeOrder())
    module.resume_execution_notice()
    module._report_order(FakeOrder())

    assert len(buffered) == 1
    assert buffered[0]["security"] == "513100.XSHG"


def test_wrapped_order_captures_run_type_from_caller_context(monkeypatch):
    module = load_module(monkeypatch)
    reported = []
    original = Mock(return_value=FakeOrder())

    def report(order, call_context=None):
        reported.append(call_context)

    wrapped = module._wrap_order_function(original, function_name="order", report_func=report)

    def place_order(context):
        return wrapped("513100.XSHG", 100)

    context = types.SimpleNamespace(run_params=types.SimpleNamespace(type="sim_trade"))
    place_order(context)

    assert reported[0]["run_type"] == "sim_trade"


def test_buffer_merges_orders_and_clears_after_flush(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    sender = lambda message, replay=False, retry_index=0, orders=None: sent.append((message, replay, retry_index, orders))
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=sender, jitter_seconds=0)

    buffer.add({"time": "2026-05-20 09:31:00", "action": "买入", "name": "", "security": "513100.XSHG", "amount": 100, "price": 1.0, "strategy": "S"})
    buffer.add({"time": "2026-05-20 09:31:01", "action": "卖出", "name": "", "security": "518880.XSHG", "amount": 50, "price": 5.0, "strategy": "S"})
    buffer.flush()

    assert len(sent) == 1
    assert "513100.XSHG" in sent[0][0]
    assert "518880.XSHG" in sent[0][0]
    assert sent[0][3] == [
        {
            "time": "2026-05-20 09:31:00",
            "action": "买入",
            "name": "",
            "security": "513100.XSHG",
            "amount": 100,
            "price": 1.0,
            "strategy": "S",
        },
        {
            "time": "2026-05-20 09:31:01",
            "action": "卖出",
            "name": "",
            "security": "518880.XSHG",
            "amount": 50,
            "price": 5.0,
            "strategy": "S",
        },
    ]
    assert buffer.pending_count == 0


def test_buffer_limits_message_size_with_prefix(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    buffer = module._OrderBuffer(wait_seconds=60, max_size=1, send_func=lambda message, replay=False, retry_index=0, orders=None: sent.append(message), jitter_seconds=0)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    buffer.add({"time": "t2", "action": "买入", "name": "", "security": "B", "amount": 1, "price": 1, "strategy": "S"})
    buffer.flush()

    assert "前略 1 条" in sent[0]
    assert "A" not in sent[0]
    assert "B" in sent[0]


def test_security_keyword_is_in_every_message(monkeypatch):
    module = load_module(monkeypatch)

    text = module._build_message("S", ["line1"], security_keyword="安全校验")

    assert "安全校验" in text
    assert "S" in text


def test_buffer_prefixes_known_run_environment(monkeypatch):
    module = load_module(monkeypatch)
    cases = [
        ("full_backtest", "[回测]"),
        ("sim_trade", "[模拟交易]"),
        ("simple_backtest", "[编译运行]"),
    ]

    for run_type, expected_prefix in cases:
        sent = []
        buffer = module._OrderBuffer(
            wait_seconds=60,
            max_size=30,
            send_func=lambda message, replay=False, retry_index=0, orders=None: sent.append(message),
            jitter_seconds=0,
        )

        buffer.add({
            "time": "t1",
            "action": "买入",
            "name": "",
            "security": "A",
            "amount": 1,
            "price": 1,
            "strategy": "S",
            "run_type": run_type,
        })
        buffer.flush()

        assert sent[0].startswith(expected_prefix)


def test_stale_timer_token_is_ignored(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=lambda message, replay=False, retry_index=0, orders=None: sent.append(message), jitter_seconds=0)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    first_timer = FakeTimer.scheduled[-1]
    buffer.add({"time": "t2", "action": "买入", "name": "", "security": "B", "amount": 1, "price": 1, "strategy": "S"})
    second_timer = FakeTimer.scheduled[-1]

    first_timer.callback(*first_timer.args, **first_timer.kwargs)
    assert sent == []
    assert buffer.pending_count == 2

    second_timer.fire()
    assert len(sent) == 1
    assert "A" in sent[0]
    assert "B" in sent[0]
    assert buffer.pending_count == 0


def test_expired_token_does_not_drain_items(monkeypatch):
    module = load_module(monkeypatch)
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=lambda message, replay=False, retry_index=0, orders=None: None, jitter_seconds=0)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    old_token = buffer._timer_token
    buffer.add({"time": "t2", "action": "买入", "name": "", "security": "B", "amount": 1, "price": 1, "strategy": "S"})

    assert buffer._drain_items(token=old_token) is None
    assert buffer.pending_count == 2


def test_jitter_schedules_deferred_send(monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.setattr(module.random, "randint", lambda start, end: 7)
    sent = []
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=lambda message, replay=False, retry_index=0, orders=None: sent.append(message), jitter_seconds=30)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    buffer.flush()

    assert FakeTimer.scheduled[-1].delay == 7
    assert sent == []
    FakeTimer.scheduled[-1].fire()
    assert len(sent) == 1


def test_send_exception_is_logged(monkeypatch):
    module = load_module(monkeypatch)
    logs = []
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))

    def failing_send(message, orders=None):
        raise RuntimeError("boom")

    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=failing_send, jitter_seconds=0)
    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    buffer.flush()

    assert any("发送通知异常" in item and "boom" in item for item in logs)


def test_outbox_writes_pending_then_acked(monkeypatch):
    module = load_module(monkeypatch)
    outbox = module._Outbox("feishu_relay_outbox/S.jsonl", read_file_func=lambda path: "", write_file_func=module.write_file)

    outbox.write_pending("batch-1", "message", [{"security": "A"}])
    outbox.write_acked("batch-1")

    rows = [json.loads(content) for _, content, append in module._test_writes]
    assert rows[0]["status"] == "pending"
    assert rows[0]["batch_id"] == "batch-1"
    assert rows[1]["status"] == "acked"
    assert rows[1]["batch_id"] == "batch-1"
    assert all(call[2] is True for call in module._test_writes)


def test_outbox_resolves_file_api_from_kuanke_when_module_globals_missing(monkeypatch):
    writes = []

    def kuanke_read_file(path):
        return ""

    def kuanke_write_file(path, content, append=False):
        writes.append((path, content, append))

    kuanke_api = types.SimpleNamespace(read_file=kuanke_read_file, write_file=kuanke_write_file)
    module = load_module(monkeypatch, preinject_file_api=False, kuanke_file_api=kuanke_api)

    module._outbox.write_pending("batch-1", "message", [{"security": "A"}])

    assert len(writes) == 1
    path, content, append = writes[0]
    assert path == "feishu_relay_outbox/%s.jsonl" % module.CURRENT_STRATEGY_NAME
    assert append is True
    row = json.loads(content)
    assert row["status"] == "pending"
    assert row["batch_id"] == "batch-1"


def test_outbox_ignores_non_callable_module_file_api_and_uses_kuanke(monkeypatch):
    writes = []
    kuanke_api = types.SimpleNamespace(
        read_file=lambda path: "",
        write_file=lambda path, content, append=False: writes.append((path, content, append)),
    )
    module = load_module(monkeypatch, preinject_file_api="non_callable", kuanke_file_api=kuanke_api)

    module._outbox.write_pending("batch-1", "message", [])

    assert len(writes) == 1
    assert json.loads(writes[0][1])["status"] == "pending"


def test_outbox_loads_unacked_batches(monkeypatch):
    pending = json.dumps({"status": "pending", "batch_id": "batch-1", "message": "m1"}, ensure_ascii=False)
    acked = json.dumps({"status": "acked", "batch_id": "batch-2"}, ensure_ascii=False)
    read_text = "\n".join([
        pending,
        json.dumps({"status": "pending", "batch_id": "batch-2", "message": "m2"}, ensure_ascii=False),
        acked,
    ])
    module = load_module(monkeypatch, read_text=read_text)
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)

    batches = outbox.load_unacked(limit=20)

    assert [item["batch_id"] for item in batches] == ["batch-1"]
    assert batches[0]["message"] == "m1"


def test_outbox_later_pending_overrides_earlier_acked(monkeypatch):
    read_text = "\n".join([
        json.dumps({"status": "pending", "batch_id": "batch-1", "message": "old"}, ensure_ascii=False),
        json.dumps({"status": "acked", "batch_id": "batch-1"}, ensure_ascii=False),
        json.dumps({"status": "pending", "batch_id": "batch-1", "message": "new"}, ensure_ascii=False),
    ])
    module = load_module(monkeypatch, read_text=read_text)
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)

    batches = outbox.load_unacked(limit=20)

    assert [item["batch_id"] for item in batches] == ["batch-1"]
    assert batches[0]["message"] == "new"


def test_outbox_limit_uses_latest_event_order(monkeypatch):
    read_text = "\n".join([
        json.dumps({"status": "pending", "batch_id": "batch-1", "message": "old"}, ensure_ascii=False),
        json.dumps({"status": "pending", "batch_id": "batch-2", "message": "middle"}, ensure_ascii=False),
        json.dumps({"status": "pending", "batch_id": "batch-1", "message": "new"}, ensure_ascii=False),
    ])
    module = load_module(monkeypatch, read_text=read_text)
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)

    batches = outbox.load_unacked(limit=1)

    assert [item["batch_id"] for item in batches] == ["batch-1"]
    assert batches[0]["message"] == "new"


def test_outbox_invalid_limits_return_empty(monkeypatch):
    read_text = json.dumps({"status": "pending", "batch_id": "batch-1", "message": "m1"}, ensure_ascii=False)
    module = load_module(monkeypatch, read_text=read_text)
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)

    assert outbox.load_unacked(limit=0) == []
    assert outbox.load_unacked(limit=-1) == []
    assert outbox.load_unacked(limit="bad") == []


def test_outbox_skips_non_object_and_bad_json_lines(monkeypatch):
    read_text = "\n".join([
        "not-json",
        json.dumps([], ensure_ascii=False),
        json.dumps("x", ensure_ascii=False),
        json.dumps({"status": "pending", "batch_id": "batch-1", "message": "m1"}, ensure_ascii=False),
    ])
    module = load_module(monkeypatch, read_text=read_text)
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)

    batches = outbox.load_unacked(limit=20)

    assert [item["batch_id"] for item in batches] == ["batch-1"]


def test_resolve_outbox_path_sanitizes_strategy_name(monkeypatch):
    module = load_module(monkeypatch)

    assert module._resolve_outbox_path("A/B\\C") == "feishu_relay_outbox/A_B_C.jsonl"


def test_batch_id_is_stable_for_same_message(monkeypatch):
    module = load_module(monkeypatch)

    first = module._make_batch_id("S", "2026-05-20", ["a", "b"])
    second = module._make_batch_id("S", "2026-05-20", ["a", "b"])

    assert first == second
    assert first.startswith("S-2026-05-20-2-")


def test_jitter_send_exception_is_logged(monkeypatch):
    module = load_module(monkeypatch)
    logs = []
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))
    monkeypatch.setattr(module.random, "randint", lambda start, end: 1)

    def failing_send(message, orders=None):
        raise RuntimeError("later boom")

    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=failing_send, jitter_seconds=30)
    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    buffer.flush()
    FakeTimer.scheduled[-1].fire()

    assert any("发送通知异常" in item and "later boom" in item for item in logs)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"code": 0, "msg": "ok"}
        self.headers = headers or {}

    def json(self):
        return self._payload


def test_sender_marks_acked_after_success(monkeypatch):
    post = Mock(return_value=FakeResponse())
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    assert post.call_count == 1
    statuses = [json.loads(content)["status"] for _, content, _ in module._test_writes]
    assert statuses == ["pending", "acked"]


def test_sender_keeps_pending_when_request_fails(monkeypatch):
    post = Mock(side_effect=RuntimeError("network down"))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.RETRY_DELAYS_SECONDS = []
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    statuses = [json.loads(content)["status"] for _, content, _ in module._test_writes]
    assert statuses == ["pending"]


def test_sender_keeps_pending_when_secret_missing(monkeypatch):
    post = Mock(return_value=FakeResponse())
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.WEBHOOK_SECRET = ""
    module.RETRY_DELAYS_SECONDS = []
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    assert post.call_count == 0
    statuses = [json.loads(content)["status"] for _, content, _ in module._test_writes]
    assert statuses == ["pending"]
    assert FakeTimer.scheduled == []


def test_sender_masks_webhook_url_in_request_exception_log(monkeypatch):
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/sensitive-token"
    post = Mock(side_effect=RuntimeError("failed POST %s" % webhook_url))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = webhook_url
    module.RETRY_DELAYS_SECONDS = []
    logs = []
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    joined_logs = "\n".join(logs)
    assert webhook_url not in joined_logs
    assert "sensitive-token" not in joined_logs
    assert "<webhook>" in joined_logs


def test_sender_masks_webhook_and_secret_in_response_failure_log(monkeypatch):
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/sensitive-token"
    secret = "unit-test-secret"
    payload = {
        "code": 1,
        "msg": "bad https://open.feishu.cn/open-apis/bot/v2/hook/sensitive-token unit-test-secret",
    }
    post = Mock(return_value=FakeResponse(status_code=400, payload=payload))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = webhook_url
    module.WEBHOOK_SECRET = secret
    module.RETRY_DELAYS_SECONDS = []
    logs = []
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    joined_logs = "\n".join(logs)
    assert webhook_url not in joined_logs
    assert "sensitive-token" not in joined_logs
    assert secret not in joined_logs
    assert "<webhook>" in joined_logs
    assert "<secret>" in joined_logs


def test_sender_replay_retry_does_not_stack_replay_prefix(monkeypatch):
    post = Mock(return_value=FakeResponse(status_code=500, payload={"code": 1, "msg": "fail"}))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.RETRY_DELAYS_SECONDS = [5, 8]
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("title\nbody", orders=[{"security": "A"}])
    FakeTimer.scheduled[-1].fire()
    FakeTimer.scheduled[-1].fire()

    second_retry_text = post.call_args_list[2].kwargs["json"]["content"]["text"]
    assert second_retry_text.count("[补发]") == 1


def test_sender_uses_retry_delay_sequence_until_exhausted(monkeypatch):
    post = Mock(return_value=FakeResponse(status_code=500, payload={"code": 1, "msg": "fail"}))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.RETRY_DELAYS_SECONDS = [5, 8]
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])
    assert FakeTimer.scheduled[-1].delay == 5
    assert len(FakeTimer.scheduled) == 1

    FakeTimer.scheduled[-1].fire()
    assert FakeTimer.scheduled[-1].delay == 8
    assert len(FakeTimer.scheduled) == 2

    FakeTimer.scheduled[-1].fire()
    assert len(FakeTimer.scheduled) == 2


def test_sender_sends_without_ack_when_outbox_pending_write_fails(monkeypatch):
    post = Mock(return_value=FakeResponse())
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"

    def failing_write_file(path, content, append=False):
        raise RuntimeError("disk full")

    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=failing_write_file)
    sender = module._FeishuSender(outbox=outbox)

    assert sender.send("message", orders=[{"security": "A"}]) is True
    assert post.call_count == 1
    assert module._test_writes == []


def test_sender_retry_success_does_not_ack_when_pending_write_failed(monkeypatch):
    post = Mock(side_effect=[
        FakeResponse(status_code=500, payload={"code": 1, "msg": "fail"}),
        FakeResponse(),
    ])
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.RETRY_DELAYS_SECONDS = [5]

    class FailingPendingOutbox:
        ack_count = 0

        def write_pending(self, batch_id, message, orders):
            raise RuntimeError("disk full")

        def write_acked(self, batch_id):
            self.ack_count += 1

    outbox = FailingPendingOutbox()
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])
    FakeTimer.scheduled[-1].fire()

    assert post.call_count == 2
    assert outbox.ack_count == 0


def test_sender_handles_non_dict_json_failure_body(monkeypatch):
    post = Mock(return_value=FakeResponse(status_code=500, payload=["not", "dict"]))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.RETRY_DELAYS_SECONDS = []
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    statuses = [json.loads(content)["status"] for _, content, _ in module._test_writes]
    assert statuses == ["pending"]
    assert FakeTimer.scheduled == []


def test_sender_uses_rate_limit_reset_for_retry(monkeypatch):
    post = Mock(return_value=FakeResponse(status_code=429, payload={"code": 999, "msg": "rate"}, headers={"x-ogw-ratelimit-reset": "9"}))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    assert FakeTimer.scheduled[-1].delay == 9


def test_sender_rate_limit_retry_stops_after_retry_delays_exhausted(monkeypatch):
    post = Mock(return_value=FakeResponse(
        status_code=429,
        payload={"code": 999, "msg": "rate"},
        headers={"x-ogw-ratelimit-reset": "9"},
    ))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    module.RETRY_DELAYS_SECONDS = [5, 8]
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])
    assert FakeTimer.scheduled[-1].delay == 9
    assert len(FakeTimer.scheduled) == 1

    FakeTimer.scheduled[-1].fire()
    assert FakeTimer.scheduled[-1].delay == 9
    assert len(FakeTimer.scheduled) == 2

    FakeTimer.scheduled[-1].fire()
    assert len(FakeTimer.scheduled) == 2


def test_wrap_function_returns_original_order_and_buffers_summary(monkeypatch):
    module = load_module(monkeypatch)
    captured = []
    original = Mock(return_value=FakeOrder())
    wrapped = module._wrap_order_function(original, lambda order: captured.append(order))

    result = wrapped("arg", key="value")

    assert result is original.return_value
    original.assert_called_once_with("arg", key="value")
    assert captured == [original.return_value]


def test_wrap_function_handles_order_list(monkeypatch):
    module = load_module(monkeypatch)
    captured = []
    orders = [FakeOrder(), FakeOrder()]
    wrapped = module._wrap_order_function(Mock(return_value=orders), lambda order: captured.append(order))

    assert wrapped() == orders
    assert captured == orders


def test_wrap_function_defaults_to_module_report_order(monkeypatch):
    module = load_module(monkeypatch)
    captured = []
    original = Mock(return_value=FakeOrder())
    monkeypatch.setattr(module, "_report_order", lambda order: captured.append(order))

    wrapped = module._wrap_order_function(original)

    assert wrapped() is original.return_value
    assert captured == [original.return_value]


def test_wrap_function_returns_existing_wrapped_function(monkeypatch):
    module = load_module(monkeypatch)
    captured = []
    original = Mock(return_value=FakeOrder())
    first = module._wrap_order_function(original, lambda order: captured.append(order))

    second = module._wrap_order_function(first, lambda order: captured.append(order))

    assert second is first
    assert getattr(first, "_feishu_wrapped", False) is True
    assert second() is original.return_value
    assert captured == [original.return_value]


def test_install_wrappers_scans_user_code_and_kuanke_modules(monkeypatch):
    module = load_module(monkeypatch)
    user_code = types.SimpleNamespace(order=Mock(return_value=FakeOrder()))
    kuanke = types.SimpleNamespace(order_value=Mock(return_value=FakeOrder()))
    monkeypatch.setitem(sys.modules, "user_code", user_code)
    monkeypatch.setitem(sys.modules, "kuanke.user_space_api", kuanke)
    captured = []

    count = module._install_wrappers(lambda order: captured.append(order))

    assert count == 2
    user_code.order()
    kuanke.order_value()
    assert len(captured) == 2


def test_install_wrappers_skips_feishu_wrapped_functions(monkeypatch):
    module = load_module(monkeypatch)
    original = Mock(return_value=FakeOrder())
    original._feishu_wrapped = True
    user_code = types.SimpleNamespace(order=original)
    monkeypatch.setitem(sys.modules, "user_code", user_code)

    count = module._install_wrappers(lambda order: None)

    assert count == 0
    assert user_code.order is original


def test_install_wrappers_skips_legacy_feishu_relay_wrapped_functions(monkeypatch):
    module = load_module(monkeypatch)
    original = Mock(return_value=FakeOrder())
    original._feishu_relay_wrapped = True
    user_code = types.SimpleNamespace(order=original)
    monkeypatch.setitem(sys.modules, "user_code", user_code)

    count = module._install_wrappers(lambda order: None)

    assert count == 0
    assert user_code.order is original


def test_install_wrappers_wrapped_user_code_claims_same_name(monkeypatch):
    module = load_module(monkeypatch)
    user_order = Mock(return_value=FakeOrder())
    user_order._feishu_wrapped = True
    kuanke_order = Mock(return_value=FakeOrder())
    user_code = types.SimpleNamespace(order=user_order)
    kuanke = types.SimpleNamespace(order=kuanke_order)
    monkeypatch.setitem(sys.modules, "user_code", user_code)
    monkeypatch.setitem(sys.modules, "kuanke.user_space_api", kuanke)

    count = module._install_wrappers(lambda order: None)

    assert count == 0
    assert user_code.order is user_order
    assert kuanke.order is kuanke_order


def test_install_wrappers_legacy_wrapped_user_code_claims_same_name(monkeypatch):
    module = load_module(monkeypatch)
    user_order = Mock(return_value=FakeOrder())
    user_order._feishu_relay_wrapped = True
    kuanke_order = Mock(return_value=FakeOrder())
    user_code = types.SimpleNamespace(order=user_order)
    kuanke = types.SimpleNamespace(order=kuanke_order)
    monkeypatch.setitem(sys.modules, "user_code", user_code)
    monkeypatch.setitem(sys.modules, "kuanke.user_space_api", kuanke)

    count = module._install_wrappers(lambda order: None)

    assert count == 0
    assert user_code.order is user_order
    assert kuanke.order is kuanke_order


def test_install_wrappers_skips_non_callable_targets(monkeypatch):
    module = load_module(monkeypatch)
    user_code = types.SimpleNamespace(order="not callable")
    monkeypatch.setitem(sys.modules, "user_code", user_code)

    count = module._install_wrappers(lambda order: None)

    assert count == 0
    assert user_code.order == "not callable"


def test_replay_unacked_skips_malformed_message_and_continues(monkeypatch):
    module = load_module(monkeypatch)
    logs = []
    sent = []
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))

    outbox = types.SimpleNamespace(load_unacked=lambda limit: [
        {"batch_id": "bad", "message": {"not": "text"}, "orders": [{"security": "A"}]},
        {"batch_id": "good", "message": "normal message", "orders": [{"security": "B"}]},
    ])
    sender = types.SimpleNamespace(
        send=lambda message, replay=False, batch_id=None, orders=None: sent.append((message, replay, batch_id, orders))
    )

    module._replay_unacked(outbox, sender)

    assert sent == [("normal message", True, "good", [{"security": "B"}])]
    assert any("补发记录异常" in item for item in logs)


def test_replay_unacked_sender_exception_does_not_stop_following_rows(monkeypatch):
    module = load_module(monkeypatch)
    logs = []
    sent = []
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/sensitive-token"
    module.WEBHOOK_URL = webhook_url
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))

    outbox = types.SimpleNamespace(load_unacked=lambda limit: [
        {"batch_id": "bad", "message": "bad message", "orders": []},
        {"batch_id": "good", "message": "good message", "orders": []},
    ])

    class Sender:
        def send(self, message, replay=False, batch_id=None, orders=None):
            if batch_id == "bad":
                raise RuntimeError("failed %s" % webhook_url)
            sent.append((message, replay, batch_id, orders))

    module._replay_unacked(outbox, Sender())

    assert sent == [("good message", True, "good", [])]
    joined_logs = "\n".join(logs)
    assert "补发记录异常" in joined_logs
    assert webhook_url not in joined_logs
    assert "sensitive-token" not in joined_logs
    assert "<webhook>" in joined_logs
