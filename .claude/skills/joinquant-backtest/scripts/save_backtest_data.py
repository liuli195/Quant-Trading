"""
Parse a persisted evaluate_script output and save all tab data as structured
Markdown files plus JSON index files for the JoinQuant backtest skill.

Usage:
  python save_backtest_data.py <persisted_json_path> <run_dir>
  python save_backtest_data.py --api <api_export_json_path> <run_dir>
  python save_backtest_data.py <persisted_json_path> --strategy <strategy> --run-id <run_id>
  python save_backtest_data.py --api <api_export_json_path> --strategy <strategy> --run-id <run_id>
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


PARTIAL_TABS = {"logs"}


def metric_to_md(title, text):
    """Tab-separated metric table -> Markdown table."""
    lines = text.strip().split("\n")
    if not lines:
        return f"# {title}\n\n(无数据)\n"

    title = lines[0].strip().replace("\ufeff", "") or title
    md = f"# {title}\n\n"
    md += "| 日期 | 1个月 | 3个月 | 6个月 | 12个月 |\n"
    md += "|------|-------|-------|-------|--------|\n"
    for line in lines[2:]:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 5:
            md += "| " + " | ".join(p.strip() for p in parts[:5]) + " |\n"
    return md


def transaction_to_md(text):
    """Transaction detail -> monthly summary + detail table."""
    lines = text.strip().split("\n")
    records = []
    for line in lines:
        line = line.strip()
        if not line or "\xa0" in line:
            continue
        if any(kw in line for kw in ["品种 交易类型", "Group by", "日期\n", "委托时间\n"]):
            continue
        parts = line.split("\t")
        if len(parts) >= 10:
            records.append(
                {
                    "date": parts[0].strip(),
                    "time": parts[1].strip(),
                    "symbol": parts[2].strip(),
                    "dir": parts[3].strip(),
                    "amount": parts[5].strip(),
                    "price": parts[6].strip(),
                    "value": parts[7].strip(),
                    "pnl": parts[8].strip() if len(parts) > 8 else "",
                    "comm": parts[9].strip() if len(parts) > 9 else "",
                }
            )

    md = "# 交易详情\n\n"
    if not records:
        return md + "(无交易数据)\n"

    buy = sum(1 for r in records if r["dir"] == "买")
    sell = sum(1 for r in records if r["dir"] == "卖")
    by_month = {}
    for record in records:
        by_month.setdefault(record["date"][:7], []).append(record)

    md += f"- 总成交：{len(records)} 笔（买 {buy} / 卖 {sell}），涉及 {len(by_month)} 个月\n\n"
    md += "## 月度汇总\n\n"
    md += "| 月份 | 笔数 | 买入 | 卖出 | 买入额 | 卖出额 | 净买入 |\n"
    md += "|------|------|------|------|--------|--------|--------|\n"
    for month in sorted(by_month):
        month_records = by_month[month]
        buys = [r for r in month_records if r["dir"] == "买"]
        sells = [r for r in month_records if r["dir"] == "卖"]
        buy_value = sum(float(r["value"].replace(",", "")) for r in buys)
        sell_value = sum(float(r["value"].replace(",", "")) for r in sells)
        md += (
            f"| {month} | {len(month_records)} | {len(buys)} | {len(sells)} | "
            f"{buy_value:,.0f} | {-sell_value:,.0f} | {buy_value + sell_value:,.0f} |\n"
        )

    md += "\n## 逐笔明细\n\n"
    md += "| 日期 | 标的 | 方向 | 数量 | 成交价 | 成交额 | 平仓盈亏 | 手续费 |\n"
    md += "|------|------|------|------|--------|--------|----------|--------|\n"
    sym_map = {
        "黄金ETF(518880.XSHG)": "黄金ETF",
        "人工智能ETF易方达(159819.XSHE)": "AI ETF",
        "纳指ETF(513100.XSHG)": "纳指ETF",
    }
    for record in records:
        symbol = record["symbol"]
        for full, short in sym_map.items():
            symbol = symbol.replace(full, short)
        md += (
            f"| {record['date']} | {symbol} | {record['dir']} | {record['amount']} | "
            f"{record['price']} | {record['value']} | {record['pnl']} | {record['comm']} |\n"
        )
    return md


def position_to_md(text):
    """Daily position -> grouped Markdown tables."""
    lines = text.strip().split("\n")
    days = {}
    current_date = None
    current_holdings = []
    for line in lines:
        line = line.strip()
        if not line or "Group by" in line or "品种 多空" in line or "标的\n" in line:
            continue
        match = re.match(r"^(\d{4}-\d{2}-\d{2})$", line)
        if match:
            if current_date and current_holdings:
                days[current_date] = current_holdings
            current_date = match.group(1)
            current_holdings = []
        elif current_date and line:
            parts = line.split("\t")
            if "Cash" in parts[0]:
                continue
            if any("总共:" in p for p in parts):
                total = next(p.replace("总共:", "").strip() for p in parts if "总共:" in p)
                current_holdings.append({"type": "total", "value": total})
                continue
            if len(parts) >= 5:
                current_holdings.append(
                    {
                        "type": "holding",
                        "sym": parts[0].strip(),
                        "qty": parts[1].strip() if len(parts) > 1 else "",
                        "price": parts[2].strip() if len(parts) > 2 else "",
                        "mv": parts[3].strip() if len(parts) > 3 else "",
                        "pnl": parts[4].strip() if len(parts) > 4 else "",
                    }
                )
    if current_date and current_holdings:
        days[current_date] = current_holdings

    sym_map = {
        "黄金ETF(518880.XSHG)": "黄金ETF",
        "人工智能ETF易方达(159819.XSHE)": "AI ETF",
        "纳指ETF(513100.XSHG)": "纳指ETF",
    }
    md = f"# 每日持仓与收益\n\n- 持仓天数：{len(days)}\n\n"
    for date in sorted(days):
        md += f"## {date}\n\n"
        md += "| 标的 | 数量 | 收盘价 | 市值 | 浮盈 |\n"
        md += "|------|------|--------|------|------|\n"
        for holding in days[date]:
            if holding["type"] == "total":
                md += f"| **合计** | | | **{holding['value']}** | |\n"
            else:
                symbol = holding["sym"]
                for full, short in sym_map.items():
                    symbol = symbol.replace(full, short)
                md += (
                    f"| {symbol} | {holding['qty']} | {holding['price']} | "
                    f"{holding['mv']} | {holding['pnl']} |\n"
                )
        md += "\n"
    return md


# ============================================================
# API JSON 格式转换器
# ============================================================
# 处理通过内部 API (fetchAllBacktestData) 获取的结构化 JSON 数据，
# 替代原来的 DOM 文本解析方式，数据完整度 100%。

SYM_MAP = {
    "黄金ETF(518880.XSHG)": "黄金ETF",
    "人工智能ETF易方达(159819.XSHE)": "AI ETF",
    "纳指ETF(513100.XSHG)": "纳指ETF",
}


def _short_symbol(name):
    for full, short in SYM_MAP.items():
        name = name.replace(full, short)
    return name


def api_transaction_to_md(transactions):
    """API JSON 交易数据 → Markdown。"""
    md = "# 交易详情\n\n"
    if not transactions:
        return md + "(无交易数据)\n"

    buy_count = sum(1 for t in transactions if t.get("transaction") == "买")
    sell_count = sum(1 for t in transactions if t.get("transaction") == "卖")

    by_month = {}
    for t in transactions:
        month = t["date"][:7]
        by_month.setdefault(month, []).append(t)

    md += f"- 总成交：{len(transactions)} 笔（买 {buy_count} / 卖 {sell_count}），"
    md += f"涉及 {len(by_month)} 个月\n\n"

    md += "## 月度汇总\n\n"
    md += "| 月份 | 笔数 | 买入 | 卖出 | 买入额 | 卖出额 | 净买入 |\n"
    md += "|------|------|------|------|--------|--------|--------|\n"
    for month in sorted(by_month):
        month_txns = by_month[month]
        buys = [t for t in month_txns if t.get("transaction") == "买"]
        sells = [t for t in month_txns if t.get("transaction") == "卖"]
        buy_value = sum(float(t["total"]) for t in buys)
        sell_value = sum(float(t["total"]) for t in sells)
        md += (
            f"| {month} | {len(month_txns)} | {len(buys)} | {len(sells)} | "
            f"{buy_value:,.0f} | {-sell_value:,.0f} | {buy_value + sell_value:,.0f} |\n"
        )

    md += "\n## 逐笔明细\n\n"
    md += "| 日期 | 标的 | 方向 | 数量 | 成交价 | 成交额 | 平仓盈亏 | 手续费 |\n"
    md += "|------|------|------|------|--------|--------|----------|--------|\n"
    for t in transactions:
        symbol = _short_symbol(t.get("stock", ""))
        md += (
            f"| {t['date']} | {symbol} | {t.get('transaction', '')} | "
            f"{t.get('amount', '')} | {t.get('price', '')} | "
            f"{t.get('total', '')} | {t.get('gains', '')} | "
            f"{t.get('commission', '')} |\n"
        )
    return md


def api_position_to_md(positions):
    """API JSON 持仓数据 → 按日期分组的 Markdown。"""
    md = "# 每日持仓与收益\n\n"

    # 过滤掉 Cash 行
    holdings = [p for p in positions if p.get("security") == "基金"]

    if not holdings:
        return md + "(无持仓数据)\n"

    by_date = {}
    for p in holdings:
        date = p["date"]
        by_date.setdefault(date, []).append(p)

    md += f"- 持仓天数：{len(by_date)}\n\n"

    for date in sorted(by_date):
        md += f"## {date}\n\n"
        md += "| 标的 | 数量 | 收盘价 | 市值 | 当日盈亏 | 累计盈亏 | 成本价 | 权重 |\n"
        md += "|------|------|--------|------|----------|----------|--------|------|\n"

        total_value = 0
        for p in by_date[date]:
            symbol = _short_symbol(p.get("stock", ""))
            md += (
                f"| {symbol} | {p.get('amount', '')} | "
                f"{p.get('price', '')} | {p.get('value', '')} | "
                f"{p.get('dailyGains', '')} | {p.get('gain', '')} | "
                f"{p.get('avgCost', '')} | {p.get('positionPersent', '')} |\n"
            )
            total_value += float(p.get("totalValue", p.get("value", 0)))

        md += f"| **合计** | | | **{total_value:,.2f}** | | | | |\n\n"

    return md


def api_results_to_md(results):
    """API 每日收益数据 → Markdown 表格。"""
    md = "# 每日收益\n\n"

    if not results:
        return md + "(无收益数据)\n"

    # 合并多个 result 页
    all_times = []
    all_returns = []
    all_bm_returns = []

    for page in results:
        bench = page.get("benchmark", {})
        times = bench.get("time", [])
        returns_list = page.get("returns", [])
        bm_returns_list = page.get("benchmark_returns", [])

        for i, ts in enumerate(times):
            from datetime import datetime, timezone

            dt_obj = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            all_times.append(dt_obj.strftime("%Y-%m-%d"))
            all_returns.append(returns_list[i] if i < len(returns_list) else "")
            all_bm_returns.append(
                bm_returns_list[i] if i < len(bm_returns_list) else ""
            )

    md += f"- 交易日数：{len(all_times)}\n\n"
    md += "| 日期 | 策略收益 | 基准收益 | 超额收益 |\n"
    md += "|------|----------|----------|----------|\n"

    for i in range(len(all_times)):
        strat_r = all_returns[i] if isinstance(all_returns[i], (int, float)) else 0
        bm_r = all_bm_returns[i] if isinstance(all_bm_returns[i], (int, float)) else 0
        excess = strat_r - bm_r if strat_r != 0 or bm_r != 0 else 0
        md += f"| {all_times[i]} | {strat_r:.6f} | {bm_r:.6f} | {excess:.6f} |\n"

    return md


RISK_TAB_DEFS = [
    ("algorithm_period_return", "策略收益"),
    ("benchmark_period_return", "基准收益"),
    ("alpha", "阿尔法"),
    ("beta", "贝塔"),
    ("sharpe", "夏普比率"),
    ("sortino", "索提诺比率"),
    ("information", "信息比率"),
    ("algo_volatility", "波动率"),
    ("benchmark_volatility", "基准波动率"),
    ("max_drawdown", "最大回撤"),
]


def api_result_rows_to_md(rows):
    """新版 bundle 的 result_rows → Markdown 表格。"""
    md = "# 每日收益\n\n"
    if not rows:
        return md + "(无收益数据)\n"

    md += f"- 交易日数：{len(rows)}\n\n"
    md += "| 日期 | 策略收益 | 基准收益 | 当日盈利 | 当日亏损 | 当日买入 | 当日卖出 |\n"
    md += "|------|----------|----------|----------|----------|----------|----------|\n"
    for row in rows:
        md += (
            f"| {row.get('date', '')} | {row.get('algorithm_return_value', '')} | "
            f"{row.get('benchmark_return_value', '')} | {row.get('gains_earn', '')} | "
            f"{row.get('gains_lose', '')} | {row.get('orders_buy', '')} | "
            f"{row.get('orders_sell', '')} |\n"
        )
    return md


def api_risk_tab_to_md(title, rows):
    """新版 bundle 的单个风险标签页 → Markdown 表格。"""
    md = f"# {title}\n\n"
    if not rows:
        return md + "(无数据)\n"

    md += "| 日期 | 1个月 | 3个月 | 6个月 | 12个月 |\n"
    md += "|------|-------|-------|-------|--------|\n"
    for row in rows:
        md += (
            f"| {row.get('date', '')} | {row.get('1month', '')} | "
            f"{row.get('3month', '')} | {row.get('6month', '')} | "
            f"{row.get('12month', '')} |\n"
        )
    return md


def api_logs_to_md(log_rows, partial=False, title="策略日志"):
    text = "\n".join(str(row) for row in log_rows)
    md = logs_to_md(text)
    if partial:
        md += "\n> 注：日志接口返回 `max=true`，当前文件为免费只读接口可获取部分；未使用扣积分导出。\n"
    if title != "策略日志":
        md = md.replace("# 策略日志", f"# {title}", 1)
    return md


def api_profile_to_md(profile_text):
    """profile 接口响应可能是 JSON 字符串，也可能是原始文本。"""
    text = profile_text or ""
    try:
        parsed = json.loads(text)
        text = parsed.get("data", {}).get("profile", text)
    except (TypeError, json.JSONDecodeError):
        pass
    return profile_to_md(text)


def summary_metrics_from_stats(stats):
    data = (stats or {}).get("data", {})

    def pct(value):
        return "" if value is None else f"{float(value) * 100:.2f}%"

    def fixed(value, digits=3):
        return "" if value is None else f"{float(value):.{digits}f}"

    return {
        "策略收益": pct(data.get("algorithm_return")),
        "策略年化收益": pct(data.get("annual_algo_return")),
        "基准收益": pct(data.get("benchmark_return")),
        "超额收益": pct(data.get("excess_return")),
        "最大回撤": pct(data.get("max_drawdown")),
        "最大回撤区间": ",".join(data.get("max_drawdown_period") or []),
        "阿尔法": fixed(data.get("alpha")),
        "贝塔": fixed(data.get("beta")),
        "夏普比率": fixed(data.get("sharpe")),
        "索提诺比率": fixed(data.get("sortino")),
        "信息比率": fixed(data.get("information")),
        "策略波动率": fixed(data.get("algorithm_volatility")),
        "基准波动率": fixed(data.get("benchmark_volatility")),
        "胜率": fixed(data.get("win_ratio")),
        "盈亏比": fixed(data.get("profit_loss_ratio")),
        "日胜率": fixed(data.get("day_win_ratio")),
        "盈利次数": data.get("win_count"),
        "亏损次数": data.get("lose_count"),
    }


def metadata_from_api_bundle(api_data):
    meta = default_metadata(extraction_method="api")
    bundle_meta = api_data.get("metadata") or {}
    meta.update(
        {
            "strategy_name": bundle_meta.get("strategy_name") or bundle_meta.get("strategyName", ""),
            "start_date_effective": bundle_meta.get("start_date_effective", ""),
            "end_date_effective": bundle_meta.get("end_date_effective", ""),
            "capital": bundle_meta.get("capital"),
            "backtest_id": bundle_meta.get("backtest_id", ""),
            "backtest_url": bundle_meta.get("backtest_url", ""),
            "generated_at": bundle_meta.get("generated_at") or datetime.now(timezone.utc).isoformat(),
            "extraction_method": bundle_meta.get("extraction_method", "api"),
            "export_used": bundle_meta.get("export_used", False),
            "frequency": bundle_meta.get("frequency", ""),
            "py_version": bundle_meta.get("py_version", ""),
        }
    )
    return meta


def write_report_files(api_data, run_dir, report_dir, files_written):
    os.makedirs(report_dir, exist_ok=True)
    summary = summary_metrics_from_stats(api_data.get("stats", {}))
    meta = metadata_from_api_bundle(api_data)
    counts = api_data.get("counts", {})
    partial = api_data.get("partial", {})

    def line(key):
        return f"| {key} | {summary.get(key, '')} |"

    backtest_report = "# 回测数据汇总\n\n"
    backtest_report += f"- 策略名称：{meta.get('strategy_name', '')}\n"
    backtest_report += f"- 回测 ID：{meta.get('backtest_id', '')}\n"
    backtest_report += f"- 回测 URL：{meta.get('backtest_url', '')}\n"
    backtest_report += f"- 区间：{meta.get('start_date_effective', '')} 至 {meta.get('end_date_effective', '')}\n"
    backtest_report += "- 提取方式：聚宽详情页只读 JSON 接口；未使用扣积分导出。\n\n"
    backtest_report += "## 核心指标\n\n| 指标 | 值 |\n| --- | --- |\n"
    for key in ["策略收益", "策略年化收益", "基准收益", "超额收益", "最大回撤", "夏普比率", "阿尔法", "贝塔", "信息比率"]:
        backtest_report += line(key) + "\n"
    backtest_report += "\n## 数据覆盖\n\n| 数据 | 记录数 | 完整度 |\n| --- | ---: | --- |\n"
    backtest_report += f"| 交易详情 | {counts.get('transactions', '')} | {'部分' if partial.get('transactions') else '完整'} |\n"
    backtest_report += f"| 每日持仓&收益 | {counts.get('positions', '')} | {'部分' if partial.get('positions') else '完整'} |\n"
    backtest_report += f"| 每日收益 | {counts.get('result_rows', '')} | 完整 |\n"
    backtest_report += f"| 风险标签页 | {counts.get('risk_rows', '')} | 10 个标签完整 |\n"
    backtest_report += f"| 日志 | {counts.get('logs', '')} | {'免费接口部分' if partial.get('logs') else '完整'} |\n"

    with open(os.path.join(report_dir, "backtest_report.md"), "w", encoding="utf-8") as file:
        file.write(backtest_report)

    files_written.extend(
        [
            ("report/backtest_report.md", 1),
        ]
    )


def _ensure_repo_on_path():
    """Add the repository root to sys.path so path_tools can be imported."""
    candidates = []
    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    script_path = Path(__file__).resolve()
    candidates.extend([script_path.parent, *script_path.parents])

    for candidate in candidates:
        if (candidate / "path_aliases.json").is_file():
            repo = str(candidate)
            if repo not in sys.path:
                sys.path.insert(0, repo)
            return candidate

    raise RuntimeError("Could not find repository root containing path_aliases.json")


def resolve_output_dirs(run_dir=None, strategy=None, run_id=None):
    """Resolve output directories, preferring path aliases when strategy/run_id are provided."""
    if run_dir and (strategy or run_id):
        raise ValueError("Use either <run_dir> or --strategy/--run-id, not both")

    if run_dir:
        resolved_run_dir = os.path.abspath(run_dir)
        tabs_dir = os.path.join(resolved_run_dir, "tabs_raw")
        report_dir = os.path.join(resolved_run_dir, "report")
    else:
        if not strategy or not run_id:
            raise ValueError("Either <run_dir> or both --strategy and --run-id are required")

        _ensure_repo_on_path()
        from scripts.path_tools.aliases import ensure_dir

        resolved_run_dir = str(ensure_dir("backtest_run", strategy=strategy, run_id=run_id))
        tabs_dir = str(ensure_dir("backtest_tabs_dir", strategy=strategy, run_id=run_id))
        report_dir = str(ensure_dir("backtest_report_dir", strategy=strategy, run_id=run_id))

    os.makedirs(resolved_run_dir, exist_ok=True)
    os.makedirs(tabs_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)
    return resolved_run_dir, tabs_dir, report_dir


def save_api_data(api_json_path, run_dir, tabs_dir=None):
    """将 fetchAllBacktestData 或 fetchExistingBacktestBundle 输出的 JSON 落盘。"""
    os.makedirs(run_dir, exist_ok=True)
    tabs_dir = tabs_dir or os.path.join(run_dir, "tabs_raw")
    report_dir = os.path.join(run_dir, "report")
    os.makedirs(tabs_dir, exist_ok=True)
    os.makedirs(report_dir, exist_ok=True)

    with open(api_json_path, "r", encoding="utf-8") as file:
        api_data = json.load(file)

    if api_data.get("metadata", {}).get("schema_version") == 2 or "risk_tabs" in api_data:
        return save_api_bundle_data(api_json_path, api_data, run_dir, tabs_dir, report_dir)

    transactions = api_data.get("transactions", [])
    positions = api_data.get("positions", [])
    results = api_data.get("results", [])

    # 写入完整的 Markdown
    files_written = []

    tx_md = api_transaction_to_md(transactions)
    tx_path = os.path.join(tabs_dir, "transactioninfo.md")
    with open(tx_path, "w", encoding="utf-8") as file:
        file.write(tx_md)
    files_written.append(("transactioninfo.md", len(transactions)))

    pos_md = api_position_to_md(positions)
    pos_path = os.path.join(tabs_dir, "positioninfo.md")
    with open(pos_path, "w", encoding="utf-8") as file:
        file.write(pos_md)
    files_written.append(("positioninfo.md", len(positions)))

    ret_md = api_results_to_md(results)
    ret_path = os.path.join(tabs_dir, "daily_returns.md")
    with open(ret_path, "w", encoding="utf-8") as file:
        file.write(ret_md)
    files_written.append(("daily_returns.md", len(results)))

    metadata_path = os.path.join(run_dir, "metadata.json")
    summary_path = os.path.join(run_dir, "summary_metrics.json")
    index_path = os.path.join(run_dir, "all_data.json")

    ensure_json_file(metadata_path, default_metadata(extraction_method="api"))
    ensure_json_file(summary_path, {})

    index = build_api_index(api_json_path, files_written)
    with open(index_path, "w", encoding="utf-8") as file:
        json.dump(index, file, ensure_ascii=False, indent=2)

    print(f"Saved {len(files_written)} API-backed Markdown files to {tabs_dir}")
    for name, count in files_written:
        print(f"  {name}: {count} records")
    print(f"Created index file: {index_path}")
    return {name: count for name, count in files_written}


def save_api_bundle_data(api_json_path, api_data, run_dir, tabs_dir, report_dir):
    """新版一次性 JS bundle → 现有输出契约。"""
    files_written = []

    transactions = api_data.get("transactions", {}).get("rows", [])
    positions = api_data.get("positions", {}).get("rows", [])
    result_rows = api_data.get("result_rows", [])
    logs = api_data.get("logs", {}).get("rows", [])
    error_logs = api_data.get("error_logs", {}).get("rows", [])
    risk_tabs = api_data.get("risk_tabs", {})

    outputs = {
        "transactioninfo.md": api_transaction_to_md(transactions),
        "positioninfo.md": api_position_to_md(positions),
        "daily_returns.md": api_result_rows_to_md(result_rows),
        "logs.md": api_logs_to_md(logs, partial=api_data.get("partial", {}).get("logs", False)),
        "profile.md": api_profile_to_md(api_data.get("profile_text", "")),
    }

    if error_logs:
        outputs["error_logs.md"] = api_logs_to_md(error_logs, title="错误日志")

    for name, title in RISK_TAB_DEFS:
        tab = risk_tabs.get(name, {})
        outputs[f"{name}.md"] = api_risk_tab_to_md(tab.get("label") or title, tab.get("rows", []))

    for filename, content in outputs.items():
        with open(os.path.join(tabs_dir, filename), "w", encoding="utf-8") as file:
            file.write(content)
        if filename == "transactioninfo.md":
            count = len(transactions)
        elif filename == "positioninfo.md":
            count = len(positions)
        elif filename == "daily_returns.md":
            count = len(result_rows)
        elif filename == "logs.md":
            count = len(logs)
        elif filename == "error_logs.md":
            count = len(error_logs)
        elif filename.replace(".md", "") in risk_tabs:
            count = len(risk_tabs[filename.replace(".md", "")].get("rows", []))
        else:
            count = len(content)
        files_written.append((filename, count))

    metadata = metadata_from_api_bundle(api_data)
    summary_metrics = summary_metrics_from_stats(api_data.get("stats", {}))

    with open(os.path.join(run_dir, "metadata.json"), "w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    with open(os.path.join(run_dir, "summary_metrics.json"), "w", encoding="utf-8") as file:
        json.dump(summary_metrics, file, ensure_ascii=False, indent=2)

    write_report_files(api_data, run_dir, report_dir, files_written)

    index = build_api_bundle_index(api_json_path, files_written, api_data)
    with open(os.path.join(run_dir, "all_data.json"), "w", encoding="utf-8") as file:
        json.dump(index, file, ensure_ascii=False, indent=2)

    print(f"Saved {len(files_written)} API bundle files to {tabs_dir}")
    for name, count in files_written:
        print(f"  {name}: {count} records")
    print(f"Created index file: {os.path.join(run_dir, 'all_data.json')}")
    return {name: count for name, count in files_written}


def logs_to_md(text):
    """Logs -> summary stats + excerpt."""
    lines = text.strip().split("\n")
    info = sum(1 for line in lines if "INFO" in line)
    warning = sum(1 for line in lines if "WARNING" in line)
    error = sum(1 for line in lines if "ERROR" in line)
    rebalance = len([line for line in lines if "触发调仓" in line or "执行调仓" in line])
    skip = len([line for line in lines if "跳过本次调仓" in line])

    md = "# 策略日志\n\n"
    md += f"- INFO：{info}  |  WARNING：{warning}  |  ERROR：{error}\n"
    md += f"- 触发调仓：{rebalance}  |  跳过调仓：{skip}\n\n"
    md += "```text\n"
    for line in lines[:30]:
        md += line + "\n"
    if len(lines) > 30:
        md += f"\n... （剩余 {len(lines) - 30} 行未展开） ...\n\n"
        for line in lines[-15:]:
            md += line + "\n"
    md += "```\n"
    return md


def profile_to_md(text):
    """Profiler output -> per-function Markdown blocks."""
    md = "# 性能分析\n\n"
    sections = text.split("\n\n")
    hit = False
    for section in sections:
        if "Function:" not in section:
            continue
        hit = True
        func_match = re.search(r"Function: (\w+)", section)
        time_match = re.search(r"Total time: ([\d.]+) s", section)
        name = func_match.group(1) if func_match else "未知函数"
        total_time = time_match.group(1) if time_match else "?"
        md += f"## {name}\n\n"
        md += f"- 总耗时：{total_time}s\n\n"
        md += f"```text\n{section}\n```\n\n"
    if not hit:
        md += "(无性能分析数据)\n"
    return md


CONVERTERS = {
    "transactioninfo": transaction_to_md,
    "positioninfo": position_to_md,
    "logs": logs_to_md,
    "profile": profile_to_md,
}


def extract_from_persisted(persisted_path):
    """Parse the persisted evaluate_script output and return {tab_name: text}."""
    with open(persisted_path, "r", encoding="utf-8") as file:
        raw = json.load(file)
    text = raw[0]["text"]
    match = re.search(r"```json\n(.+?)\n```", text, re.DOTALL)
    if not match:
        raise ValueError("Could not find JSON block in persisted output")
    return json.loads(json.loads(match.group(1)))


def ensure_json_file(path, default_content):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as file:
            json.dump(default_content, file, ensure_ascii=False, indent=2)


def default_metadata(extraction_method=None):
    metadata = {
        "strategy_name": "",
        "strategy_file": "",
        "strategy_dir": "",
        "start_date_requested": "",
        "start_date_effective": "",
        "end_date_requested": "",
        "end_date_effective": "",
        "capital": None,
        "need_performance": False,
        "need_analysis": True,
        "backtest_id": "",
        "backtest_url": "",
        "generated_at": "",
    }
    if extraction_method:
        metadata["extraction_method"] = extraction_method
    return metadata


def build_index(data, persisted_path):
    return {
        "persisted_json": os.path.abspath(persisted_path),
        "extraction_method": "dom",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tabs": {
            key: {
                "path": f"tabs_raw/{key}.md",
                "partial": key in PARTIAL_TABS,
                "raw_text_length": len(text),
            }
            for key, text in data.items()
        },
    }


def build_api_index(api_json_path, files_written):
    return {
        "api_export_json": os.path.abspath(api_json_path),
        "extraction_method": "api",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tabs": {
            name.replace(".md", ""): {
                "path": f"tabs_raw/{name}",
                "partial": False,
                "record_count": count,
            }
            for name, count in files_written
        },
        "supplemental_dom_tabs": {
            "status": "not_generated_by_api_mode",
            "note": "Use collectBacktestTabTexts() for logs, profile, and static metric tabs when needed.",
        },
    }


def build_api_bundle_index(api_json_path, files_written, api_data):
    partial = api_data.get("partial", {})

    def is_partial(name):
        key = name.replace(".md", "")
        if key == "logs":
            return bool(partial.get("logs"))
        if key == "transactioninfo":
            return bool(partial.get("transactions"))
        if key == "positioninfo":
            return bool(partial.get("positions"))
        return False

    return {
        "api_export_json": os.path.abspath(api_json_path),
        "extraction_method": "api_bundle",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": api_data.get("counts", {}),
        "partial": partial,
        "tabs": {
            name.replace(".md", "").replace("report/", ""): {
                "path": f"tabs_raw/{name}" if not name.startswith("report/") else name,
                "partial": is_partial(name),
                "record_count": count,
            }
            for name, count in files_written
        },
        "note": "Generated from one fetchExistingBacktestBundle() JSON payload; no JoinQuant export endpoint was confirmed or used.",
    }


def save_all(persisted_path, run_dir, tabs_dir=None):
    os.makedirs(run_dir, exist_ok=True)
    tabs_dir = tabs_dir or os.path.join(run_dir, "tabs_raw")
    os.makedirs(tabs_dir, exist_ok=True)

    data = extract_from_persisted(persisted_path)

    for key, text in data.items():
        converter = CONVERTERS.get(key, lambda current_text, title=key: metric_to_md(title, current_text))
        md_content = converter(text)
        md_path = os.path.join(tabs_dir, f"{key}.md")
        with open(md_path, "w", encoding="utf-8") as file:
            file.write(md_content)

    metadata_path = os.path.join(run_dir, "metadata.json")
    summary_path = os.path.join(run_dir, "summary_metrics.json")
    index_path = os.path.join(run_dir, "all_data.json")

    ensure_json_file(
        metadata_path,
        default_metadata(extraction_method="dom"),
    )
    ensure_json_file(summary_path, {})

    with open(index_path, "w", encoding="utf-8") as file:
        json.dump(build_index(data, persisted_path), file, ensure_ascii=False, indent=2)

    print(f"Saved {len(data)} markdown files to {tabs_dir}")
    print(f"Created index file: {index_path}")
    return data


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_json",
        nargs="?",
        help="Persisted DOM JSON path, or <run_dir> when --api is used with legacy arguments.",
    )
    parser.add_argument("run_dir", nargs="?", help="Legacy output run directory.")
    parser.add_argument("--api", dest="api_json", help="API export JSON path.")
    parser.add_argument("--strategy", help="Strategy alias variable used by path_aliases.json.")
    parser.add_argument("--run-id", help="Run id alias variable used by path_aliases.json.")
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.api_json:
            if args.run_dir:
                parser.error("--api accepts at most one legacy <run_dir> positional argument")
            run_dir_arg = args.input_json
            run_dir, tabs_dir, _ = resolve_output_dirs(
                run_dir=run_dir_arg,
                strategy=args.strategy,
                run_id=args.run_id,
            )
            save_api_data(args.api_json, run_dir, tabs_dir=tabs_dir)
            return 0

        if not args.input_json:
            parser.error("persisted_json is required when --api is not used")

        run_dir, tabs_dir, _ = resolve_output_dirs(
            run_dir=args.run_dir,
            strategy=args.strategy,
            run_id=args.run_id,
        )
        save_all(args.input_json, run_dir, tabs_dir=tabs_dir)
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
