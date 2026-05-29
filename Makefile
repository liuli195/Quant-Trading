.PHONY: verify-fast verify-full pre-pr ai-review risk-check pr-ready pr-diagnose pr-resolve-threads pr-ready-for-review pr-merge pr-cleanup pr-complete

ifeq ($(OS),Windows_NT)
PYTHON ?= ./.venv/Scripts/python.exe
else
PYTHON ?= ./.venv/bin/python
endif
PRE_COMMIT := $(PYTHON) -m pre_commit
AI_REVIEW_REPORT := .local/ai-review/latest.json
THREAD_FLAGS := $(foreach thread,$(THREADS),--resolve-thread "$(thread)")
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
	$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)" $(THREAD_FLAGS)

pr-diagnose:
	$(PYTHON) -m scripts.research.governance.pr_flow diagnose $(if $(PR),--pr "$(PR)",)

pr-resolve-threads:
	$(PYTHON) -m scripts.research.governance.pr_flow resolve-threads $(THREADS)

pr-ready-for-review:
	$(PYTHON) -m scripts.research.governance.pr_flow ready-for-review $(if $(PR),--pr "$(PR)",)

pr-merge:
	$(PYTHON) -m scripts.research.governance.pr_flow merge $(if $(PR),--pr "$(PR)",)

pr-cleanup:
	$(PYTHON) -m scripts.research.governance.pr_flow cleanup $(if $(PR),--pr "$(PR)",)

pr-complete:
	$(PYTHON) -m scripts.research.governance.pr_flow complete --title "$(TITLE)" $(if $(PR),--pr "$(PR)",) $(THREAD_FLAGS)
