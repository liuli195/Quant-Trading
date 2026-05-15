# 性能分析报告 — AI-start-075 (CrowdStart=0.75)

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 变体名称：ai-start-075
- 是否启用 `enable_profile()`：是
- 数据来源：JoinQuant 云端回测
- Run ID：`20260515-2102-bt5d8807c600e004cf70f4c4b31a1b28ac`

## 2. 主要耗时函数

（需从 profile.md 中解析）

# 性能分析

## fund_code

- 总耗时：0.00998s

```text
Total time: 0.00998 s
File: /tmp/strategy/user_code.py
Function: fund_code at line 39
```

## format_etf_name

- 总耗时：0.06681s

```text
Total time: 0.06681 s
File: /tmp/strategy/user_code.py
Function: format_etf_name at line 41
```

## build_etf_display_names

- 总耗时：0.129248s

```text
Total time: 0.129248 s
File: /tmp/strategy/user_code.py
Function: build_etf_display_names at line 54
```

## fetch_etf_official_name

- 总耗时：0s

```text
Total time: 0 s
F

## 3. 热点路径解读

见上方 profile 数据。

## 4. 优化建议

见 profile 数据分析。