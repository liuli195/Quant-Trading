# Feishu Relay Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一个可上传到聚宽的 `FeishuRelayTools.py`，导入后自动捕获下单订单，合并后推送到飞书自定义机器人，并用 outbox 降低漏通知风险。

**Architecture:** 工具保持单文件上传形态，运行时只依赖 Python 标准库、`requests`、聚宽内置 `read_file/write_file` 和聚宽下单函数。核心行为拆成可本地测试的纯函数与小类：配置、订单摘要、消息拼装、outbox、飞书发送、缓冲调度、导入时包装。

**Tech Stack:** Python、pytest、unittest.mock、threading.Timer、requests、JoinQuant `read_file/write_file`。

---

## 依据

- 方案文档：[2026-05-20-feishu-relay-tools-design.md](../specs/2026-05-20-feishu-relay-tools-design.md) <!-- pathref: docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md -->
- 参考模板：[RelayTools.py](../../../scripts/archive/RelayTools.py) <!-- pathref: repo/scripts/archive/RelayTools.py -->
- 命令规则：[commands.md](../../rules/commands.md) <!-- pathref: docs/rules/commands.md -->
- 代码规则：[code-style.md](../../rules/code-style.md) <!-- pathref: docs/rules/code-style.md -->
- 密钥忽略规则：[.gitignore](../../../.gitignore) <!-- pathref: repo/.gitignore -->

## 文件结构

- Create: `scripts/joinquant_tools/FeishuRelayTools.py`
  - 聚宽可上传模板。必须是单文件、占位配置、导入即包装，不依赖本仓库包。
- Create: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`
  - 本地单元测试。通过 `importlib` 按文件路径加载模板，注入 fake `requests`、fake `Timer`、fake `read_file/write_file`、fake 聚宽模块。
- Create: `docs/guides/feishu-relay-tools.md`
  - 使用说明、私有上传版准备方式、密钥安全边界、聚宽人工冒烟步骤。
- Modify: `.gitignore`
  - 忽略本地私有上传版和本地 outbox：`FeishuRelayTools.private.py`、`FeishuRelayTools.local.py`、`scripts/joinquant_tools/FeishuRelayTools.private.py`、`scripts/joinquant_tools/FeishuRelayTools.local.py`、`feishu_relay_outbox/`。
- Modify: `docs/README.md`
  - 在指南索引中加入飞书通知工具说明链接。

不新增生成脚本。私有上传版先按文档手工复制并填入 webhook/secret，避免把密钥生成流程做复杂。

## 行为契约

- 默认 `feishu_enabled = False`，仓库模板不会误发真实请求。
- `WEBHOOK_URL`、`WEBHOOK_SECRET` 只放占位值或空字符串。
- 包装目标为 `order`、`order_value`、`order_target`、`order_target_value`、`order_target_percent`。
- 包装函数必须原样传参、原样返回；原始下单异常必须继续抛出。
- 通知异常不得抛出到策略层。
- `write_file` 写 outbox 失败时仍可尝试发送，但必须打日志提示“无持久化补偿”。
- 成功发送的唯一判定：HTTP 2xx 且响应 JSON 的 `code == 0`。
- 补发标题必须包含 `[补发]` 和 `batch_id`。
- 日志不得输出完整 webhook 或 secret。

## Task 1: 建立本地加载夹具和配置/签名单测

**Files:**
- Create: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`
- Create: `scripts/joinquant_tools/FeishuRelayTools.py`

- [ ] **Step 1: Write the failing test**

Add the initial test module with a path loader and the first three tests:

