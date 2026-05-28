# 第三层：流程编排层

研究项目生命周期、流程模板、插件调度和聚宽自动化。

本页由工具注册表生成，不手工维护。

| tool_id | owner | lifecycle | library | kind | entry_module | cli_windows | cli_posix | README | tests | inputs | outputs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `research.cli` | research-platform | active | `scripts.research` | `cli` | `scripts.research.cli` | `.\.venv\Scripts\python.exe -m scripts.research.cli` | `.venv/bin/python -m scripts.research.cli` | `scripts/research/README.md` | `scripts/research/platform/tests/test_platform.py` | `project.json`<br>`dataset snapshots`<br>`raw research exports` | `runs/<run_id>/manifest.json`<br>`candidate funnel tables`<br>`cloud_handoff.json` |
| `research.platform.plugins` | research-platform | active | `scripts.research.platform` | `library` | `scripts.research.platform.plugins` | `` | `` | `scripts/research/platform/README.md` | `scripts/research/platform/tests/test_platform.py` | `project.json`<br>`ResearchRunContext`<br>`feature bundles` | `fast/full result tables`<br>`cloud handoff payloads` |
| `research.workflow_templates` | research-platform | active | `scripts.research.workflows` | `workflow_template` | `scripts.research.platform.workflows` | `` | `` | `scripts/research/workflows/README.md` | `scripts/research/platform/tests/test_platform.py` | `scripts/research/workflows/templates/*.json` | `validated WorkflowTemplate objects` |
| `tools.jq_automation` | research-platform | active | `scripts.tools.jq_automation` | `cli` | `scripts.tools.jq_automation` | `.\.venv\Scripts\python.exe -m scripts.tools.jq_automation` | `.venv/bin/python -m scripts.tools.jq_automation` | `scripts/tools/jq_automation/README.md` | `scripts/tools/jq_automation/tests/test_core.py`<br>`scripts/tools/jq_automation/tests/test_ab.py` | `scenario.json`<br>`AB config`<br>`browser profile`<br>`JoinQuant run pages` | `backtest_runs/<run_id>`<br>`test_batches/<batch_id>`<br>`research_datasets snapshots` |
