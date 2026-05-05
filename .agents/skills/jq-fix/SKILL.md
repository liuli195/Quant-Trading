---
name: jq-fix
description: 根据 JoinQuant 编译错误、回测日志、分析报告、pytest 失败或批次 issue-log 修复本地 Python 策略。用于修改策略代码、测试或本地文档，并执行本地验证。该技能不得启动 JoinQuant 云端回测。
---

# JQ Fix

只做本地修复：定位问题、改代码、跑本地检查、标记需云端验证的场景。

## 使用

1. 先读 [references/workflow.md](references/workflow.md) <!-- pathref: agents_jq_fix_skill/references/workflow.md -->。
2. 从编译错误、`tabs_raw/logs.md`、分析报告、测试输出或 `issue-log.md` 收集证据。
3. 只修改相关本地文件。
4. 运行 `py_compile` 和相关 pytest。

## 边界

- 不上传策略，不跑云端回测。
- 不改写已保存的原始回测数据。
- 需要云端复验时，把场景标记为 `needs_cloud_verification`。
- 最后只建议最小的 `jq-run` 验证场景。