```python
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
        hmac.new(secret.encode("utf-8"), b"1700000000\nunit-test-secret", hashlib.sha256).digest()
    ).decode("utf-8")

    assert module._make_signature(1700000000, secret) == expected


def test_build_payload_includes_signature_when_secret_exists(monkeypatch):
    module = load_module(monkeypatch)

    payload = module._build_feishu_payload("hello", secret="unit-test-secret", timestamp=1700000000)

    assert payload["timestamp"] == "1700000000"
    assert payload["sign"]
    assert payload["msg_type"] == "text"
    assert payload["content"]["text"] == "hello"


def test_build_payload_omits_signature_when_secret_missing(monkeypatch):
    module = load_module(monkeypatch)

    payload = module._build_feishu_payload("hello", secret="", timestamp=1700000000)

    assert "timestamp" not in payload
    assert "sign" not in payload
    assert payload["content"]["text"] == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\joinquant_tools\tests\test_feishu_relay_tools.py -q
```

Expected: FAIL because `scripts/joinquant_tools/FeishuRelayTools.py` or `_make_signature` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `scripts/joinquant_tools/FeishuRelayTools.py` with these initial sections:

```python
# FeishuRelayTools.py
# 聚宽飞书交易通知工具模板。仓库版本只保留占位配置，不保存真实 webhook 或 secret。

import atexit
import base64
import datetime as _datetime
import hashlib
import hmac
import json
import os
import random
import sys
import threading
import time

try:
    import requests
except Exception:
    requests = None


feishu_enabled = False
WEBHOOK_URL = ""
WEBHOOK_SECRET = ""
SECURITY_KEYWORD = "交易通知"
STRATEGY_NAME = ""
BUFFER_WAIT_TIME = 60
SEND_JITTER_SECONDS = 30
MAX_BUFFER_SIZE = 30
REQUEST_TIMEOUT_SECONDS = 3
RETRY_DELAYS_SECONDS = [30, 120, 300]
OUTBOX_PATH = "feishu_relay_outbox/{strategy}.jsonl"
OUTBOX_REPLAY_LIMIT = 20
TARGET_FUNCTIONS = (
    "order",
    "order_value",
    "order_target",
    "order_target_value",
    "order_target_percent",
)

_print = print


def _log(message):
    _print("[FeishuRelayTools] %s" % message)


def _make_signature(timestamp, secret):
    string_to_sign = "%s\n%s" % (timestamp, secret)
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _build_feishu_payload(text, secret=None, timestamp=None):
    payload = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = int(time.time()) if timestamp is None else int(timestamp)
        payload["timestamp"] = str(timestamp)
        payload["sign"] = _make_signature(timestamp, secret)
    return payload
```

- [ ] **Step 4: Run test to verify it passes**

Run the same pytest command. Expected: `3 passed`.

- [ ] **Step 5: Commit**

```powershell
git add scripts\joinquant_tools\FeishuRelayTools.py scripts\joinquant_tools\tests\test_feishu_relay_tools.py
git commit -m "新增飞书通知工具基础签名测试"
```

## Task 2: 策略名和订单摘要

**Files:**
- Modify: `scripts/joinquant_tools/FeishuRelayTools.py`
- Modify: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`

- [ ] **Step 1: Write the failing test**

Append these tests:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\joinquant_tools\tests\test_feishu_relay_tools.py -q
```

Expected: FAIL because `_get_strategy_name` and `_summarize_order` are missing.

- [ ] **Step 3: Write minimal implementation**

Add these functions:

