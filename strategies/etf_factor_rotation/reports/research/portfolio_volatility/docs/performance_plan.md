# 性能计划

- `fast` 负责 cold/warm 冒烟
- `full` 目标耗时门槛：`60s`
- warm smoke 必须命中特征缓存
- 预计 full 耗时超过门槛时，先优化再继续
