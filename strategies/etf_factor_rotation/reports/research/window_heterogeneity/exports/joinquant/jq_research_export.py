import datetime
import json
import os
from jqdata import *

ETF_CODES = ['159819.XSHE', '513100.XSHG', '518880.XSHG']
FIELDS = ["open", "close", "high", "low", "money"]
HISTORY_START = "2018-01-01"
SCORE_START = "2021-01-01"
SCORE_END = "2026-04-30"
EXPORT_PATH = "jq_auto_exports/etf_factor_rotation_window_research_prices.json"


def _jsonable(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        return float(value)
    except Exception:
        return value


calendar = get_trade_days(start_date=HISTORY_START, end_date=datetime.date.today())
payload = {
    "metadata": {
        "strategy": "etf_factor_rotation",
        "history_start": HISTORY_START,
        "score_start": SCORE_START,
        "score_end": SCORE_END,
        "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "fields": FIELDS,
    },
    "calendar": [_jsonable(day) for day in calendar],
    "prices": {},
}

for code in ETF_CODES:
    frame = get_price(
        code,
        start_date=HISTORY_START,
        end_date=datetime.date.today(),
        frequency="daily",
        fields=FIELDS,
        skip_paused=True,
        fq=None,
        panel=False,
    )
    frame = frame.reset_index().rename(columns={"index": "date"})
    records = []
    for row in frame.to_dict(orient="records"):
        records.append({key: _jsonable(value) for key, value in row.items()})
    payload["prices"][code] = records

export_dir = os.path.dirname(EXPORT_PATH)
if export_dir:
    home_dir = os.path.expanduser("~") or "/home/jquser"
    if home_dir == "/":
        home_dir = "/home/jquser"
    os.makedirs(os.path.join(home_dir, export_dir), exist_ok=True)
write_file(EXPORT_PATH, json.dumps(payload, ensure_ascii=False), append=False)
print("window research export written: " + EXPORT_PATH)
