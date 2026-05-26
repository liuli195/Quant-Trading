# 研究工具注册表

`registry/` 保存本地研究平台的正式工具清单。它只负责登记、发现和校验，不承载业务逻辑。

## 命令

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry list
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry list --group-by-library
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry list --group-by-layer
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry list --format markdown
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry validate
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry write-layers
```

## 登记字段

- `tool_id`：稳定工具 ID。
- `library`：所属库，例如 `scripts.research.research_core` 或 `scripts.tools.jq_automation`。
- `layer`：所属架构层。
- `kind`：`cli`、`library`、`workflow_template` 或 `automation`。
- `entry_module` / `cli`：Python 模块和可选命令入口。
- `readme_path` / `docs_path` / `tests`：治理审计使用的文档和测试锚点。
- `inputs` / `outputs`：工具输入输出摘要。
- `owner` / `lifecycle` / `permissions`：治理责任、生命周期和允许写入来源。

## 管理规则

- 新正式 CLI 必须登记。
- 新库级工具至少登记到所属库。
- CLI 元数据必须使用 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m ...`。
- 每个登记项必须有 owner 和 lifecycle。
- 治理审计会扫描未登记 CLI，并按 registry 自动执行 `--help` 检查。
- [layers](../layers) <!-- pathref: scripts/research/layers --> 是 registry 生成的5层工具索引，缺失或过期会被治理审计拦截。
