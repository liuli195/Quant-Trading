# 执行计划

1. 刷新带 `open` 的行情导出
2. 先让 baseline 本地复算通过校准
3. 运行 `signal_shift`
4. 运行 `delay_only`
5. 生成三组近似收益路径
6. 根据本地阈值决定是否进入云端 A/B
