# PR Flow Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fast, explicit PR automation flow that minimizes manual PR evidence work without moving slow or judgment-heavy steps into Git hooks.

**Architecture:** Keep Git hooks focused on deterministic local safeguards. Add a Python `pr_flow` orchestrator for PR preparation, GitHub synchronization, and check waiting. Extend the existing AI review gate so scripts can draft and render PR evidence from structured review JSON while skills/agents still own judgment.

**Tech Stack:** Python 3.12, pytest, existing `.githooks/run-python.ps1` and `.githooks/run-python.sh` wrappers, Git CLI, GitHub CLI `gh`, Makefile, existing governance modules.

---

## Current State

- Hook layer:
  - `.githooks/pre-commit` runs `pre-commit` and full `scripts.research.governance gate`.
  - `.githooks/pre-push` runs branch protection, full governance gate, then Git LFS handoff.
  - `.githooks/reference-transaction` blocks unsafe local `main` / `master` ref updates.
- Script layer:
  - `Makefile` exposes `pre-pr`, `ai-review`, and `risk-check`.
  - `scripts.research.governance.ai_review_gate` validates `.local/ai-review/latest.json`, renders `.local/ai-review/latest.md`, and renders `.local/ai-review/codex-review-scope.md`.
  - `scripts.research.governance.pr_review_evidence` validates GitHub PR body evidence in CI.
- Manual friction still present:
  - Humans must assemble `.local/ai-review/latest.json`.
  - Humans must copy PR body evidence into the PR template.
  - Humans must create/update PR, labels, `@codex review` trigger comments, and check waiting manually.

## Target Flow

Primary local command:

```powershell
.\.githooks\run-python.ps1 -m scripts.research.governance.pr_flow ready --title "<PR标题>"
```

Equivalent Makefile wrapper:

```powershell
make pr-ready TITLE="<PR标题>"
```

`ready` runs:

1. `prepare`: detect changed files, draft local review JSON, run selected local checks, render PR body evidence.
2. `sync`: create or update a draft PR with `gh`, update a machine-managed PR body block, sync `ai-risk-review` label, and post a compliant `@codex review` comment when required.
3. `wait`: wait for required checks and summarize failures.

## Task 1: Fast Governance Gate

**Files:**
- Modify: `scripts/research/governance/gate.py`
- Modify: `scripts/research/governance/__main__.py`
- Modify: `scripts/research/governance/rules.py`
- Modify: `.githooks/pre-commit`
- Test: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: Add a failing test for fast gate CLI forwarding**

Add a test proving the legacy fast-gate command is accepted and forwards a mode that skips slow checks.

Expected behavior:

```text
legacy fast-gate:
- runs governance audit
- skips CLI help
- skips pathref gate
- returns nonzero on governance audit errors
```

- [ ] **Step 2: Add a failing audit test for fast pre-commit**

Update governance tests so `.githooks/pre-commit` may call:

```sh
sh .githooks/run-python.sh -m scripts.research.governance <legacy-fast-gate>
```

while `.githooks/pre-push` must still call full:

```sh
sh .githooks/run-python.sh -m scripts.research.governance gate
```

- [ ] **Step 3: Implement legacy fast mode in gate parser**

Add the legacy fast mode to `gate.py` and `__main__.py`.

Fast mode must call the same audit surface but skip:

- CLI help checks.
- pathref gate.

Full mode must keep current behavior.

- [ ] **Step 4: Update pre-commit hook**

Change `.githooks/pre-commit` to run:

```sh
sh .githooks/run-python.sh \
  -m scripts.research.governance <legacy-fast-gate>
```

Do not change `pre-push` behavior.

- [ ] **Step 5: Verify Task 1**

Run:

```powershell
.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests\test_governance.py -q
```

Expected: all governance tests pass.

## Task 2: AI Review Draft and PR Body Rendering

**Files:**
- Modify: `scripts/research/governance/ai_review_gate.py`
- Test: `scripts/research/governance/tests/test_ai_review_gate.py`

- [ ] **Step 1: Add failing tests for `draft`**

