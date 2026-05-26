# 第二层：数据中心

本地不可变数据集、快照、目录和数据导入。

本页由工具注册表生成，不手工维护。

| tool_id | owner | lifecycle | library | kind | entry_module | cli | README | tests | inputs | outputs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `research.datasets` | research-platform | active | `scripts.research` | `cli` | `scripts.research.datasets` | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\.githooks\run-python.ps1 -m scripts.research.datasets` | `scripts/research/README.md` | `scripts/research/platform/tests/test_platform.py` | `JoinQuant price JSON`<br>`audit_log.jsonl`<br>`backtest_runs/<run_id>` | `research_datasets/<dataset_id>/<snapshot_id>`<br>`catalog.json`<br>`catalog.md` |