```python
def _get_strategy_name(strategy_file="/tmp/strategy/user_code.py"):
    if STRATEGY_NAME:
        return STRATEGY_NAME
    if os.path.exists(strategy_file):
        try:
            with open(strategy_file, "r", encoding="utf-8") as handle:
                first_line = handle.readline().strip()
            if first_line.startswith("#") and len(first_line) > 1:
                content = first_line[1:].strip()
                if "策略名" in content:
                    name = content.split("策略名", 1)[-1].lstrip("：:").strip()
                    if name:
                        return name
                if len(content) <= 50 and "import" not in content and "coding" not in content:
                    return content
        except Exception as exc:
            _log("读取策略名失败: %s" % exc)
    return "未命名策略"


def _safe_value(obj, attr, default=""):
    try:
        value = getattr(obj, attr)
    except Exception:
        return default
    return default if value is None else value


def _format_time(value):
    if isinstance(value, _datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, str) and value:
        return value
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _get_security_name(security, get_security_info_func=None):
    if get_security_info_func is None:
        get_security_info_func = globals().get("get_security_info")
    if get_security_info_func is None:
        return ""
    try:
        info = get_security_info_func(security)
        return getattr(info, "display_name", "") or ""
    except Exception:
        return ""


def _summarize_order(order_obj, strategy_name=None, get_security_info_func=None):
    security = str(_safe_value(order_obj, "security", ""))
    is_buy = bool(_safe_value(order_obj, "is_buy", False))
    amount = _safe_value(order_obj, "amount", "")
    price = _safe_value(order_obj, "price", "")
    order_time = _safe_value(order_obj, "add_time", None)
    return {
        "time": _format_time(order_time),
        "action": "买入" if is_buy else "卖出",
        "name": _get_security_name(security, get_security_info_func),
        "security": security,
        "amount": amount,
        "price": price,
        "strategy": strategy_name or CURRENT_STRATEGY_NAME,
    }


def _format_order_summary(summary):
    name_part = "%s(%s)" % (summary.get("name"), summary.get("security")) if summary.get("name") else summary.get("security")
    return "[%s] 【%s】%s %s %s股 价格:%s" % (
        summary.get("time", ""),
        summary.get("strategy", ""),
        summary.get("action", ""),
        name_part,
        summary.get("amount", ""),
        summary.get("price", ""),
    )
```

Add near module bottom:

```python
CURRENT_STRATEGY_NAME = _get_strategy_name()
```

- [ ] **Step 4: Run test to verify it passes**

Expected: all current tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts\joinquant_tools\FeishuRelayTools.py scripts\joinquant_tools\tests\test_feishu_relay_tools.py
git commit -m "实现飞书通知订单摘要"
```

## Task 3: 缓冲区、静默窗口、关键词和错峰

**Files:**
- Modify: `scripts/joinquant_tools/FeishuRelayTools.py`
- Modify: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`

- [ ] **Step 1: Write the failing test**

Append these tests:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL because `_OrderBuffer` and `_build_message` are missing.

- [ ] **Step 3: Write minimal implementation**

Implement:

```python
def _build_message(strategy_name, lines, security_keyword=""):
    title = "【%s】飞书交易通知" % strategy_name
    if security_keyword and security_keyword not in title:
        title = "%s %s" % (security_keyword, title)
    return title + "\n" + ("\n" + "-" * 28 + "\n").join(lines)


class _OrderBuffer:
    def __init__(self, wait_seconds, max_size, send_func, jitter_seconds=0):
        self.wait_seconds = wait_seconds
        self.max_size = max_size
        self.send_func = send_func
        self.jitter_seconds = jitter_seconds
        self._items = []
        self._timer = None
        self._lock = threading.Lock()

    @property
    def pending_count(self):
        with self._lock:
            return len(self._items)

    def add(self, order_summary):
        with self._lock:
            self._items.append(order_summary)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.wait_seconds, self.flush)
            self._timer.start()

    def flush(self):
        try:
            with self._lock:
                if self._timer:
                    self._timer.cancel()
                    self._timer = None
                if not self._items:
                    return
                items = self._items
                self._items = []
            lines = [_format_order_summary(item) for item in items[-self.max_size:]]
            if len(items) > self.max_size:
                lines.insert(0, "...(前略 %s 条)" % (len(items) - self.max_size))
            message = _build_message(CURRENT_STRATEGY_NAME, lines, SECURITY_KEYWORD)
            self._send_with_jitter(message)
        except Exception as exc:
            _log("flush 异常: %s" % exc)

    def _send_with_jitter(self, message):
        if self.jitter_seconds and self.jitter_seconds > 0:
            delay = random.randint(0, int(self.jitter_seconds))
            timer = threading.Timer(delay, self.send_func, args=(message,))
            timer.start()
            return
        self.send_func(message)
```

- [ ] **Step 4: Run test to verify it passes**

