# jq_automation A/B 测试能力方案设计

## Why
为 scripts/tools/jq_automation 增加声明式 A/B 测试能力：用户通过实验配置声明 baseline、controls、variants 和参数差异，工具在一次聚宽上传会话中顺序覆盖上传、编译、回测、抓取结果，生成 A/B 对比报告。

## What Changes
- 支持同一策略的参数 A/B 和 Git 管理的代码版本 A/B
- 支持多个对照版本（baseline + controls）
- 支持参数扫描后确认组合的工作流
- 新增 ab expand/run/report CLI 子命令
- 新增 manifest ab_experiments 扩展
- 新增 abtest.py、git_versioning.py、metrics.py 模块

## Impact
v1 定位为"可复现的回测变体对比工具"，首要交付物是对比报告。不自动改策略、不自动筛参、不并行启动回测。本地用 uploaded_code_sha256 绑定候选项与云端回测记录。

---
source: docs/design/AB_TEST_DESIGN.md
