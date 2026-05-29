.PHONY: verify-fast verify-full pre-pr ai-review risk-check pr-ready pr-diagnose

ifeq ($(OS),Windows_NT)
PYTHON ?= ./.venv/Scripts/python.exe
else
PYTHON ?= ./.venv/bin/python
endif
PRE_COMMIT := $(PYTHON) -m pre_commit
AI_REVIEW_REPORT := .local/ai-review/latest.json
PY_CHECK_PATHS := scripts/research/governance
PYTEST_PATHS := scripts/research/governance/tests
BANDIT_SKIP := B310,B404,B603,B607
MYPY_FLAGS := --explicit-package-bases --follow-imports=skip --ignore-missing-imports

verify-fast:
	$(PYTHON) -m scripts.research.governance verify fast --staged

verify-full:
	$(PYTHON) -m scripts.research.governance verify full

pre-pr:
	$(PRE_COMMIT) run --all-files
	$(MAKE) verify-full

ai-review:
	$(PYTHON) -m scripts.research.governance.ai_review_gate validate --report $(AI_REVIEW_REPORT)
	$(PYTHON) -m scripts.research.governance.ai_review_gate markdown --report $(AI_REVIEW_REPORT) --output .local/ai-review/latest.md
	$(PYTHON) -m scripts.research.governance.ai_review_gate scope --report $(AI_REVIEW_REPORT) --output .local/ai-review/codex-review-scope.md

risk-check:
	$(PYTHON) -m scripts.research.governance.ai_review_gate risk --report $(AI_REVIEW_REPORT)

pr-ready:
	$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)"

pr-diagnose:
	$(PYTHON) -m scripts.research.governance.pr_flow diagnose $(if $(PR),--pr "$(PR)",)
