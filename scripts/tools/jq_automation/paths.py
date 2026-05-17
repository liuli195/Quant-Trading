from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from scripts.tools.path_tools.aliases import ensure_dir, find_repo_root, resolve_path


BACKTEST_DETAIL_URL = "https://www.joinquant.com/algorithm/backtest/detail?backtestId={backtest_id}"
BACKTEST_ID_RE = re.compile(r"backtestId=([^&#]+)")


def repo_root() -> Path:
    return find_repo_root()


def default_chrome_user_data_dir(root: Path | None = None) -> Path:
    return (root or repo_root()) / ".local" / "chrome-jq"


def automation_tmp_dir(root: Path | None = None) -> Path:
    path = (root or repo_root()) / ".local" / "jq-automation"
    path.mkdir(parents=True, exist_ok=True)
    return path


def quota_ledger_dir() -> Path:
    return ensure_dir("joinquant_quota_ledger")


def resolve_run_dir(strategy: str, run_id: str) -> Path:
    return ensure_dir("backtest_run", strategy=strategy, run_id=run_id)


def resolve_tabs_dir(strategy: str, run_id: str) -> Path:
    return ensure_dir("backtest_tabs_dir", strategy=strategy, run_id=run_id)


def resolve_batch_manifest(strategy: str, batch_id: str) -> Path:
    return resolve_path("test_batch", strategy=strategy, batch_id=batch_id) / "manifest.json"


def extract_backtest_id(target: str) -> str:
    match = BACKTEST_ID_RE.search(target)
    if match:
        return match.group(1)

    parsed = urlparse(target)
    if parsed.query:
        values = parse_qs(parsed.query).get("backtestId")
        if values:
            return values[0]

    if re.fullmatch(r"[A-Za-z0-9_-]+", target):
        return target
    return ""


def detail_url_for(target: str) -> str:
    if target.startswith("http://") or target.startswith("https://"):
        return target
    backtest_id = extract_backtest_id(target)
    return BACKTEST_DETAIL_URL.format(backtest_id=backtest_id)


def make_run_id(backtest_id: str, now: datetime | None = None) -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "", backtest_id).strip()
    if not clean:
        clean = "unknown"
    current = now or datetime.now()
    return f"{current:%Y%m%d-%H%M}-bt{clean}"