Expected: all current tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts\joinquant_tools\FeishuRelayTools.py scripts\joinquant_tools\tests\test_feishu_relay_tools.py
git commit -m "实现飞书通知静默窗口缓冲"
```

## Task 4: outbox pending/acked 和启动补发

**Files:**
- Modify: `scripts/joinquant_tools/FeishuRelayTools.py`
- Modify: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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


def test_batch_id_is_stable_for_same_message(monkeypatch):
    module = load_module(monkeypatch)

    first = module._make_batch_id("S", "2026-05-20", ["a", "b"])
    second = module._make_batch_id("S", "2026-05-20", ["a", "b"])

    assert first == second
    assert first.startswith("S-2026-05-20-2-")
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL because `_Outbox` and `_make_batch_id` are missing.

- [ ] **Step 3: Write minimal implementation**

Implement:

```python
def _json_dumps(row):
    return json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"


def _make_batch_id(strategy_name, trade_date, lines):
    raw = "%s|%s|%s|%s" % (strategy_name, trade_date, len(lines), "\n".join(lines))
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    safe_strategy = str(strategy_name).replace("/", "_").replace("\\", "_")
    return "%s-%s-%s-%s" % (safe_strategy, trade_date, len(lines), digest)


def _resolve_outbox_path(strategy_name):
    safe_strategy = str(strategy_name).replace("/", "_").replace("\\", "_")
    return OUTBOX_PATH.format(strategy=safe_strategy)