Add tests for:

```powershell
.\.githooks\run-python.ps1 -m scripts.research.governance.ai_review_gate draft --output .local/ai-review/latest.draft.json
```

Expected draft JSON:

```json
{
  "schema_version": 2,
  "tool": "codex",
  "review_mode": "complete",
  "risk_level": "high",
  "requires_official_codex_review": true,
  "changed_files": ["scripts/research/governance/ai_review_gate.py"],
  "findings": [],
  "checks": {}
}
```

Risk defaults:

- `high` if any changed file matches existing high-risk prefixes.
- `low` for docs-only changes outside high-risk docs.
- `unknown` if changed files cannot be detected.

- [ ] **Step 2: Add failing tests for `pr-body`**

Add tests proving:

```powershell
.\.githooks\run-python.ps1 -m scripts.research.governance.ai_review_gate pr-body --report .local/ai-review/latest.json --output .local/ai-review/pr-body.md
```

renders sections accepted by `pr_review_evidence.validate_pr_body()`.

Required rendered sections:

- `## AI Review 风险分级`
- `## P2 保留项`
- `## Codex Code Review 结论` only when official Codex review is required and already has evidence.

- [ ] **Step 3: Implement changed-file discovery**

Use Git CLI from Python:

```text
git diff --name-only --cached
git diff --name-only
```

Merge both lists, normalize to forward-slash repo-relative paths, deduplicate, and sort.

- [ ] **Step 4: Implement `draft` command**

The draft command writes JSON with stable defaults and never claims review completion.

It must not create fake values for:

- `security_review`
- `cross_review`
- `complete_review`
- findings

- [ ] **Step 5: Implement `pr-body` command**

Render PR evidence from validated report data.

Rules:

- Preserve `utf-8-sig` JSON reading.
- Use provider/tool mapping already enforced by `ai_review_gate`.
- Render P2 accepted findings with `defer_reason`, `risk_acceptance`, and `handling`.
- Render official review skip authorization when present.
- Do not invent a Codex review link.

- [ ] **Step 6: Verify Task 2**

Run:

```powershell
.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests\test_ai_review_gate.py -q
```

Expected: all AI review gate tests pass.

## Task 3: PR Flow Orchestrator

**Files:**
- Create: `scripts/research/governance/pr_flow.py`
- Test: `scripts/research/governance/tests/test_pr_flow.py`

- [ ] **Step 1: Add tests for diff-aware local check selection**

Expected mapping:

| Changed files | Selected checks |
| --- | --- |
| `docs/guides/a.md` | `governance-fast`, `pathref` |
| `scripts/research/governance/rules.py` | `ruff-governance`, `bandit-governance`, `mypy-governance`, `pytest-governance`, `governance-full` |
| `strategies/demo/demo.py` | `py-compile-strategy`, `pytest-strategy-if-present`, `governance-full` |
| `requirements.txt` | `pip-audit`, `governance-full` |

- [ ] **Step 2: Add tests for GitHub CLI command construction**

Mock subprocess calls and assert:

- Existing PR is discovered with `gh pr view --json number,url,state,isDraft`.
- Missing PR is created with `gh pr create --draft`.
- Existing PR body is updated with `gh pr edit --body-file`.
- `ai-risk-review` label is added for high/unknown risk.
- `@codex review` comment is posted only when required.

- [ ] **Step 3: Implement command runner abstraction**

Create a small internal runner so tests can inject fake command results.

Return shape:

```python
@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
```

- [ ] **Step 4: Implement `prepare`**

`prepare` must:

- discover changed files
- run selected local checks
- create `.local/ai-review/latest.draft.json` if `.local/ai-review/latest.json` is missing
- validate `.local/ai-review/latest.json` when present
- render `.local/ai-review/latest.md`
- render `.local/ai-review/codex-review-scope.md`
- render `.local/ai-review/pr-body.md`

- [ ] **Step 5: Implement `sync`**

`sync` must:

- require `--title` when no PR exists
- use current branch as PR head
- create draft PR by default
- update only a machine-managed block in PR body:

