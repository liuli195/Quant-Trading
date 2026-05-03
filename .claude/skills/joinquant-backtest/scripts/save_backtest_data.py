"""
Parse a persisted evaluate_script output and save all tab data as structured
Markdown files plus JSON index files for the JoinQuant backtest skill.

Usage:
  python save_backtest_data.py <persisted_json_path> <run_dir>
  python save_backtest_data.py --api <api_export_json_path> <run_dir>
"""
import json
import os
import re
import sys
from datetime import datetime, timezone


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


def save_api_data(api_json_path, run_dir):
    """将 fetchAllBacktestData 输出的 JSON 转为三类 API-backed Markdown。"""
    os.makedirs(run_dir, exist_ok=True)
    tabs_dir = os.path.join(run_dir, "tabs_raw")
    os.makedirs(tabs_dir, exist_ok=True)

    with open(api_json_path, "r", encoding="utf-8") as file:
        api_data = json.load(file)

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


def save_all(persisted_path, run_dir):
    os.makedirs(run_dir, exist_ok=True)
    tabs_dir = os.path.join(run_dir, "tabs_raw")
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


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--api":
        save_api_data(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3:
        save_all(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python save_backtest_data.py <persisted_json> <run_dir>")
        print("   or: python save_backtest_data.py --api <api_export_json> <run_dir>")
        sys.exit(1)
