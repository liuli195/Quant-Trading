# 回测 run 快照字段

| 视图 | 说明 |
| --- | --- |
| `raw/source.json.gz` | 原始 run 文件清单与哈希 |
| `raw/*.gz` | 压缩保存的原始回测文件 |
| `data/data.parquet` | 累计收益序列主存储 |
| `data/audit_events.parquet` | 审计事件主存储 |
| `views/sample.csv` | 收益序列小样本 |
| `views/profile.json` | 行数、日期范围、审计日志和报告文件摘要 |