```markdown
<!-- pr-flow:start -->
...
<!-- pr-flow:end -->
```

- sync `ai-risk-review` label for high/unknown
- post the exact compliant Codex trigger when required:

```markdown
@codex review

PR：<pr-url>
HEAD：<head-sha>
Review Scope：
<contents of .local/ai-review/codex-review-scope.md>

审查重点：仅 P0/P1 合并阻断风险
```

- [ ] **Step 6: Implement `wait`**

`wait` must call:

```text
gh pr checks <PR> --required --watch --interval 10
```

On failure, run:

```text
gh pr checks <PR> --required
```

and print the failing check names.

- [ ] **Step 7: Implement `ready`**

`ready` runs `prepare`, then `sync`, then `wait`.

If any stage fails, stop immediately and return that exit code.

- [ ] **Step 8: Verify Task 3**

Run:

```powershell
.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests\test_pr_flow.py -q
```

Expected: all PR flow tests pass without writing GitHub.

## Task 4: Entrypoints and Governance Registration

**Files:**
- Modify: `Makefile`
- Modify: `scripts/research/registry/tool_registry.py`
- Modify: `scripts/research/governance/rules.py`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: Add Makefile wrapper**

Add:

```makefile
pr-ready:
	$(PYTHON) -m scripts.research.governance.pr_flow ready --title "$(TITLE)"
```

Keep existing `pre-pr`, `ai-review`, and `risk-check` for compatibility.

- [ ] **Step 2: Register the CLI**

Add `scripts.research.governance.pr_flow` to the repo tool registry using the existing registry pattern.

- [ ] **Step 3: Update governance audit tokens**

Governance should require:

- `pr-ready` in `Makefile`.
- `scripts.research.governance.pr_flow` registered.
- `.github/pull_request_template.md` contains `pr-flow:start`.
- `.githooks/pre-commit` uses fast gate.
- `.githooks/pre-push` uses full gate.

- [ ] **Step 4: Regenerate generated registry docs**

Run the existing registry layer writer if registry changes require generated docs updates:

```powershell
.\.githooks\run-python.ps1 -m scripts.research.registry.tool_registry write-layers
```

- [ ] **Step 5: Verify Task 4**

Run:

```powershell
.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests\test_governance.py -q
```

Expected: governance tests pass.

## Task 5: Template and Rule Documentation

**Files:**
- Modify: `.github/pull_request_template.md`
- Modify: `docs/rules/pr-workflow.md`
- Modify: `docs/rules/review-guidelines.md`
- Modify: `docs/rules/governance.md`

- [ ] **Step 1: Simplify PR template**

Replace manual evidence-heavy content with:

```markdown
## 改动目标

-

## 影响范围

-

<!-- pr-flow:start -->
运行 `make pr-ready TITLE="<PR标题>"` 后由脚本更新本区块。
<!-- pr-flow:end -->

## 人工补充

- 额外证据链接：
- waiver：
```

- [ ] **Step 2: Update workflow rule docs**

`docs/rules/pr-workflow.md` should state:

- Hooks guard local invariants.
- `pr_flow` handles PR preparation and GitHub synchronization.
- Skills/agents produce review judgments.
- Rule docs are fallback, not the main execution surface.

- [ ] **Step 3: Update review guideline docs**

`docs/rules/review-guidelines.md` should keep evidence schema and review requirements, but direct users to `pr_flow` instead of manual copying.

- [ ] **Step 4: Update governance docs**

`docs/rules/governance.md` should describe:

- fast gate for pre-commit
- full gate for pre-push and CI
- `pr_flow` as local PR automation entrypoint

- [ ] **Step 5: Verify docs pathrefs**

Run:

```powershell
.\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor check
```

Expected: pathref check passes.

## Task 6: Final Verification

**Files:**
- No new source files beyond earlier tasks.

- [ ] **Step 1: Run focused tests**

```powershell
.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests -q
```

Expected: all governance tests pass.

- [ ] **Step 2: Run syntax checks for changed modules**

