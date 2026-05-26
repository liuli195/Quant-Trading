# 本地与聚宽环境差异

策略代码运行于聚宽云端（回测/模拟），本地仅负责编写、测试、分析。

## 环境速览

| | 本地 .venv | 回测 | 模拟交易 | 研究 |
| --- | --- | --- | --- | --- |
| Python | 3.12 | 3.6 | 3.6 | 3.6 |
| numpy/pandas | 最新 | 旧版 | 旧版 | 旧版 |
| scipy | ✅ | ✅ | ✅ | ✅ |
| statsmodels | ✅ | ✅ | ✅ | ✅ |
| cvxpy | ✅ | ❌ | ❌ | ⚠️ 手动安装 |
| matplotlib/seaborn | ✅ | ❌ | ❌ | ✅ |
| jqdata API | ❌ | ✅ | ✅ | ✅ |
| 网络请求 | ✅ | ❌ | ❌ | ✅ |
| 文件系统 | ✅ 完整 | ⚠️ 仅研究目录 | ⚠️ 仅研究目录 | ✅ |

## 库白名单

策略代码（回测/模拟）中可用的第三方库：

| 库 | 回测 | 模拟 | 研究 |
| --- | --- | --- | --- |
| numpy | ✅ | ✅ | ✅ |
| pandas | ✅ | ✅ | ✅ |
| scipy | ✅ | ✅ | ✅ |
| statsmodels | ✅ | ✅ | ✅ |
| scikit-learn | ✅ | ✅ | ✅ |
| ta / talib | ✅ | ✅ | ✅ |
| matplotlib | ❌ | ❌ | ✅ |
| seaborn | ❌ | ❌ | ✅ |
| cvxpy | ❌ | ❌ | ⚠️ |

研究环境可通过 `!pip install --target=...` 手动安装额外库，但文件数不得超 10000。

## 语法约束

策略代码运行于 Python 3.6，以下特性**禁止**：

| 禁止 | 替代方案 |
| --- | --- |
| `f"{x=}"` | `f"x={x}"` |
| `X \| Y` | `from typing import Union` |
| `match/case` | `if/elif/else` |
| `list[float]` | `from typing import List` |

## 开发经验

**写策略时**：
- 本地测试需要 mock 聚宽 API（`get_price`、`order_target_value` 等）
- 上传前运行 `jq-auto compile-check` 验证语法兼容
- 策略间共享代码放聚宽研究根目录，用 `import xxx` 导入

**做分析时**：
- 重型计算（cvxpy 优化、回归归因）放研究 Notebook 或本地
- 计算结果存为文件上传到研究，策略用 `read_file()` 读取
- 研究环境安装额外库：`!pip install 库名 --target="/home/jquser/目录"`

**本地便利**：
- 本地 numpy/pandas 版本远高于聚宽，避免使用聚宽不支持的新 API 参数
- 本地有完整 pyarrow、playwright 等工具链，聚宽没有
