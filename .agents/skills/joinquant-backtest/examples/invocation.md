# 调用示例

## 直接调用技能

```text
/joinquant-backtest strategies/alpha_rotation/alpha_rotation.py
```

含完整参数：

```text
/joinquant-backtest strategies/alpha_rotation/alpha_rotation.py 2023-01-01 2025-03-31 500000
```

## 参数说明

- 第 1 个参数：策略文件路径
- 第 2 个参数：开始日期
- 第 3 个参数：结束日期
- 第 4 个参数：初始资金

策略分析与性能分析不在本技能范围内，基于已下载的回测数据单独运行。

## 多词路径

若路径里含空格，调用时要加引号：

```text
/joinquant-backtest “strategies/my strategy/main.py” 2024-01-01 2024-12-31 1000000
```

## 典型使用场景

- 用户说”帮我把这个策略传到聚宽回测一下”
- 用户说”跑一遍 JoinQuant backtest，下载完整数据”
- 用户说”打开已有回测详情，把所有详细回测数据保存下来”

## 已有回测详情数据

在回测详情页按 `reference/browser-contracts.md` 的“API bundle 主路径”执行只读抓取，然后一次性落盘：

```bash
python "<skill_dir>/scripts/save_backtest_data.py" --api "<run_dir>/api_export.json" --strategy etf_dynamic_rebalance --run-id "<run_id>"
```
