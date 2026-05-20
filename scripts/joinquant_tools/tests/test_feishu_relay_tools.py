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
