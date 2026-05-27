.PHONY: pre-pr ai-review risk-check pr-ready

ifeq ($(OS),Windows_NT)
PYTHON ?= powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./.githooks/run-python.ps1
else
PYTHON ?= sh .githooks/run-python.sh
endif
PRE_COMMIT := $(PYTHON) -m pre_commit
AI_REVIEW_REPORT := .local/ai-review/latest.json
PY_CHECK_PATHS := scripts/research/governance
PYTEST_PATHS := scripts/research/governance/tests
BANDIT_SKIP := B310,B404,B603,B607
MYPY_FLAGS := --explicit-package-bases --follow-imports=skip --ignore-missing-imports

pre-pr:
	$(PRE_COMMIT) run --all-files
	$(PYTHON) -m ruff check $(PY_CHECK_PATHS)
	$(PYTHON) -m bandit -q -r $(PY_CHECK_PATHS) -x $(PY_CHECK_PATHS)/tests -s $(BANDIT_SKIP)
	$(PYTHON) -m mypy $(MYPY_FLAGS) $(PY_CHECK_PATHS)
	$(PYTHON) -m pip_audit
	$(PYTHON) -m pytest $(PYTEST_PATHS)
	$(PYTHON) -m scripts.tools.path_tools.refactor check
	$(PYTHON) -m scripts.research.governance gate

ai-review:
	$(PYTHON) -m scripts.research.governance.ai_review_gate validate --report $(AI_REVIEW_REPORT)
	$(PYTHON) -m scripts.research.governance.ai_review_gate markdown --report $(AI_REVIEW_REPORT) --output .local/ai-review/latest.md
	$(PYTHON) -m scripts.research.governance.ai_review_gate scope --report $(AI_REVIEW_REPORT) --output .local/ai-review/codex-review-scope.md

risk-check:
	$(PYTHON) -m scripts.research.governance.ai_review_gate risk --report $(AI_REVIEW_REPORT)

pr-ready:
	$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)"
