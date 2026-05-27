# 横向治理：注册与审计

跨层注册、审计、路径引用和提交门禁。

本页由工具注册表生成，不手工维护。

| tool_id | owner | lifecycle | library | kind | entry_module | cli_windows | cli_posix | README | tests | inputs | outputs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `research.governance` | research-platform | active | `scripts.research.governance` | `cli` | `scripts.research.governance` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.governance audit` | `.githooks/run-python.sh -m scripts.research.governance audit` | `scripts/research/governance/README.md` | `scripts/research/governance/tests/test_governance.py` | `tool registry`<br>`CLAUDE.md`<br>`.claude/skills`<br>`catalogs` | `audit result JSON/stdout`<br>`gate result JSON/stdout` |
| `research.registry` | research-platform | active | `scripts.research.registry` | `cli` | `scripts.research.registry.tool_registry` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry` | `.githooks/run-python.sh -m scripts.research.registry.tool_registry` | `scripts/research/registry/README.md` | `scripts/research/registry/tests/test_registry.py` | `ToolDefinition entries` | `registry validation report` |
| `tools.path_tools.aliases` | research-platform | active | `scripts.tools.path_tools` | `cli` | `scripts.tools.path_tools.aliases` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.path_tools.aliases` | `.githooks/run-python.sh -m scripts.tools.path_tools.aliases` | `scripts/tools/path_tools/README.md` | `scripts/research/governance/tests/test_governance.py` | `path_aliases.json`<br>`alias variables` | `resolved repository paths` |
| `tools.path_tools.refactor` | research-platform | active | `scripts.tools.path_tools` | `cli` | `scripts.tools.path_tools.refactor` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor` | `.githooks/run-python.sh -m scripts.tools.path_tools.refactor` | `scripts/tools/path_tools/README.md` | `scripts/research/governance/tests/test_governance.py` | `Markdown pathrefs`<br>`move maps` | `pathref validation result`<br>`rewritten references` |
