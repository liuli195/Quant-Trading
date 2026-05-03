"""
Aggregate per-tab .md files into a combined backtest report.
Reads summary_metrics.json + metadata.json + tabs_raw/*.md, produces report/backtest_report.md.
"""
import os, json

from scripts.path_tools.aliases import resolve_path

TAB_ORDER = [
    'transactioninfo', 'positioninfo', 'logs', 'profile',
    'algorithm_period_return', 'benchmark_period_return',
    'max_drawdown', 'alpha', 'beta', 'sharpe', 'sortino',
    'algo_volatility', 'benchmark_volatility', 'information',
]


def process_backtest(run_dir, threshold_label):
    tabs_dir = os.path.join(run_dir, 'tabs_raw')
    report_dir = os.path.join(run_dir, 'report')
    os.makedirs(report_dir, exist_ok=True)

    if not os.path.exists(tabs_dir):
        print(f"  SKIP: {tabs_dir} not found")
        return

    # Read metadata
    meta_path = os.path.join(run_dir, 'metadata.json')
    backtest_id = ''
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8-sig') as f:
            meta = json.load(f)
            backtest_id = meta.get('backtestId', '')

    # Read summary
    summary_path = os.path.join(run_dir, 'summary_metrics.json')
    summary = {}
    if os.path.exists(summary_path):
        with open(summary_path, 'r', encoding='utf-8-sig') as f:
            summary = json.load(f)

    # Header
    report = f"# ETF动态调仓策略 — 回测详情报告\n\n"
    report += f"**偏离度阈值**: {threshold_label} | "
    report += f"**回测区间**: 2023-01-01 至 2026-04-30 | "
    report += f"**初始资金**: 50万 | **基准**: 沪深300\n\n"

    # Completeness note
    tx_path = os.path.join(tabs_dir, 'transactioninfo.md')
    pos_path = os.path.join(tabs_dir, 'positioninfo.md')
    tx_kb = os.path.getsize(tx_path)//1000 if os.path.exists(tx_path) else 0
    pos_kb = os.path.getsize(pos_path)//1000 if os.path.exists(pos_path) else 0

    report += "> **数据完整性**：月度指标表完整；交易/持仓/日志受浏览器虚拟滚动限制仅捕获可见行\n"
    if backtest_id:
        report += f"> [聚宽回测详情](https://www.joinquant.com/algorithm/backtest/detail?backtestId={backtest_id})\n\n"
    report += "---\n\n"

    # Summary metrics
    if summary:
        report += "## 收益概述\n\n| 指标 | 数值 |\n|------|------|\n"
        for key in ['策略收益', '策略年化收益', '超额收益', '基准收益',
                     '阿尔法', '贝塔', '夏普比率', '最大回撤', '索提诺比率',
                     '胜率', '盈亏比', '盈利次数', '亏损次数',
                     '信息比率', '策略波动率', '基准波动率']:
            if key in summary:
                report += f"| {key} | {summary[key]} |\n"
        report += "\n---\n\n"

    # Append each tab's .md content
    for stem in TAB_ORDER:
        path = os.path.join(tabs_dir, f'{stem}.md')
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        report += content + "\n\n---\n\n"

    # Write
    report_path = os.path.join(report_dir, 'backtest_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  {threshold_label}: {report_path} ({len(report)} chars)")


def main():
    base = str(resolve_path('backtest_runs', strategy='etf_dynamic_rebalance'))
    runs = [
        ('etf_threshold_005_20260503_214900_8c080de9', '5%'),
        ('etf_threshold_010_20260503_215400_cedcd414', '10%'),
        ('etf_threshold_015_20260503_215600_9b64a0ee', '15%'),
    ]
    for dirname, label in runs:
        process_backtest(os.path.join(base, dirname), label)
    print("\nDone.")


if __name__ == '__main__':
    main()