```powershell
.\.githooks\run-python.ps1 -m py_compile scripts\research\governance\ai_review_gate.py scripts\research\governance\gate.py scripts\research\governance\pr_flow.py
```

Expected: exit code 0.

- [ ] **Step 3: Run pathref check**

```powershell
.\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor check
```

Expected: no broken pathrefs.

- [ ] **Step 4: Run full governance gate**

```powershell
.\.githooks\run-python.ps1 -m scripts.research.governance gate
```

Expected: full gate passes.

- [ ] **Step 5: Review final diff**

```powershell
git diff --check
git diff --stat
```

Expected: no whitespace errors; changed files match this plan.

## Notes for Execution

- Do not make `pr_flow sync` run from hooks. GitHub writes must stay explicit.
- Do not auto-merge PRs.
- Do not fabricate AI/security review conclusions.
- Preserve existing CI required checks: `Research Governance / governance`, `Research Governance / pr-review-evidence`, and `Codex Review Monitor`.
- Before implementation starts, decide what to do with the current dirty test file `scripts/research/governance/tests/test_ai_review_gate.py`: keep its added tests as draft material or revert and re-add clean tests during Task 2.

## Review Record - 2026-05-28

**Review setup**

- Subagent A used `superpowers:receiving-code-review` perspective.
- Subagent B used `superpowers:requesting-code-review` perspective.
- Main session independently verified the reported blockers against current code and tests.

**P0**

- None found.

**P1 fixed**

- Changed-file discovery no longer depends only on staged/worktree diff. It now also reads branch diff against `origin/main` / fallback bases and untracked files, so clean committed branches still get correct risk and check selection.
- `pr_flow sync` no longer posts a new `@codex review` trigger when valid `official_codex_review` evidence already exists, avoiding invalidating the accepted review on rerun.
- `bandit-governance` now uses the same skip/exclude policy as `make pre-pr`: excludes governance tests and skips `B310,B404,B603,B607`.
- `mypy-governance` now uses the same package/import flags as `make pre-pr`, and the new governance code/tests pass that check.
- Check selection now accumulates categories for mixed changes instead of returning on the first match.
- `prepare` now selects local checks from local diff plus `.local/ai-review/latest.json.changed_files`, so already-committed high-risk changes are still checked.
- Missing `.local/ai-review/codex-review-scope.md` in `sync` is handled by rendering the validated review scope instead of crashing.
- Missing branch base with an otherwise clean tree now produces unknown changed-files state instead of silently drafting low risk.

**Remaining P0/P1**

- None found after fixes.

**Verification**

- `.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests\test_ai_review_gate.py scripts\research\governance\tests\test_pr_flow.py -q` -> `48 passed`
- `.\.githooks\run-python.ps1 -m pytest scripts\research\governance\tests -q` -> `234 passed`
- `.\.githooks\run-python.ps1 -m ruff check scripts\research\governance\ai_review_gate.py scripts\research\governance\pr_flow.py scripts\research\governance\tests\test_ai_review_gate.py scripts\research\governance\tests\test_pr_flow.py` -> passed
- `.\.githooks\run-python.ps1 -m bandit -q -r scripts\research\governance -x scripts\research\governance\tests -s 'B310,B404,B603,B607'` -> passed
- `.\.githooks\run-python.ps1 -m mypy --explicit-package-bases --follow-imports=skip --ignore-missing-imports scripts\research\governance` -> passed
- `.\.githooks\run-python.ps1 -m py_compile scripts\research\governance\ai_review_gate.py scripts\research\governance\gate.py scripts\research\governance\pr_flow.py` -> passed
- `.\.githooks\run-python.ps1 -m scripts.tools.path_tools.refactor check` -> `Checked 568 pathref link(s).`
- `.\.githooks\run-python.ps1 -m scripts.research.governance gate` -> passed
- `make pre-pr` -> passed pre-commit, ruff, bandit, and mypy; stopped at `pip_audit` because `pypi.org` timed out.
- `git diff --check` -> passed for tracked diff; changed-file trailing whitespace scan across tracked and untracked files -> no matches.
