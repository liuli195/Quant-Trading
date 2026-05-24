# FeishuRelayTools.py
# 聚宽飞书交易通知工具模板。仓库版本只保留占位配置，不保存真实 webhook 或 secret。

import atexit
import base64
import datetime as _datetime
import hashlib
import hmac
import importlib
import json
import os
import random
import re
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
RUN_TYPE_LABELS = {
    "full_backtest": "回测",
    "sim_trade": "模拟交易",
    "simple_backtest": "编译运行",
}

_print = print


def _log(message):
    _print("[FeishuRelayTools] %s" % message)


def _safe_error_text(exc):
    text = str(exc)
    if WEBHOOK_URL:
        text = text.replace(WEBHOOK_URL, "<webhook>")
    if WEBHOOK_SECRET:
        text = text.replace(WEBHOOK_SECRET, "<secret>")
    text = re.sub(r"(open-apis/bot/v2/hook/)\S+", r"\1<webhook>", text)
    return text


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


def _resolve_file_api(name):
    candidate = globals().get(name)
    if callable(candidate):
        return candidate
    module = sys.modules.get("kuanke.user_space_api")
    if module is None:
        try:
            module = importlib.import_module("kuanke.user_space_api")
        except Exception:
            return None
    candidate = getattr(module, name, None)
    if callable(candidate):
        return candidate
    return None


def _get_strategy_name(strategy_file="/tmp/strategy/user_code.py"):
    if STRATEGY_NAME:
        return STRATEGY_NAME
    user_code = sys.modules.get("user_code")
    if user_code is not None:
        try:
            strategy_name = getattr(user_code, "STRATEGY_NAME", "")
        except Exception:
            strategy_name = ""
        if strategy_name:
            return str(strategy_name)
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
            _log("读取策略名失败: %s" % _safe_error_text(exc))
    return "未命名策略"


def _safe_value(obj, attr, default=""):
    try:
        value = getattr(obj, attr)
    except Exception:
        return default
    return default if value is None else value


def _context_run_type(context):
    if context is None:
        return ""
    if isinstance(context, dict):
        run_params = context.get("run_params")
    else:
        run_params = getattr(context, "run_params", None)
    if isinstance(run_params, dict):
        run_type = run_params.get("type")
    else:
        run_type = getattr(run_params, "type", "")
    return str(run_type) if run_type else ""


def _frame_run_type(frame):
    if frame is None:
        return ""
    locals_dict = getattr(frame, "f_locals", {})
    for name in ("context", "ctx"):
        run_type = _context_run_type(locals_dict.get(name))
        if run_type:
            return run_type
    return ""


def _run_type_label(run_type):
    return RUN_TYPE_LABELS.get(str(run_type), "") if run_type else ""


def _prefix_message_with_run_type(message, run_type):
    label = _run_type_label(run_type)
    if not label:
        return message
    prefix = "[%s]" % label
    if message.startswith(prefix):
        return message
    return "%s %s" % (prefix, message)


def _resolve_items_run_type(items):
    for item in items or []:
        run_type = item.get("run_type") if isinstance(item, dict) else ""
        if _run_type_label(run_type):
            return run_type
    return ""


def _format_time(value):
    if isinstance(value, _datetime.datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, str) and value:
        return value
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _get_security_name(security, get_security_info_func=None):
    if get_security_info_func is None:
        get_security_info_func = _resolve_get_security_info_func()
    if get_security_info_func is None:
        return ""
    try:
        info = get_security_info_func(security)
        if isinstance(info, dict):
            return info.get("display_name") or info.get("name") or ""
        return getattr(info, "display_name", "") or ""
    except Exception:
        return ""


def _resolve_get_security_info_func():
    direct_func = globals().get("get_security_info")
    if callable(direct_func):
        return direct_func
    for module_name in ("kuanke.user_space_api", "user_code", "__main__"):
        module = sys.modules.get(module_name)
        if module is None:
            continue
        try:
            func = getattr(module, "get_security_info", None)
        except Exception:
            continue
        if callable(func):
            return func
    return None


