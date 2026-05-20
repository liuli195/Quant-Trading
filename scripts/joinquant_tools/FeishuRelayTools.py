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
