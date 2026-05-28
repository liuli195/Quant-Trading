# 第五层：文档报告库

报告、索引、证据链接和文档产出。

本页由工具注册表生成，不手工维护。

| tool_id | owner | lifecycle | library | kind | entry_module | cli_windows | cli_posix | README | tests | inputs | outputs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `research.docs_index` | research-platform | active | `scripts.research` | `cli` | `scripts.research.docs` | `.\.venv\Scripts\python.exe -m scripts.research.docs` | `.venv/bin/python -m scripts.research.docs` | `scripts/research/platform/README.md` | `scripts/research/platform/tests/test_platform.py` | `Markdown reports`<br>`pathref comments` | `docs/indexes/docs_catalog.json`<br>`docs/indexes/reports_catalog.json`<br>`docs/indexes/datasets_catalog.json`<br>`docs/indexes/variants_catalog.json` |