def _to_float(value):
    if value == "" or value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _format_decimal(value, digits=2):
    numeric = _to_float(value)
    if numeric is None:
        return str(value) if value is not None else "--"
    text = ("%%.%sf" % int(digits)) % numeric
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _signed_number(value, is_buy):
    numeric = _to_float(value)
    if numeric is None:
        return value
    sign = 1 if is_buy else -1
    return abs(numeric) * sign


def _format_percent(value):
    numeric = _to_float(value)
    if numeric is None:
        return "--"
    return "%s%%" % _format_decimal(numeric * 100, 2)


def _calculate_trade_value(order_obj, amount, price, call_context):
    value = _safe_value(order_obj, "value", None)
    if value in ("", None) and call_context:
        value = call_context.get("trade_value")
    if value not in ("", None):
        return value
    amount_float = _to_float(amount)
    price_float = _to_float(price)
    if amount_float is None or price_float is None:
        return None
    return amount_float * price_float


def _summarize_order(order_obj, strategy_name=None, get_security_info_func=None, call_context=None):
    security = str(_safe_value(order_obj, "security", ""))
    is_buy = bool(_safe_value(order_obj, "is_buy", False))
    amount = _safe_value(order_obj, "amount", "")
    price = _safe_value(order_obj, "price", "")
    order_time = _safe_value(order_obj, "add_time", None)
    call_context = call_context or {}
    return {
        "time": _format_time(order_time),
        "action": "买入" if is_buy else "卖出",
        "name": _get_security_name(security, get_security_info_func),
        "security": security,
        "amount": amount,
        "price": price,
        "signed_amount": _signed_number(amount, is_buy),
        "trade_value": _signed_number(_calculate_trade_value(order_obj, amount, price, call_context), is_buy),
        "target_weight": call_context.get("target_weight"),
        "run_type": call_context.get("run_type"),
        "strategy": strategy_name or CURRENT_STRATEGY_NAME,
    }


def _format_order_summary(summary):
    if summary.get("name"):
        name_part = "%s-%s" % (summary.get("name"), summary.get("security"))
    else:
        name_part = summary.get("security")
    return "[%s] 【%s】【%s】 “%s” 数量：%s股，价格：%s，总金额：%s，目标仓位：%s" % (
        summary.get("time", ""),
        summary.get("strategy", ""),
        summary.get("action", ""),
        name_part,
        _format_decimal(summary.get("signed_amount", summary.get("amount", "")), 0),
        _format_decimal(summary.get("price", ""), 4),
        _format_decimal(summary.get("trade_value"), 2),
        _format_percent(summary.get("target_weight")),
    )


def _build_message(strategy_name, lines, security_keyword="", run_type=None):
    title = "【%s】飞书交易通知" % strategy_name
    if security_keyword and security_keyword not in title:
        title = "%s %s" % (security_keyword, title)
    message = title + "\n" + ("\n" + "-" * 28 + "\n").join(lines)
    return _prefix_message_with_run_type(message, run_type)


class _Outbox:
    def __init__(self, path, read_file_func=None, write_file_func=None):
        self.path = path
        self.read_file = read_file_func if read_file_func is not None else _resolve_file_api("read_file")
        self.write_file = write_file_func if write_file_func is not None else _resolve_file_api("write_file")

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
            _log("outbox replay limit 无效: %s" % _safe_error_text(exc))
            return []
        if limit <= 0:
            return []
        try:
            text = self.read_file(self.path) or ""
        except Exception as exc:
            _log("outbox 读取失败: %s" % _safe_error_text(exc))
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
                latest_by_batch.pop(batch_id, None)
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
            _log("flush 异常: %s" % _safe_error_text(exc))

    def flush(self):
        try:
            self._flush_items(self._drain_items())
        except Exception as exc:
            _log("flush 异常: %s" % _safe_error_text(exc))

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
        run_type = _resolve_items_run_type(items)
        message = _build_message(CURRENT_STRATEGY_NAME, lines, SECURITY_KEYWORD, run_type=run_type)
        self._send_with_jitter(message, items)

    def _send_with_jitter(self, message, orders):
        if self.jitter_seconds and self.jitter_seconds > 0:
            delay = random.randint(0, int(self.jitter_seconds))
            timer = threading.Timer(delay, self._safe_send, args=(message, orders))
            timer.start()
            return
        self._safe_send(message, orders)

    def _safe_send(self, message, orders):
        try:
            self.send_func(message, orders=orders)
        except Exception as exc:
            _log("发送通知异常: %s" % _safe_error_text(exc))


