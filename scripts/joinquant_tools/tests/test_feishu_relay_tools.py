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

    text = module._build_message("S", ["line1"], security_keyword="安全校验")

    assert "安全校验" in text
    assert "S" in text


def test_stale_timer_token_is_ignored(monkeypatch):
    module = load_module(monkeypatch)
    sent = []
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=lambda message, replay=False, retry_index=0: sent.append(message), jitter_seconds=0)

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
    buffer = module._OrderBuffer(wait_seconds=60, max_size=30, send_func=lambda message, replay=False, retry_index=0: None, jitter_seconds=0)

    buffer.add({"time": "t1", "action": "买入", "name": "", "security": "A", "amount": 1, "price": 1, "strategy": "S"})
    old_token = buffer._timer_token
    buffer.add({"time": "t2", "action": "买入", "name": "", "security": "B", "amount": 1, "price": 1, "strategy": "S"})

    assert buffer._drain_items(token=old_token) is None
    assert buffer.pending_count == 2


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


def test_send_exception_is_logged(monkeypatch):
    module = load_module(monkeypatch)
    logs = []
    monkeypatch.setattr(module, "_print", lambda message: logs.append(message))

    def failing_send(message):
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

    def failing_send(message):
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


def test_sender_uses_rate_limit_reset_for_retry(monkeypatch):
    post = Mock(return_value=FakeResponse(status_code=429, payload={"code": 999, "msg": "rate"}, headers={"x-ogw-ratelimit-reset": "9"}))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    assert FakeTimer.scheduled[-1].delay == 9
