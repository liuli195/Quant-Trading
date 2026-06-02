.PHONY: verify-fast verify-full pre-pr pr-submit pr-resolve-threads

ifeq ($(OS),Windows_NT)
PYTHON ?= ./.venv/Scripts/python.exe
else
PYTHON ?= ./.venv/bin/python
endif
PRE_COMMIT := $(PYTHON) -m pre_commit
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

pr-submit:
	$(PYTHON) -m scripts.research.governance.pr_flow submit --title "$(TITLE)" $(if $(PR),--pr "$(PR)",)

pr-resolve-threads:
	$(PYTHON) -m scripts.research.governance.pr_flow resolve-threads $(THREADS)