class _FeishuSender:
    def __init__(self, outbox):
        self.outbox = outbox

    def send(self, message, replay=False, retry_index=0, batch_id=None, orders=None, pending_persisted=True):
        raw_message = message
        orders = orders or []
        lines = raw_message.splitlines()[1:]
        batch_id = batch_id or _make_batch_id(CURRENT_STRATEGY_NAME, time.strftime("%Y-%m-%d"), lines)
        post_message = "[补发] batch_id=%s\n%s" % (batch_id, raw_message) if replay else raw_message
        persisted = pending_persisted
        if not replay:
            try:
                self.outbox.write_pending(batch_id, raw_message, orders)
                persisted = True
            except Exception as exc:
                persisted = False
                _log("outbox 写入失败，无持久化补偿: %s" % _safe_error_text(exc))
        if not feishu_enabled:
            _log("飞书通知未启用，保留 pending: %s" % batch_id)
            return False
        if not WEBHOOK_URL:
            _log("飞书 webhook 未配置，保留 pending: %s" % batch_id)
            return False
        if not WEBHOOK_SECRET:
            _log("飞书 webhook secret 未配置，保留 pending: %s" % batch_id)
            return False
        if requests is None:
            _log("requests 不可用，保留 pending: %s" % batch_id)
            return False
        ok, retry_delay = self._post(post_message)
        if ok:
            if persisted:
                try:
                    self.outbox.write_acked(batch_id)
                except Exception as exc:
                    _log("outbox ack 写入失败: %s" % _safe_error_text(exc))
            return True
        self._schedule_retry(
            raw_message,
            replay=True,
            retry_index=retry_index,
            batch_id=batch_id,
            orders=orders,
            retry_delay=retry_delay,
            pending_persisted=persisted,
        )
        return False

    def _post(self, message):
        try:
            payload = _build_feishu_payload(message, secret=WEBHOOK_SECRET)
            response = requests.post(WEBHOOK_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
        except Exception as exc:
            _log("飞书请求异常: %s" % _safe_error_text(exc))
            return False, None
        try:
            body = response.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        try:
            status_code = int(response.status_code)
        except Exception:
            status_code = 0
        if 200 <= status_code < 300 and body.get("code") == 0:
            return True, None
        reset = response.headers.get("x-ogw-ratelimit-reset")
        if status_code == 429 and reset:
            try:
                return False, int(reset)
            except Exception:
                return False, None
        _log("飞书发送失败: http=%s code=%s msg=%s" % (
            response.status_code,
            body.get("code"),
            _safe_error_text(body.get("msg")),
        ))
        return False, None

    def _schedule_retry(self, message, replay, retry_index, batch_id, orders, retry_delay=None, pending_persisted=True):
        delays = list(RETRY_DELAYS_SECONDS)
        if retry_index >= len(delays):
            return
        if retry_delay is None:
            retry_delay = delays[retry_index]
        timer = threading.Timer(
            retry_delay,
            self.send,
            args=(message,),
            kwargs={
                "replay": replay,
                "retry_index": retry_index + 1,
                "batch_id": batch_id,
                "orders": orders,
                "pending_persisted": pending_persisted,
            },
        )
        timer.start()


def _get_arg(args, kwargs, index, names):
    if len(args) > index:
        return args[index]
    for name in names:
        if name in kwargs:
            return kwargs[name]
    return None


def _frame_portfolio_total_value(frame):
    if frame is None:
        return None
    locals_dict = getattr(frame, "f_locals", {})
    for name in ("account_value", "total_value"):
        total = _to_float(locals_dict.get(name))
        if total is not None:
            return total
    for name in ("context", "ctx"):
        context = locals_dict.get(name)
        portfolio = getattr(context, "portfolio", None)
        total = _to_float(getattr(portfolio, "total_value", None))
        if total is not None:
            return total
    portfolio = locals_dict.get("portfolio")
    total = _to_float(getattr(portfolio, "total_value", None))
    if total is not None:
        return total
    return None


def _build_call_context(function_name, args, kwargs, caller_frame=None):
    context = {"function": function_name}
    run_type = _frame_run_type(caller_frame)
    if run_type:
        context["run_type"] = run_type
    if function_name == "order_value":
        context["trade_value"] = _get_arg(args, kwargs, 1, ("value", "cash_amount"))
    elif function_name == "order_target_value":
        target_value = _get_arg(args, kwargs, 1, ("value", "target_value"))
        context["target_value"] = target_value
        total_value = _frame_portfolio_total_value(caller_frame)
        target_value_float = _to_float(target_value)
        if target_value_float is not None and total_value and total_value != 0:
            context["target_weight"] = target_value_float / total_value
    elif function_name == "order_target_percent":
        context["target_weight"] = _get_arg(args, kwargs, 1, ("percent", "target_percent"))
    return context


def _report_with_context(reporter, order_obj, call_context):
    try:
        reporter(order_obj, call_context=call_context)
    except TypeError as exc:
        text = str(exc)
        if "call_context" not in text and "unexpected keyword" not in text:
            raise
        reporter(order_obj)


def _wrap_order_function(func, function_name=None, report_func=None):
    if report_func is None and callable(function_name):
        report_func = function_name
        function_name = None
    if getattr(func, "_feishu_wrapped", False) is True:
        return func
    if getattr(func, "_feishu_relay_wrapped", False) is True:
        return func

    def wrapper(*args, **kwargs):
        try:
            caller_frame = sys._getframe(1)
        except Exception:
            caller_frame = None
        call_context = _build_call_context(function_name, args, kwargs, caller_frame)
        result = func(*args, **kwargs)
        if result is None:
            return result
        reporter = report_func or _report_order
        if isinstance(result, list):
            for item in result:
                _report_with_context(reporter, item, call_context)
        else:
            _report_with_context(reporter, result, call_context)
        return result
    wrapper._feishu_wrapped = True
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
            if not callable(original):
                continue
            wrapped_names.add(function_name)
            if getattr(original, "_feishu_wrapped", False) is True:
                continue
            if getattr(original, "_feishu_relay_wrapped", False) is True:
                continue
            wrapped = _wrap_order_function(original, function_name=function_name, report_func=report_func)
            wrapped._feishu_wrapped = True
            setattr(module, function_name, wrapped)
            count += 1
            _log("已包装 %s.%s" % (module_name, function_name))
    return count


def _report_order(order_obj, call_context=None):
    try:
        summary = _summarize_order(order_obj, CURRENT_STRATEGY_NAME, call_context=call_context)
        _buffer.add(summary)
    except Exception as exc:
        _log("订单摘要失败: %s" % _safe_error_text(exc))


def _replay_unacked(outbox, sender):
    try:
        batches = outbox.load_unacked(OUTBOX_REPLAY_LIMIT)
    except Exception as exc:
        _log("启动补发失败: %s" % _safe_error_text(exc))
        return
    for row in batches:
        try:
            message = row.get("message", "")
            if not isinstance(message, str):
                _log("补发记录异常: message 不是字符串 batch_id=%s" % _safe_error_text(row.get("batch_id")))
                continue
            sender.send(message, replay=True, batch_id=row.get("batch_id"), orders=row.get("orders") or [])
        except Exception as exc:
            _log("补发记录异常: %s" % _safe_error_text(exc))


CURRENT_STRATEGY_NAME = _get_strategy_name()
_outbox = _Outbox(_resolve_outbox_path(CURRENT_STRATEGY_NAME))
_sender = _FeishuSender(_outbox)
_buffer = _OrderBuffer(
    BUFFER_WAIT_TIME,
    MAX_BUFFER_SIZE,
    lambda message, replay=False, retry_index=0, orders=None: _sender.send(
        message,
        replay=replay,
        retry_index=retry_index,
        orders=orders,
    ),
    SEND_JITTER_SECONDS,
)
atexit.register(_buffer.flush)
_wrapped_count = _install_wrappers(_report_order)
_log("初始化完成，策略“%s”已包装 %s 个下单函数。" % (CURRENT_STRATEGY_NAME, _wrapped_count))
_replay_unacked(_outbox, _sender)
