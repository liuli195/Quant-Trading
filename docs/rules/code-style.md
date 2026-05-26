# 代码风格和策略实现规则

## MUST

- Python 环境和命令入口按 [commands.md](commands.md) <!-- pathref: docs/rules/commands.md --> 执行。
- 策略代码仅在聚宽云端运行，本地不假装完整复现聚宽交易环境。
- **环境兼容**：策略代码必须兼容 Python 3.6 语法和聚宽回测环境可用库。环境差异详见 [environments.md](environments.md) <!-- pathref: docs/rules/environments.md -->。
- 策略参数集中定义，避免魔法数字。
- `initialize` 负责集中配置与注册，`handle_data` 或 `run_daily` 实现调仓。
- 策略改动必须通过语法检查；涉及测试覆盖的模块必须运行对应 pytest。
- 研究结论写入分析文档，不用代码注释承载结论。

## 环境兼容约束

策略代码运行于聚宽 Python 3.6，以下特性**禁止使用**：

| 禁止 | 原因 |
| --- | --- |
| `f"{x=}"` 调试格式 | Python 3.8+ |
| `X \| Y` 类型联合 | Python 3.10+ |
| `match/case` | Python 3.10+ |
| `list[float]` 泛型注解 | Python 3.9+（用 `from typing import List`） |
| `pd.DataFrame.groupby(dropna=)` | 聚宽 pandas 版本不支持此参数 |
| `import matplotlib`（策略内） | 回测环境无图形显示 |
| `import cvxpy`（策略内） | 不在聚宽白名单 |

可用库白名单：numpy、pandas、scipy、statsmodels、scikit-learn、ta、talib。完整对照见 [environments.md](environments.md) <!-- pathref: docs/rules/environments.md -->。

本地测试环境（Python 3.12 + 新版本库）写策略时需注意：

- 允许使用新版 API，但上传前用 `jq-auto compile-check` 验证语法兼容性
- 策略中 `get_price()`、`order_target_value()` 等聚宽 API 在本地不存在，测试时需 mock
- 策略间共享代码放聚宽研究根目录，策略中用 `from xxx import yyy` 导入

## SHOULD

- 注释解释“为什么”，不要逐行翻译代码。
- 优先批量向量化，先筛选后计算。
- 明确处理停牌、缺失值、仓位上下限和风控参数。

## MAY

- 窄范围修复可只补最小测试；共享行为、跨模块契约或用户可见流程应扩大测试覆盖。