class _Outbox:
    def __init__(self, path, read_file_func=None, write_file_func=None):
        self.path = path
        self.read_file = read_file_func or globals().get("read_file")
        self.write_file = write_file_func or globals().get("write_file")

    def write_pending(self, batch_id, message, orders):
        row = {
            "status": "pending",
            "batch_id": batch_id,
            "message": message,
            "orders": orders,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        self._append(row)

    def write_acked(self, batch_id):
        self._append({"status": "acked", "batch_id": batch_id, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")})

    def _append(self, row):
        if self.write_file is None:
            raise RuntimeError("write_file unavailable")
        self.write_file(self.path, _json_dumps(row), append=True)

    def load_unacked(self, limit):
        if self.read_file is None:
            return []
        try:
            text = self.read_file(self.path) or ""
        except Exception as exc:
            _log("outbox 读取失败: %s" % exc)
            return []
        pending = {}
        acked = set()
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            batch_id = row.get("batch_id")
            if not batch_id:
                continue
            if row.get("status") == "pending":
                pending[batch_id] = row
            elif row.get("status") == "acked":
                acked.add(batch_id)
        batches = [row for batch_id, row in pending.items() if batch_id not in acked]
        return batches[-int(limit):]
```

- [ ] **Step 4: Run test to verify it passes**

Expected: all current tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts\joinquant_tools\FeishuRelayTools.py scripts\joinquant_tools\tests\test_feishu_relay_tools.py
git commit -m "实现飞书通知 outbox 补偿记录"
```

## Task 5: 飞书发送、429 重试和普通失败退避

**Files:**
- Modify: `scripts/joinquant_tools/FeishuRelayTools.py`
- Modify: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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


def test_sender_uses_rate_limit_reset_for_retry(monkeypatch):
    post = Mock(return_value=FakeResponse(status_code=429, payload={"code": 999, "msg": "rate"}, headers={"x-ogw-ratelimit-reset": "9"}))
    module = load_module(monkeypatch, request=post)
    module.feishu_enabled = True
    module.WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/fake"
    outbox = module._Outbox("path.jsonl", read_file_func=module.read_file, write_file_func=module.write_file)
    sender = module._FeishuSender(outbox=outbox)

    sender.send("message", orders=[{"security": "A"}])

    assert FakeTimer.scheduled[-1].delay == 9
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL because `_FeishuSender` is missing.

- [ ] **Step 3: Write minimal implementation**

Implement:

```python
class _FeishuSender:
    def __init__(self, outbox):
        self.outbox = outbox

    def send(self, message, replay=False, retry_index=0, batch_id=None, orders=None):
        orders = orders or []
        lines = message.splitlines()[1:]
        batch_id = batch_id or _make_batch_id(CURRENT_STRATEGY_NAME, time.strftime("%Y-%m-%d"), lines)
        if replay:
            message = "[补发] batch_id=%s\n%s" % (batch_id, message)
        persisted = True
        if not replay:
            try:
                self.outbox.write_pending(batch_id, message, orders)
            except Exception as exc:
                persisted = False
                _log("outbox 写入失败，无持久化补偿: %s" % exc)
        if not feishu_enabled:
            _log("飞书通知未启用，保留 pending: %s" % batch_id)
            return False
        if not WEBHOOK_URL:
            _log("飞书 webhook 未配置，保留 pending: %s" % batch_id)
            return False
        if requests is None:
            _log("requests 不可用，保留 pending: %s" % batch_id)
            return False
        ok, retry_delay = self._post(message)
        if ok:
            if persisted:
                try:
                    self.outbox.write_acked(batch_id)
                except Exception as exc:
                    _log("outbox ack 写入失败: %s" % exc)
            return True
        self._schedule_retry(message, replay=True, retry_index=retry_index, batch_id=batch_id, orders=orders, retry_delay=retry_delay)
        return False

    def _post(self, message):
        try:
            payload = _build_feishu_payload(message, secret=WEBHOOK_SECRET)
            response = requests.post(WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:
            _log("飞书请求异常: %s" % exc)
            return False, None
        try:
            body = response.json()
        except Exception:
            body = {}
        if 200 <= int(response.status_code) < 300 and body.get("code") == 0:
            return True, None
        reset = response.headers.get("x-ogw-ratelimit-reset")
        if int(response.status_code) == 429 and reset:
            try:
                return False, int(reset)
            except Exception:
                return False, None
        _log("飞书发送失败: http=%s code=%s msg=%s" % (response.status_code, body.get("code"), body.get("msg")))
        return False, None

    def _schedule_retry(self, message, replay, retry_index, batch_id, orders, retry_delay=None):
        delays = list(RETRY_DELAYS_SECONDS)
        if retry_delay is None:
            if retry_index >= len(delays):
                return
            retry_delay = delays[retry_index]
        timer = threading.Timer(
            retry_delay,
            self.send,
            args=(message,),
            kwargs={"replay": replay, "retry_index": retry_index + 1, "batch_id": batch_id, "orders": orders},
        )
        timer.start()
```

- [ ] **Step 4: Run test to verify it passes**

Expected: all current tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts\joinquant_tools\FeishuRelayTools.py scripts\joinquant_tools\tests\test_feishu_relay_tools.py
git commit -m "实现飞书发送和失败重试"
```

## Task 6: 导入即包装聚宽下单函数并启动补发

**Files:**
- Modify: `scripts/joinquant_tools/FeishuRelayTools.py`
- Modify: `scripts/joinquant_tools/tests/test_feishu_relay_tools.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL because `_wrap_order_function` and `_install_wrappers` are missing.

- [ ] **Step 3: Write minimal implementation**

Implement:

```python
def _wrap_order_function(func, report_func):
    def wrapper(*args, **kwargs):
        result = func(*args, **kwargs)
        if result is None:
            return result
        if isinstance(result, list):
            for item in result:
                report_func(item)
        else:
            report_func(result)
        return result
    return wrapper


def _install_wrappers(report_func):
    count = 0
    wrapped_names = set()
    for module_name in ("user_code", "kuanke.user_space_api"):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        for function_name in TARGET_FUNCTIONS:
            if function_name in wrapped_names or not hasattr(module, function_name):
                continue
            original = getattr(module, function_name)
            if getattr(original, "_feishu_relay_wrapped", False):
                continue
            wrapped = _wrap_order_function(original, report_func)
            wrapped._feishu_relay_wrapped = True
            setattr(module, function_name, wrapped)
            wrapped_names.add(function_name)
            count += 1
            _log("已包装 %s.%s" % (module_name, function_name))
    return count


def _report_order(order_obj):
    try:
        summary = _summarize_order(order_obj, CURRENT_STRATEGY_NAME)
        _buffer.add(summary)
    except Exception as exc:
        _log("订单摘要失败: %s" % exc)


def _replay_unacked(outbox, sender):
    try:
        batches = outbox.load_unacked(OUTBOX_REPLAY_LIMIT)
    except Exception as exc:
        _log("启动补发失败: %s" % exc)
        return
    for row in batches:
        sender.send(row.get("message", ""), replay=True, batch_id=row.get("batch_id"), orders=row.get("orders") or [])
```

At the module bottom, wire runtime objects:

```python
_outbox = _Outbox(_resolve_outbox_path(CURRENT_STRATEGY_NAME))
_sender = _FeishuSender(_outbox)
_buffer = _OrderBuffer(BUFFER_WAIT_TIME, MAX_BUFFER_SIZE, lambda message, replay=False, retry_index=0: _sender.send(message, replay=replay, retry_index=retry_index), SEND_JITTER_SECONDS)
atexit.register(_buffer.flush)
_wrapped_count = _install_wrappers(_report_order)
_log("初始化完成，策略“%s”已包装 %s 个下单函数。" % (CURRENT_STRATEGY_NAME, _wrapped_count))
_replay_unacked(_outbox, _sender)
```

- [ ] **Step 4: Run test to verify it passes**

Expected: all current tests pass.

- [ ] **Step 5: Commit**

```powershell
git add scripts\joinquant_tools\FeishuRelayTools.py scripts\joinquant_tools\tests\test_feishu_relay_tools.py
git commit -m "实现飞书通知下单函数包装"
```

## Task 7: 使用说明、密钥忽略和文档索引

**Files:**
- Create: `docs/guides/feishu-relay-tools.md`
- Modify: `.gitignore`
- Modify: `docs/README.md`

- [ ] **Step 1: Write the failing checks**

Before writing docs, run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: current pathrefs pass before doc changes. This is the baseline.

- [ ] **Step 2: Update `.gitignore`**

Add:

```gitignore
# ========================
# 飞书通知私有上传版与本地 outbox
# ========================
FeishuRelayTools.private.py
FeishuRelayTools.local.py
scripts/joinquant_tools/FeishuRelayTools.private.py
scripts/joinquant_tools/FeishuRelayTools.local.py
feishu_relay_outbox/
```

- [ ] **Step 3: Create the guide**

Create `docs/guides/feishu-relay-tools.md` with:

```markdown
# 飞书交易通知工具使用说明

本工具用于聚宽模拟交易通知。仓库模板只保留占位配置，真实 webhook 和 secret 只能写入聚宽私有上传版或本地未跟踪文件。

## 文件

- 模板：`scripts/joinquant_tools/FeishuRelayTools.py`
- 方案：`docs/superpowers/specs/2026-05-20-feishu-relay-tools-design.md`

## 私有上传版

1. 复制 `scripts/joinquant_tools/FeishuRelayTools.py` 为 `FeishuRelayTools.private.py`。
2. 在私有版里填入 `WEBHOOK_URL` 和 `WEBHOOK_SECRET`。
3. 按需设置 `SECURITY_KEYWORD`、`BUFFER_WAIT_TIME`、`SEND_JITTER_SECONDS`。
4. 上传私有版到聚宽研究环境或策略文件目录。
5. 在策略开头导入私有版，确保导入发生在策略下单函数被调用前。

## 聚宽人工冒烟

1. 用最小策略触发一笔 `order_target_value`。
2. 查看日志中包装数量是否大于 0。
3. 确认飞书收到一条合并消息，标题包含策略名。
4. 确认 outbox 写入了 `pending` 和 `acked`。
5. 临时填入错误 webhook，再触发一笔订单，确认只留下 `pending` 且策略不报错。
6. 恢复 webhook 后重新启动工具，确认补发消息标题包含 `[补发]` 和 `batch_id`。

## 安全边界

- 不提交真实 webhook。
- 不提交真实 secret。
- 不在日志打印完整 webhook 或 secret。
- 私有上传版文件名必须使用 `.gitignore` 已覆盖的 `FeishuRelayTools.private.py` 或 `FeishuRelayTools.local.py`。
```

- [ ] **Step 4: Update docs index**

Add one row in `docs/README.md` under guides. The implementation must use the repo's clickable-link plus `pathref` format, with pathref target `docs/guides/feishu-relay-tools.md`.

```markdown
| [feishu-relay-tools.md](guides/feishu-relay-tools.md) | 聚宽模拟交易飞书通知工具使用说明 |  |
```

- [ ] **Step 5: Run pathref check**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: `Checked ... pathref link(s).`

- [ ] **Step 6: Commit**

```powershell
git add .gitignore docs\guides\feishu-relay-tools.md docs\README.md
git commit -m "补充飞书通知工具使用说明"
```

## Task 8: 最终验证和手工验收清单

**Files:**
- No production changes unless verification exposes a defect.

- [ ] **Step 1: Run focused tests**

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\joinquant_tools\tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run syntax check**

```powershell
.\.venv\Scripts\python.exe -m py_compile scripts\joinquant_tools\FeishuRelayTools.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Run pathref check**

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: pathref check passes.

- [ ] **Step 4: Run governance gate**

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance gate
```

Expected: gate passes. If unrelated existing repo findings appear, record them in the final report and do not hide them.

- [ ] **Step 5: Security scan by text search**

Run:

```powershell
rg "open-apis/bot/v2/hook|WEBHOOK_SECRET\\s*=\\s*['\\\"][^'\\\"]{8,}|qyapi.weixin.qq.com/cgi-bin/webhook/send\\?key=" scripts docs .gitignore
```

Expected: only placeholders, docs, or the archived reference template appear. No real Feishu webhook or real secret is present.

- [ ] **Step 6: Manual JoinQuant acceptance remains open**

Record in final report:

- Local tests passed.
- Local pathref passed.
- Local governance gate result.
- JoinQuant cloud thread/network/atexit behavior is not locally proven.
- Required manual smoke follows `docs/guides/feishu-relay-tools.md`.

## Plan Self-Review

- Spec coverage: covers template, signing, keyword, jitter, rate-limit retry, outbox pending/acked/replay, import-time wrapping, tests, docs, security boundary, and manual JoinQuant smoke.
- Intentional non-scope: no Redis, no local service, no polling process, no `after_trading_end`, no strategy trading logic change, no generator script.
- TDD order: every behavior task starts with failing tests, then minimal implementation, then test pass.
- Known residual risk: local tests cannot prove JoinQuant module load order, network access, `threading.Timer`, or `atexit` behavior. These remain manual cloud acceptance items.

## 聚宽冒烟验收记录（2026-05-24）

- Run tag: `20260524-204724`
- 聚宽临时策略：自动创建空白策略，`algorithmId=1408ed244439c861b18797baafaa6e46`。
- 工具加载方式：用户已将 `.local/jq-feishu-smoke/FeishuRelayTools.success.py` 上传到聚宽研究环境根目录；冒烟策略通过 `read_file("FeishuRelayTools.success.py")` 动态加载为 `FeishuRelayTools` 模块。
- 本地前置检查：`.venv` 提权运行 `pytest scripts\joinquant_tools\tests -q` 通过，结果 `47 passed`；`.venv` 提权运行 `py_compile` 检查公共模板和私有上传版通过。
- Success run: `feishu-smoke-success-20260524-204724`，backtest_id `62447fc5326f8522a21e0c797864d27b`，URL `https://www.joinquant.com/algorithm/backtest/detail?backtestId=62447fc5326f8522a21e0c797864d27b`。日志证据：包装下单函数 `4` 个，`FEISHU_SMOKE_ORDER_RESULT OK security=510300.XSHG`，`events_pending=2 events_acked=2 unacked=0`，平台日志 `ERROR=0`；成交 1 笔，510300.XSHG 买入 2400 股。
- Failure run: `feishu-smoke-failure-20260524-204724`，backtest_id `01939835093ee6cadcb495fcc70cb065`，URL `https://www.joinquant.com/algorithm/backtest/detail?backtestId=01939835093ee6cadcb495fcc70cb065`。日志证据：策略完成且 `ERROR=0`，订单仍正常成交；无效 hook 返回 `http=200 code=19001`；回测结束后按 outbox 最新状态统计为 `events_pending=5 events_acked=4 unacked=1`。
- Replay run: `feishu-smoke-replay-20260524-204724`，backtest_id `df6c9c9da9d8736e05879a83ed0cc523`，URL `https://www.joinquant.com/algorithm/backtest/detail?backtestId=df6c9c9da9d8736e05879a83ed0cc523`。日志证据：`transactioninfo` 无成交，日志仅输出 `FEISHU_SMOKE_REPLAY_NO_ORDER`；outbox 回到 `events_pending=5 events_acked=5 unacked=0`。
- 飞书接收时间：自动化侧无法读取飞书群 UI；已通过 Feishu HTTP ack 与 outbox ack 证明聚宽云端发送链路跑通，群内接收时间待人工补录。
- 提取说明：本次使用 `result_source=detail`，产物完整保留平台日志和成交明细；`integrity.json` 标记 `incomplete` 是因为未生成 research bundle 和策略侧 `audit_log.jsonl`，不影响本次飞书通知冒烟结论。
- 安全记录：验收记录未保存 webhook、secret、完整签名或完整机器人 URL。

## 聚宽双策略冒烟验收记录（2026-05-24）

- Run tag: `20260524-dual-3`
- 前置：已在聚宽研究环境根目录将用户上传的 `FeishuRelayTools.success.py` 复制为 `FeishuRelayTools.py`；双策略测试源码使用普通 `import FeishuRelayTools`，不再通过 `read_file` 或路径 loader 加载工具文件。
- Alpha run: `feishu-smoke-dual-alpha-20260524-dual-3`，策略名 `FeishuDualA-20260524-dual-3`，backtest_id `29141130a775c2e5eb972098b20f7a45`，URL `https://www.joinquant.com/algorithm/backtest/detail?backtestId=29141130a775c2e5eb972098b20f7a45`。日志证据：包装下单函数 `4` 个，`FEISHU_DUAL_ORDER_RESULT OK mode=alpha security=510300.XSHG target=10000`，回测内 outbox 快照 `events_pending=2 events_acked=2 unacked=0`，最终远端 outbox 文件 `FeishuDualA-20260524-dual-3.jsonl` 为 `pending=3 acked=3 unacked=0`。
- Beta run: `feishu-smoke-dual-beta-20260524-dual-3`，策略名 `FeishuDualB-20260524-dual-3`，backtest_id `d0ba4e699588513eff2f324de672e993`，URL `https://www.joinquant.com/algorithm/backtest/detail?backtestId=d0ba4e699588513eff2f324de672e993`。日志证据：包装下单函数 `4` 个，`FEISHU_DUAL_ORDER_RESULT OK mode=beta security=510300.XSHG target=16000`，回测内 outbox 快照 `events_pending=2 events_acked=2 unacked=0`，最终远端 outbox 文件 `FeishuDualB-20260524-dual-3.jsonl` 为 `pending=3 acked=3 unacked=0`。
- 隔离结论：两个策略使用不同 `STRATEGY_NAME` 和不同 outbox 文件，最终均 ack 且 `unacked=0`，未观察到 outbox 串写或策略名串用。
- 并发提交说明：尝试过两个自动化并发路径：两个复制 Chrome profile 同时运行 `jq_automation run`、同一个已登录上下文双页面顺序编译后同时启动；两者均在聚宽编译等待阶段返回空白 `CompileFailed`，未形成可用回测结果。因此本条记录证明“双策略名独立发送与持久化隔离”通过，但“严格同时提交两个聚宽正式回测”尚未由自动化证明。
- 安全记录：验收记录未保存 webhook、secret、完整签名或完整机器人 URL。
