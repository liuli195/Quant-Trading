# 性能分析报告 — AI-calc-longwin (延长计算窗口)

## 1. 性能分析概览

- 策略名称：etf_factor_rotation
- 变体名称：ai-calc-longwin
- 是否启用 `enable_profile()`：是
- 数据来源：JoinQuant 云端回测
- Run ID：`20260515-2107-bt157c5e16bdd7a47cb327a70b75b69da4`

## 2. 主要耗时函数

（需从 profile.md 中解析）

# 性能分析

## fund_code

- 总耗时：0.010088s

```text
Total time: 0.010088 s
File: /tmp/strategy/user_code.py
Function: fund_code at line 39
```

## format_etf_name

- 总耗时：0.066027s

```text
Total time: 0.066027 s
File: /tmp/strategy/user_code.py
Function: format_etf_name at line 41
```

## build_etf_display_names

- 总耗时：0.127326s

```text
Total time: 0.127326 s
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