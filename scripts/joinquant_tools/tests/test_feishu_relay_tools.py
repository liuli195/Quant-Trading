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


def load_module(monkeypatch, name="feishu_relay_under_test", read_text="", request=None):
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

    spec = importlib.util.spec_from_file_location(name, MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    module.read_file = fake_read_file
    module.write_file = fake_write_file
    spec.loader.exec_module(module)
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


def test_strategy_name_reads_first_line(monkeypatch, tmp_path):
    strategy_file = tmp_path / "user_code.py"
    strategy_file.write_text("# 策略名：ETF轮动模拟盘\n", encoding="utf-8")
    module = load_module(monkeypatch)

    assert module._get_strategy_name(str(strategy_file)) == "ETF轮动模拟盘"


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


def test_buffer_merges_orders_and_clears_after_flush(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    sender = lambda message, replay=False, retry_index=0: sent.append((message, replay, retry_index))
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=sender, jitter_seconds=0)

    buffer.add({"time": "2026-05-20 09:31:00", "action": "买入", "name": "", "security": "513100.XSHG", "amount": 100, "price": 1.0, "strategy": "S"})
    buffer.add({"time": "2026-05-20 09:31:01", "action": "卖出", "name": "", "security": "518880.XSHG", "amount": 50, "price": 5.0, "strategy": "S"})
    buffer.flush()

    assert len(sent) == 1
    assert "513100.XSHG" in sent[0][0]
    assert "518880.XSHG" in sent[0][0]
    assert buffer.pending_count == 0


def test_buffer_limits_message_size_with_prefix(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    buffer = module._OrderBuffer(wait_seconds=60, max_size=1, send_func=lambda message, replay=False, retry_index=0: sent.append(message), jitter_seconds=0)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    buffer.add({"time": "t2", "action": "买入", "name": "", "security": "B", "amount": 1, "price": 1, "strategy": "S"})
    buffer.flush()

    assert "前略 1 条" in sent[0]
    assert "A" not in sent[0]
    assert "B" in sent[0]


def test_security_keyword_is_in_every_message(monkeypatch):
    module = load_module(monkeypatch)

    text = module._build_message("S", ["line1"], security_keyword="交易通知")

    assert "交易通知" in text
    assert "S" in text


def test_jitter_schedules_deferred_send(monkeypatch):
    module = load_module(monkeypatch)
    monkeypatch.setattr(module.random, "randint", lambda start, end: 7)
    sent = []
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=lambda message, replay=False, retry_index=0: sent.append(message), jitter_seconds=30)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    buffer.flush()

    assert FakeTimer.scheduled[-1].delay == 7
    assert sent == []
    FakeTimer.scheduled[-1].fire()
    assert len(sent) == 1
