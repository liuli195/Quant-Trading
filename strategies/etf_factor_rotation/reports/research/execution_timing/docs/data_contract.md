# 数据契约

## 必要输入

| 输入 | 用途 |
|---|---|
| 带 `open / close / high / low / money` 的日频行情包 | 计算开盘成交延迟与三组近似路径 |
| baseline `audit_log.jsonl` | 读取正式信号、参数和目标权重 |

## 当前状态

- 执行时序行情包已刷新为 `open / close / high / low / money`
- baseline 最终权重本地复算已通过校准，可继续解释 `signal_shift`
- 后续重跑仍必须保留 `open`
