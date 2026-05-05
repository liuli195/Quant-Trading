# JQ Fix 流程

## 步骤

1. 读取证据：编译错误、`tabs_raw/logs.md`、分析报告、pytest 输出或批次 `issue-log.md`。
2. 定位最小修复范围。
3. 只修改相关策略、测试或文档。
4. 执行：

```bash
python -m py_compile <strategy_file>
```

5. 有测试目录时运行相关 pytest。
6. 批次问题修复后，更新 `issue-log.md`。

## 状态

批次问题建议使用：

- `needs_fix`
- `fixed_local`
- `needs_cloud_verification`
- `closed_local_only`

不要调用 `jq-run`，只建议最小云端验证场景。
