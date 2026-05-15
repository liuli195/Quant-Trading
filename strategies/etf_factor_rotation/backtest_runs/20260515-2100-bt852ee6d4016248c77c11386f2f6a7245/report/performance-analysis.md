# 性能分析报告 — AI-baseline (CrowdStart=0.60)

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 变体名称：ai-baseline
- 是否启用 `enable_profile()`：是
- 数据来源：JoinQuant 云端回测
- Run ID：`20260515-2100-bt852ee6d4016248c77c11386f2f6a7245`

## 2. 主要耗时函数

（需从 profile.md 中解析）

# 性能分析

## fund_code

- 总耗时：0.009919s

```text
Total time: 0.009919 s
File: /tmp/strategy/user_code.py
Function: fund_code at line 39
```

## format_etf_name

- 总耗时：0.065683s

```text
Total time: 0.065683 s
File: /tmp/strategy/user_code.py
Function: format_etf_name at line 41
```

## build_etf_display_names

- 总耗时：0.128013s

```text
Total time: 0.128013 s
File: /tmp/strategy/user_code.py
Function: build_etf_display_names at line 54
```

## fetch_etf_official_name

- 总耗时：0s

```text
Total time: 0

## 3. 热点路径解读

见上方 profile 数据。

## 4. 优化建议

见 profile 数据分析。