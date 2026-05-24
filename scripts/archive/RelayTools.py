can# tools.py (用于聚宽研究环境，来自：猪头战法 时间:2025-04-26 https://www.joinquant.com/view/community/detail/70825)
# 功能作用：用python装饰器在不改变聚宽内置下单函数的基础上，新增将订单信号推送至企业微信和 Redis (QMT)的功能
# 用法：在策略开头添加 import tools 即可，无需修改策略其他代码！策略名，可通过在第一行添加注释  "# 策略名：XXX" 填写即可完成中转。

import json, time, datetime, threading, requests, sys, os, atexit

# ==================== 配置区域 ====================
redis_enabled = True
REDIS_URL = "rediss://default:你的密码@你的redis地址:6379"
CHANNEL = "trade_signals"

wechat_enabled = True
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的key"
BUFFER_WAIT_TIME = 2
MAX_BUFFER_SIZE = 15
# =================================================


# ---------- 策略名自动提取 ----------
def _get_strategy_name():
    strategy_file = '/tmp/strategy/user_code.py'
    if os.path.exists(strategy_file):
        try:
            with open(strategy_file, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line.startswith('#') and len(first_line) > 1:
                    content = first_line[1:].strip()
                    if '策略名' in content:
                        name = content.split('策略名', 1)[-1].lstrip('：:').strip()
                        if name: return name
                    elif len(content) <= 50 and 'import' not in content and 'coding' not in content:
                        return content
        except:
            pass
    return "未命名策略"


CURRENT_STRATEGY_NAME = _get_strategy_name()
_print = print


def _log(msg): _print(f"[tools] {msg}")


_log(f"当前策略名: {CURRENT_STRATEGY_NAME}")

# ---------- Redis ----------
_redis_client = None


def _init_redis():
    global _redis_client
    if not redis_enabled: return
    try:
        import redis
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True,
                                       socket_connect_timeout=15, socket_timeout=10,
                                       retry_on_timeout=True, ssl_cert_reqs=None)
        _redis_client.ping()
        _log(f"Redis 连接成功，频道: {CHANNEL}")
    except Exception as e:
        _redis_client = None
        _log(f"Redis 初始化失败: {e}")


_init_redis()


def _ensure_redis():
    if _redis_client: return True
    if redis_enabled: _init_redis()
    return _redis_client is not None


# ---------- 企业微信缓冲器（支持自定义时间戳） ----------
class _Buffer:
    def __init__(self, url, wait, max_size):
        self.url, self.wait, self.max_size = url, wait, max_size
        self.buf, self.timer, self.lock = [], None, threading.Lock()

    def _send(self):
        with self.lock:
            if not self.buf: return
            sep = "\n" + "-" * 28 + "\n"
            to_send = self.buf[-self.max_size:]
            merged = sep.join(to_send)
            if len(self.buf) > self.max_size:
                merged = f"...(前略 {len(self.buf) - self.max_size} 条)\n" + merged
            self.buf.clear();
            self.timer = None
        try:
            r = requests.post(self.url, json={"msgtype": "text", "text": {"content": f"【策略信号汇总】\n{merged}"}}, timeout=3)
            if r.status_code == 200:
                _log(f"微信 合并发送成功（{merged.count(chr(10)) + 1} 条）")
            else:
                _log(f"微信 发送失败，状态码: {r.status_code}")
        except Exception as e:
            _log(f"微信 发送异常: {e}")

    def add(self, content, ts=None):
        """
        添加一条消息
        content: 消息内容（不含时间戳）
        ts: 可选的时间戳字符串（格式 'YYYY-MM-DD HH:MM:SS'），不传则使用当前时间
        """
        if ts is None:
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with self.lock:
            self.buf.append(f"[{ts}] {content}")
            if self.timer: self.timer.cancel()
            self.timer = threading.Timer(self.wait, self._send)
            self.timer.start()

    def flush(self):
        with self.lock:
            if self.timer: self.timer.cancel(); self.timer = None
        self._send()


_buffer = _Buffer(WEBHOOK_URL, BUFFER_WAIT_TIME, MAX_BUFFER_SIZE)
atexit.register(_buffer.flush)


# ---------- 辅助函数 ----------
def _send2redis(code, act, amt, price, name="", ts=None, dt=None):
    if not redis_enabled or not _ensure_redis(): return
    if ts is None: ts = time.time()
    if dt is None: dt = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        p = {
            "code": str(code), "action": "buy" if act in ("buy", "买入") else "sell",
            "amount": int(amt), "price": float(price),
            "name": str(name) if name else "",
            "strategy": CURRENT_STRATEGY_NAME,
            "ts": ts, "dt": dt
        }
        _redis_client.publish(CHANNEL, json.dumps(p, ensure_ascii=False))
        _log(f"Redis 已发送: {p['action']} {p['code']} {p['amount']}@{p['price']} [策略:{CURRENT_STRATEGY_NAME}] 时间:{dt}")
    except Exception as e:
        _log(f"Redis 发送失败: {e}")


def _send2wechat(act, sec, amt, price, name="", order_dt=None):
    """
    发送到企业微信，order_dt 为 datetime 对象或字符串
    """
    if not wechat_enabled: return
    if not name:
        try:
            name = get_security_info(sec).display_name
        except:
            name = ""
    content = f"【{CURRENT_STRATEGY_NAME}】{act} {name}({sec}) {amt}股 价格:{price}"
    # 将 order_dt 转为字符串
    ts_str = None
    if order_dt:
        if isinstance(order_dt, datetime.datetime):
            ts_str = order_dt.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(order_dt, str):
            ts_str = order_dt
    _buffer.add(content, ts=ts_str)


# ---------- 核心：订单上报 ----------
def _report_order(o):
    if o is None: return
    try:
        s = str(o.security)
        a = "买入" if o.is_buy else "卖出"
        amt = int(o.amount)
        prc = float(o.price) if o.price else 0.0

        # 直接使用订单的 add_time
        order_time = getattr(o, 'add_time', None)
        if isinstance(order_time, datetime.datetime):
            try:
                order_ts = order_time.timestamp()
            except:
                try:
                    order_ts = time.mktime(order_time.timetuple())
                except:
                    order_ts = time.time()
            dt_str = order_time.strftime("%Y-%m-%d %H:%M:%S")
            ts_val = order_ts
        else:
            dt_str = time.strftime("%Y-%m-%d %H:%M:%S")
            ts_val = time.time()
            order_time = None

        _send2redis(s, a, amt, prc, ts=ts_val, dt=dt_str)
        _send2wechat(a, s, amt, prc, order_dt=order_time)

    except Exception as e:
        _log(f"信号上报异常: {e}")


# 装饰器
def _wrap(f):
    def w(*a, **k):
        r = f(*a, **k)
        if r is not None:
            if isinstance(r, list):
                for x in r: _report_order(x)
            else:
                _report_order(r)
        return r

    return w


# ---------- 注入包装 ----------
TARGET = ['order', 'order_value', 'order_target_value', 'order_target_percent']
wrapped_set = set()
for mod in ['user_code', 'kuanke.user_space_api']:
    if mod in sys.modules:
        m = sys.modules[mod]
        for fn in TARGET:
            if hasattr(m, fn) and fn not in wrapped_set:
                setattr(m, fn, _wrap(getattr(m, fn)))
                wrapped_set.add(fn)
                _log(f"✅ 已包装 {mod}.{fn}")

_log(f"成功包装 {len(wrapped_set)} 个核心交易函数，信号推送已就绪。")
_log(f"初始化完成，策略“{CURRENT_STRATEGY_NAME}”的交易信号将自动推送。")
