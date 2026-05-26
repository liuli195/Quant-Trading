# 第一层：策略库

策略结构、变体定义、物化和合并计划。

本页由工具注册表生成，不手工维护。

| tool_id | owner | lifecycle | library | kind | entry_module | cli | README | tests | inputs | outputs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `research.strategy_variants` | research-platform | active | `scripts.research` | `cli` | `scripts.research.variants` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.variants` | `scripts/research/platform/README.md` | `scripts/research/platform/tests/test_platform.py` | `strategy.json`<br>`variants/<variant_id>.json` | `variants/variants.json`<br>`.local/research-materialized` |
