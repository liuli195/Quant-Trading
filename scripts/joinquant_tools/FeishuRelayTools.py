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
    digest = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def _build_feishu_payload(text, secret=None, timestamp=None):
    payload = {"msg_type": "text", "content": {"text": text}}
    if secret:
        timestamp = int(time.time()) if timestamp is None else int(timestamp)
        payload["timestamp"] = str(timestamp)
        payload["sign"] = _make_signature(timestamp, secret)
    return payload


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
    if summary.get("name"):
        name_part = "%s(%s)" % (summary.get("name"), summary.get("security"))
    else:
        name_part = summary.get("security")
    return "[%s] 【%s】%s %s %s股 价格:%s" % (
        summary.get("time", ""),
        summary.get("strategy", ""),
        summary.get("action", ""),
        name_part,
        summary.get("amount", ""),
        summary.get("price", ""),
    )


def _build_message(strategy_name, lines, security_keyword=""):
    title = "【%s】飞书交易通知" % strategy_name
    if security_keyword and security_keyword not in title:
        title = "%s %s" % (security_keyword, title)
    return title + "\n" + ("\n" + "-" * 28 + "\n").join(lines)


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
            limit = int(limit)
        except Exception as exc:
            _log("outbox replay limit 无效: %s" % exc)
            return []
        if limit <= 0:
            return []
        try:
            text = self.read_file(self.path) or ""
        except Exception as exc:
            _log("outbox 读取失败: %s" % exc)
            return []
        latest_by_batch = {}
        for line in text.splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            batch_id = row.get("batch_id")
            if not batch_id:
                continue
            if row.get("status") in ("pending", "acked"):
                latest_by_batch[batch_id] = row
        batches = [row for row in latest_by_batch.values() if row.get("status") == "pending"]
        return batches[-limit:]


class _OrderBuffer:
    def __init__(self, wait_seconds, max_size, send_func, jitter_seconds=0):
        self.wait_seconds = wait_seconds
        self.max_size = max_size
        self.send_func = send_func
        self.jitter_seconds = jitter_seconds
        self._items = []
        self._timer = None
        self._timer_token = 0
        self._lock = threading.Lock()

    @property
    def pending_count(self):
        with self._lock:
            return len(self._items)

    def add(self, order_summary):
        with self._lock:
            self._items.append(order_summary)
            self._timer_token += 1
            token = self._timer_token
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.wait_seconds, self._flush_if_current, args=(token,))
            self._timer.start()

    def _flush_if_current(self, token):
        try:
            self._flush_items(self._drain_items(token=token))
        except Exception as exc:
            _log("flush 异常: %s" % exc)

    def flush(self):
        try:
            self._flush_items(self._drain_items())
        except Exception as exc:
            _log("flush 异常: %s" % exc)

    def _drain_items(self, token=None):
        with self._lock:
            if token is not None and token != self._timer_token:
                return None
            if self._timer:
                self._timer.cancel()
                self._timer = None
            if not self._items:
                return None
            items = self._items
            self._items = []
            return items

    def _flush_items(self, items):
        if not items:
            return
        lines = [_format_order_summary(item) for item in items[-self.max_size:]]
        if len(items) > self.max_size:
            lines.insert(0, "...(前略 %s 条)" % (len(items) - self.max_size))
        message = _build_message(CURRENT_STRATEGY_NAME, lines, SECURITY_KEYWORD)
        self._send_with_jitter(message)

    def _send_with_jitter(self, message):
        if self.jitter_seconds and self.jitter_seconds > 0:
            delay = random.randint(0, int(self.jitter_seconds))
            timer = threading.Timer(delay, self._safe_send, args=(message,))
            timer.start()
            return
        self._safe_send(message)

    def _safe_send(self, message):
        try:
            self.send_func(message)
        except Exception as exc:
            _log("发送通知异常: %s" % exc)


CURRENT_STRATEGY_NAME = _get_strategy_name()
