# 命令和本地环境规则

本文件承接 AI 入口中的命令细节。通用入口见 [AGENTS.md](../../AGENTS.md) <!-- pathref: repo/AGENTS.md -->。

## MUST

- Windows 本地 Python 命令必须使用 `.\.venv\Scripts\python.exe`。
- Codex Cloud/Linux 使用 `.venv/bin/python`。
- Git hook 和自动化入口统一通过 `.githooks/run-python.sh` 选择当前平台的项目虚拟环境。

## 常用命令

```powershell
# 语法检查
.\.venv\Scripts\python.exe -m py_compile strategies\<strategy>\<strategy>.py

# 单元测试
.\.venv\Scripts\python.exe -m pytest strategies\<strategy>\tests -q

# 云端回测，完整参考 scripts/tools/jq_automation/README.md
.\.venv\Scripts\python.exe -m scripts.tools.jq_automation compile-check|upload|run|fetch|batch|ab

# 路径引用校验
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check

# 本地研究
.\.venv\Scripts\python.exe -m scripts.research.cli init|run|promote|resume|handoff-cloud|status

# 数据中心
.\.venv\Scripts\python.exe -m scripts.research.datasets import-price-json|import-audit-log|import-backtest-run|inspect

# 文档报告索引
.\.venv\Scripts\python.exe -m scripts.research.docs index

# 策略变体登记、快照和 Git 计划
.\.venv\Scripts\python.exe -m scripts.research.variants list|register|materialize|branch-plan|branch-create|merge-plan|merge-apply

# 中央工具注册与治理审计
.\.venv\Scripts\python.exe -m scripts.research.registry.tool_registry list|validate
.\.venv\Scripts\python.exe -m scripts.research.governance audit
.\.venv\Scripts\python.exe -m scripts.research.governance gate

# 启用本地治理 hooks
git config core.hooksPath .githooks
```

## 参考文档

- [jq_automation/README.md](../../scripts/tools/jq_automation/README.md) <!-- pathref: scripts/tools/jq_automation/README.md -->
- [path_tools/README.md](../../scripts/tools/path_tools/README.md) <!-- pathref: scripts/tools/path_tools/README.md -->
- [research-workflow.md](../guides/research-workflow.md) <!-- pathref: docs/guides/research-workflow.md -->
