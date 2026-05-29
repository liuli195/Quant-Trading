# 代码风格和策略实现规则

环境边界见 [environments.md](environments.md) <!-- pathref: docs/rules/environments.md -->；命令见 [commands.md](commands.md) <!-- pathref: docs/rules/commands.md -->。

## MUST

<a id="joinquant-strategy"></a>

### 聚宽策略

- 策略代码必须兼容聚宽 Python 3.6、旧版库和回测/模拟白名单。
- 不得使用聚宽不支持的新语法、新 API 参数或本地专属库。
- 策略参数集中定义，避免魔法数字。
- `initialize` 集中配置与注册；`handle_data` 或 `run_daily` 承载调仓逻辑。
- 改策略必须跑语法检查；改已有测试覆盖模块必须跑对应 pytest。
- 研究结论写入报告，不用代码注释承载结论。

## SHOULD

- 注释解释原因，不逐行翻译代码。
- 优先批量向量化，先筛选后计算。
- 明确处理停牌、缺失值、仓位上下限和风控参数。

## MAY

- 窄范围修复可只补最小测试；共享行为、跨模块契约或用户可见流程应扩大测试覆盖。
