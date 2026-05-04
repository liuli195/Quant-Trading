# 调用示例

## 直接调用技能

```text
/joinquant-backtest strategies/alpha_rotation/alpha_rotation.py
```

含完整参数：

```text
/joinquant-backtest strategies/alpha_rotation/alpha_rotation.py 2023-01-01 2025-03-31 500000 true
```

## 参数说明

- 第 1 个参数：策略文件路径
- 第 2 个参数：开始日期
- 第 3 个参数：结束日期
- 第 4 个参数：初始资金
- 第 5 个参数：是否执行性能分析，建议传 `true` 或 `false`

策略分析报告固定生成，不再作为位置参数传入。

## 多词路径

若路径里含空格，调用时要加引号：

```text
/joinquant-backtest "strategies/my strategy/main.py" 2024-01-01 2024-12-31 1000000 false
```

## 典型使用场景

- 用户说“帮我把这个策略传到聚宽回测一下”
- 用户说“跑一遍 JoinQuant backtest，并给我分析报告”
- 用户说“做一次 performance 分析，看看 profile 结果”
