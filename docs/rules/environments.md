# 本地与聚宽环境差异

策略代码只在聚宽回测/模拟运行；本地负责开发、测试、文档和分析。

## 环境

| 项 | 本地 `.venv` | 回测/模拟 | 聚宽研究 |
| --- | --- | --- | --- |
| Python | 3.12 | 3.6 | 3.6 |
| 数据 API | 无 `jqdata` | 有 | 有 |
| 网络 | 可用 | 不可用 | 可用 |
| 文件系统 | 完整 | 受限 | 可用 |
| 本地依赖保证 | `requirements.txt` | 不适用 | 不适用 |
| 可选分析库 | `scipy`、`statsmodels`、`scikit-learn`、`matplotlib`、`seaborn`、`cvxpy` 仅在已安装时可用 | 不保证 | 可手动安装，文件数不得超 10000 |

## 策略代码

- 必须兼容聚宽 Python 3.6 和旧版 `numpy/pandas`。
- 禁用 `f"{x=}"`、`X | Y`、`match/case`、`list[float]`。
- 禁用聚宽旧版 pandas 不支持的新参数，例如 `groupby(dropna=...)`。
- 策略内不得依赖 `matplotlib`、`seaborn`、`cvxpy`、网络请求或本地文件系统完整权限。
- 本地测试需 mock `get_price`、`order_target_value` 等聚宽 API。
- 上传前用 `scripts.tools.jq_automation compile-check` 做兼容检查。

## 分工

- 重型计算、回归、优化、画图放本地或聚宽研究。
- 研究结果可落文件；策略用聚宽支持的读文件方式消费。
- 策略间共享代码放聚宽研究根目录，并用聚宽可解析的导入方式。
