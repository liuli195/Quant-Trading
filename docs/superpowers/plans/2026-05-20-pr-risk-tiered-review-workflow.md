# PR 风险分级评审流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前“所有 PR 都等官方 Codex 全量评审”的流程改成“本地强预审 + AI 修复闭环 + PR 风险分级 + 高风险范围定向 Codex Review”。

**Architecture:** 本地阶段负责广覆盖检查和修复闭环，CI 负责复验报告和风险判定，官方 Codex PR Review 只在高风险或 unknown 时触发，并只审生成的高风险范围。治理规则、PR 模板、workflow 和 Python gate 共用同一套风险评级语义。

**Tech Stack:** Python 3.12、pytest、GitHub Actions、pre-commit、Ruff、Bandit、Gitleaks、mypy、pip-audit、Makefile、Superpowers、Codex Security、Claude pr-review-toolkit、Claude security-guidance。

---

## 最终方案

完整流程：

```text
本地开发
  ↓
git commit 前 pre-commit
  - Ruff
  - Bandit
  - Gitleaks
  - 基础文件检查
  - governance gate
  ↓
make pre-pr
  - pre-commit run --all-files
  - mypy
  - pip-audit
  - pytest
  - pathref / governance gate
  ↓
make ai-review
  - Codex: Superpowers + Codex Security
  - Claude: pr-review-toolkit + security-guidance
  - 输出问题清单、评级、修复状态、风险等级、Codex Review Scope
  - P0/P1 必须修复或证明误报后才能继续
  - P2 可以保留，但必须写不修原因
  ↓
创建 PR
  ↓
GitHub Actions 复跑扫描、类型、依赖、测试、风险判定
  ↓
高风险或 unknown PR 加 ai-risk-review
  ↓
官方 Codex PR risk review
  - 只审高风险目录和高风险命中改动
  - 只审 P0/P1 逻辑风险
  ↓
人工 review
  ↓
合并
```

评级规则：

- `P0`：严重错误交易、密钥泄露、主干保护绕过、明确安全漏洞。阻塞。
- `P1`：高概率 bug、回归、治理门禁失效、关键测试缺失。阻塞。
- `P2`：中等风险，可以保留，但必须写不修原因、风险接受理由、处理方式。
- `P3`：风格、可读性、小优化，不阻塞。

全局阻塞规则：

- 任何阶段发现的问题都必须评级。
- `P0/P1` 未关闭时，不能进入下一阶段。
- `P0/P1` 只能以 `fixed` 或 `false_positive` 关闭。
- `false_positive` 必须写证据。
- `P2` 保留时必须写 `defer_reason` 和 `risk_acceptance`。
- 报告缺失、格式错误、AI 无法判断风险时，风险等级为 `unknown`，按高风险处理。

官方 Codex Review 新定位：

- 低风险 PR 不触发官方 `@codex review`。
- 高风险或 unknown PR 触发官方 `@codex review`。
- 大型 PR 不要求官方 Codex 全量审查，必须生成 `Codex Review Scope`，只审高风险目录和高风险规则命中改动。
- 如果 scope 无法缩窄到明确文件或模块，PR 要拆分，或按全量高风险 PR 处理。

## 文件结构

新增文件：

- `Makefile`：提供 `pre-pr`、`ai-review`、`risk-check` 本地入口。
- `.pre-commit-config.yaml`：接入 Ruff、Bandit、Gitleaks 和基础文件检查。
- `requirements-dev.txt`：保存本地和 CI 检查工具依赖，避免污染运行依赖。
- `scripts/research/governance/ai_review_gate.py`：AI review 报告 schema、校验、风险判定、Codex Review Scope 生成。
- `scripts/research/governance/tests/test_ai_review_gate.py`：覆盖 AI review gate 的单元测试。
- `docs/adr/0006-risk-tiered-pr-review.md`：记录风险分级评审的治理决策。

修改文件：

- `.githooks/pre-commit`：保留 governance gate，同时接入 pre-commit。
- `.github/pull_request_template.md`：新增风险分级、问题评级、P2 保留原因、Review Scope 链接。
- `.github/workflows/research-governance.yml`：增加静态扫描、类型检查、依赖扫描、测试和 AI review gate。
- `scripts/research/governance/pr_review_evidence.py`：只在高风险或 unknown 时要求官方 Codex Review 证据。
- `scripts/research/governance/rules.py`：把新的规则文档、模板字段、workflow 入口纳入 governance audit。
- `scripts/research/governance/tests/test_governance.py`：增加治理规则漂移测试。
- `docs/rules/pr-workflow.md`：改写 PR review 必须项。
- `docs/rules/review-guidelines.md`：定义本地 AI review、评级规则和定向官方 review。
- `docs/rules/governance.md`：定义 `ai-risk-review`、AI review gate 和 required checks。
- `scripts/research/governance/README.md`：补充本地命令和 CI 行为。

`.local/ai-review/` 继续保持不入库；`.gitignore` 已忽略 `.local/`。

---

### Task 1: 固化规则和 ADR

**Files:**
- Create: `docs/adr/0006-risk-tiered-pr-review.md`
- Modify: `docs/rules/pr-workflow.md`
- Modify: `docs/rules/review-guidelines.md`
- Modify: `docs/rules/governance.md`
- Modify: `scripts/research/governance/README.md`

- [ ] **Step 1: 写 ADR**

Create `docs/adr/0006-risk-tiered-pr-review.md`:

```markdown
# ADR 0006: PR 风险分级评审流程

## Status

Accepted

## Context

当前流程要求所有 PR 合并前都完成官方 Codex Code Review。该规则安全边界清晰，但在低风险 PR 和大型 PR 上造成等待时间过长、重复 review 过多、CI 循环过多。

## Decision

采用风险分级评审流程：

- 所有 PR 必须先完成本地静态扫描、本地 AI review 和问题评级。
- P0/P1 问题必须修复或证明误报后才能继续。
- P2 问题可以保留，但必须记录不修原因、风险接受理由和处理方式。
- 低风险 PR 不强制触发官方 Codex Code Review。
- 高风险或 unknown PR 必须触发官方 Codex Code Review。
- 大型 PR 的官方 Codex Review 必须使用定向 scope，只审高风险目录和高风险命中改动的 P0/P1 逻辑风险。

## Consequences

- 官方 Codex Review 从全量门禁变成高风险复核。
- 本地 AI review 和 CI gate 承担低风险 PR 的主要自动化检查责任。
- 无法证明低风险的 PR 一律按高风险处理。
- 规则、PR 模板、workflow 和 governance gate 必须使用同一套风险评级语义。
```

- [ ] **Step 2: 改 PR 工作流规则**

Modify `docs/rules/pr-workflow.md`:

```markdown
- PR 合并前必须完成本地静态扫描、本地 AI review 和问题评级；P0/P1 问题未关闭时禁止进入下一阶段。
- 低风险 PR 可以不触发官方 Codex Code Review，但必须提供本地 AI review 报告、CI 通过证据和 P2 保留说明。
- 高风险或 unknown PR 必须加 `ai-risk-review`，并触发官方 Codex Code Review。
- 大型 PR 的官方 Codex Code Review 必须使用 `Codex Review Scope`，只审高风险目录和高风险规则命中改动的 P0/P1 逻辑风险。
- 无法生成明确 `Codex Review Scope` 的大型 PR，应拆分 PR；未拆分时按全量高风险 PR 处理。
```

- [ ] **Step 3: 改 review 指南**

Modify `docs/rules/review-guidelines.md`:

```markdown
## 本地 AI Review

- Codex 本地 AI review 使用 Superpowers 和 Codex Security。
- Claude 本地 AI review 使用 pr-review-toolkit 和 security-guidance。
- 所有 AI review provider 必须输出统一报告 schema。
- 本地 AI review 必须输出具体问题、评级、文件位置、建议修复、处理状态和验证证据。
- 本地 AI review 不是 PR 模板生成器；它必须推动 P0/P1 修复闭环。

## 问题评级

- P0/P1 阻塞，必须修复或证明误报。
- P2 可以保留，但必须写不修原因、风险接受理由和处理方式。
- P3 不阻塞。

## 官方 Codex Review 触发条件

- 风险等级为 `high` 或 `unknown`。
- PR 存在 `ai-risk-review` label。
- 本地 AI review 报告缺失、无法解析或无法证明低风险。
- 高风险路径或高风险规则命中。
```

- [ ] **Step 4: 改 governance 规则**

Modify `docs/rules/governance.md`:

```markdown
- `scripts.research.governance.ai_review_gate` 是本地 AI review 报告、风险等级和 Codex Review Scope 的统一校验入口。
- CI 必须校验 AI review 报告；报告缺失或 unknown 时按高风险处理。
- GitHub `main` 的 required status check 必须覆盖静态扫描、类型检查、依赖漏洞扫描、测试、governance gate 和 AI review gate。
- `Codex Review Monitor` 只作为高风险或 unknown PR 的 required gate。
```

- [ ] **Step 5: 更新 governance README**

Modify `scripts/research/governance/README.md` with this command section:

```markdown
## 风险分级评审入口

```powershell
make pre-pr
make ai-review
make risk-check
```

`make ai-review` 生成 `.local/ai-review/latest.json`、`.local/ai-review/latest.md` 和 `.local/ai-review/codex-review-scope.md`。
```

- [ ] **Step 6: 运行文档校验**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: command exits `0` and prints checked pathref count.

- [ ] **Step 7: Commit**

```bash
git add docs/adr/0006-risk-tiered-pr-review.md docs/rules/pr-workflow.md docs/rules/review-guidelines.md docs/rules/governance.md scripts/research/governance/README.md
git commit -m "新增风险分级 PR 评审规则"
```

---

### Task 2: 增加本地检查入口

**Files:**
- Create: `Makefile`
- Create: `.pre-commit-config.yaml`
- Create: `requirements-dev.txt`
- Modify: `.githooks/pre-commit`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 先写治理测试**

Add to `scripts/research/governance/tests/test_governance.py`:

```python
def test_local_review_entrypoints_are_tracked(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    (tmp_path / "Makefile").write_text(
        "pre-pr:\n\tpre-commit run --all-files\n"
        "ai-review:\n\tpython -m scripts.research.governance.ai_review_gate validate --report .local/ai-review/latest.json\n"
        "risk-check:\n\tpython -m scripts.research.governance.ai_review_gate risk --report .local/ai-review/latest.json\n",
        encoding="utf-8",
    )
    (tmp_path / ".pre-commit-config.yaml").write_text(
        "repos:\n"
        "  - repo: https://github.com/astral-sh/ruff-pre-commit\n"
        "  - repo: https://github.com/PyCQA/bandit\n"
        "  - repo: https://github.com/gitleaks/gitleaks\n",
        encoding="utf-8",
    )
    (tmp_path / "requirements-dev.txt").write_text(
        "pre-commit\nruff\nbandit\nmypy\npip-audit\n",
        encoding="utf-8",
    )
    (tmp_path / ".githooks/pre-commit").write_text(
        "pre-commit run --hook-stage pre-commit\n"
        "sh .githooks/run-python.sh -m scripts.research.governance gate\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]
```

- [ ] **Step 2: 运行测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py::test_local_review_entrypoints_are_tracked -q
```

Expected: fails because `run_audit` does not yet check these new entrypoints.

- [ ] **Step 3: 新增 `requirements-dev.txt`**

Create `requirements-dev.txt`:

```text
-r requirements.txt
pre-commit
ruff
bandit
mypy
pip-audit
```

Gitleaks is managed through pre-commit and GitHub Actions, not through pip.

- [ ] **Step 4: 新增 `.pre-commit-config.yaml`**

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.14.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/PyCQA/bandit
    rev: 1.8.6
    hooks:
      - id: bandit
        args: [-q, -r, scripts, strategies]
        pass_filenames: false

  - repo: https://github.com/gitleaks/gitleaks
    rev: v8.28.0
    hooks:
      - id: gitleaks
```

- [ ] **Step 5: 新增 `Makefile`**

Create `Makefile`:

```makefile
.PHONY: pre-pr ai-review risk-check

PYTHON := ./.venv/Scripts/python.exe
AI_REVIEW_REPORT := .local/ai-review/latest.json

pre-pr:
	pre-commit run --all-files
	$(PYTHON) -m mypy scripts strategies
	$(PYTHON) -m pip_audit
	$(PYTHON) -m pytest
	$(PYTHON) -m scripts.tools.path_tools.refactor check
	$(PYTHON) -m scripts.research.governance gate

ai-review:
	$(PYTHON) -m scripts.research.governance.ai_review_gate validate --report $(AI_REVIEW_REPORT)
	$(PYTHON) -m scripts.research.governance.ai_review_gate scope --report $(AI_REVIEW_REPORT) --output .local/ai-review/codex-review-scope.md

risk-check:
	$(PYTHON) -m scripts.research.governance.ai_review_gate risk --report $(AI_REVIEW_REPORT)
```

- [ ] **Step 6: 修改 `.githooks/pre-commit`**

Replace `.githooks/pre-commit` with:

```sh
#!/bin/sh
set -eu

if command -v pre-commit >/dev/null 2>&1; then
  pre-commit run --hook-stage pre-commit
fi

sh .githooks/run-python.sh \
  -m scripts.research.governance gate
```

- [ ] **Step 7: 扩展 governance audit**

Modify `scripts/research/governance/rules.py` by adding `_audit_local_review_entrypoints(root)` and calling it from `run_audit` after `_audit_governance_gate(root)`:

```python
def _audit_local_review_entrypoints(root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []

    makefile = root / "Makefile"
    if not makefile.is_file():
        return [AuditFinding("local_review", "error", "Makefile missing")]
    make_text = makefile.read_text(encoding="utf-8", errors="ignore")
    for token in ("pre-pr", "ai-review", "risk-check", "scripts.research.governance.ai_review_gate"):
        if token not in make_text:
            findings.append(AuditFinding("local_review", "error", f"Makefile missing {token}"))

    pre_commit = root / ".pre-commit-config.yaml"
    if not pre_commit.is_file():
        findings.append(AuditFinding("local_review", "error", ".pre-commit-config.yaml missing"))
    else:
        text = pre_commit.read_text(encoding="utf-8", errors="ignore")
        for token in ("ruff-pre-commit", "bandit", "gitleaks"):
            if token not in text:
                findings.append(AuditFinding("local_review", "error", f"pre-commit config missing {token}"))

    requirements_dev = root / "requirements-dev.txt"
    if not requirements_dev.is_file():
        findings.append(AuditFinding("local_review", "error", "requirements-dev.txt missing"))
    else:
        text = requirements_dev.read_text(encoding="utf-8", errors="ignore")
        for token in ("pre-commit", "ruff", "bandit", "mypy", "pip-audit"):
            if token not in text:
                findings.append(AuditFinding("local_review", "error", f"requirements-dev.txt missing {token}"))

    hook = root / ".githooks" / "pre-commit"
    if hook.is_file():
        text = hook.read_text(encoding="utf-8", errors="ignore")
        if "pre-commit run" not in text:
            findings.append(AuditFinding("local_review", "error", "pre-commit hook missing pre-commit run"))

    return findings
```

- [ ] **Step 8: 运行测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py::test_local_review_entrypoints_are_tracked -q
```

Expected: `1 passed`.

- [ ] **Step 9: Commit**

```bash
git add Makefile .pre-commit-config.yaml requirements-dev.txt .githooks/pre-commit scripts/research/governance/rules.py scripts/research/governance/tests/test_governance.py
git commit -m "新增本地 PR 预审入口"
```

---

### Task 3: 实现 AI review 报告协议和风险 gate

**Files:**
- Create: `scripts/research/governance/ai_review_gate.py`
- Create: `scripts/research/governance/tests/test_ai_review_gate.py`

- [ ] **Step 1: 写失败测试：P0/P1 未关闭必须失败**

Create `scripts/research/governance/tests/test_ai_review_gate.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from scripts.research.governance.ai_review_gate import validate_report_file


def _write_report(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_open_p1_blocks_progress(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 1,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "changed_files": ["strategies/etf_factor_rotation/etf_factor_rotation.py"],
            "findings": [
                {
                    "id": "AIR-001",
                    "severity": "P1",
                    "title": "默认参数变更缺少回归验证",
                    "path": "strategies/etf_factor_rotation/etf_factor_rotation.py",
                    "status": "open",
                    "evidence": "diff changes default MA parameter",
                    "recommendation": "补充回归测试或云端确认证据",
                }
            ],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "P0/P1 finding AIR-001 is not closed" in result.errors
```

- [ ] **Step 2: 写失败测试：P2 保留必须有理由**

Add:

```python
def test_p2_requires_defer_reason(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 1,
            "tool": "claude",
            "reviewers": ["pr-review-toolkit", "security-guidance"],
            "risk_level": "low",
            "requires_official_codex_review": False,
            "changed_files": ["docs/guides/example.md"],
            "findings": [
                {
                    "id": "AIR-002",
                    "severity": "P2",
                    "title": "说明不够完整",
                    "path": "docs/guides/example.md",
                    "status": "accepted",
                    "evidence": "review noted missing context",
                    "recommendation": "补充上下文",
                }
            ],
            "checks": {"pytest": "pass"},
        },
    )

    result = validate_report_file(report)

    assert not result.ok
    assert "P2 finding AIR-002 accepted without defer_reason" in result.errors
```

- [ ] **Step 3: 写失败测试：高风险路径生成 scope**

Add:

```python
def test_high_risk_scope_mentions_changed_file(tmp_path: Path) -> None:
    report = tmp_path / "latest.json"
    _write_report(
        report,
        {
            "schema_version": 1,
            "tool": "codex",
            "reviewers": ["superpowers", "codex-security"],
            "risk_level": "high",
            "requires_official_codex_review": True,
            "changed_files": ["scripts/research/governance/rules.py"],
            "findings": [],
            "checks": {"pytest": "pass", "governance_gate": "pass"},
        },
    )

    result = validate_report_file(report)

    assert result.ok
    assert "scripts/research/governance/rules.py" in result.review_scope
    assert "@codex review" in result.review_scope
    assert "只审以下高风险范围的 P0/P1 逻辑风险" in result.review_scope
```

- [ ] **Step 4: 运行测试确认失败**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_ai_review_gate.py -q
```

Expected: import error because `ai_review_gate.py` does not exist.

- [ ] **Step 5: 实现 `ai_review_gate.py`**

Create `scripts/research/governance/ai_review_gate.py`:

```python
"""Validate local AI review reports and generate Codex review scope."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BLOCKING_SEVERITIES = {"P0", "P1"}
VALID_SEVERITIES = {"P0", "P1", "P2", "P3"}
VALID_STATUSES = {"open", "fixed", "false_positive", "accepted"}
HIGH_RISK_PREFIXES = (
    "strategies/",
    "scripts/research/governance/",
    ".github/workflows/",
    ".githooks/",
    "docs/rules/",
    "docs/adr/",
)


@dataclass(frozen=True)
class AiReviewValidation:
    ok: bool
    risk_level: str
    requires_official_codex_review: bool
    errors: tuple[str, ...]
    review_scope: str


def validate_report_file(path: Path) -> AiReviewValidation:
    if not path.is_file():
        return AiReviewValidation(False, "unknown", True, (f"AI review report missing: {path}",), "")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return AiReviewValidation(False, "unknown", True, (f"AI review report invalid JSON: {exc}",), "")
    return validate_report(payload)


def validate_report(payload: dict[str, Any]) -> AiReviewValidation:
    errors: list[str] = []
    risk_level = str(payload.get("risk_level") or "unknown")
    changed_files = _string_list(payload.get("changed_files"))
    findings = payload.get("findings")
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if str(payload.get("tool") or "") not in {"codex", "claude"}:
        errors.append("tool must be codex or claude")
    reviewers = _string_list(payload.get("reviewers"))
    if not reviewers:
        errors.append("reviewers must not be empty")
    if risk_level not in {"low", "high", "unknown"}:
        errors.append("risk_level must be low, high, or unknown")
        risk_level = "unknown"
    if not changed_files:
        errors.append("changed_files must not be empty")
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        findings = []

    for item in findings:
        if not isinstance(item, dict):
            errors.append("each finding must be an object")
            continue
        finding_id = str(item.get("id") or "<missing-id>")
        severity = str(item.get("severity") or "")
        status = str(item.get("status") or "")
        if severity not in VALID_SEVERITIES:
            errors.append(f"finding {finding_id} has invalid severity")
        if status not in VALID_STATUSES:
            errors.append(f"finding {finding_id} has invalid status")
        if severity in BLOCKING_SEVERITIES and status not in {"fixed", "false_positive"}:
            errors.append(f"P0/P1 finding {finding_id} is not closed")
        if status == "false_positive" and not str(item.get("evidence") or "").strip():
            errors.append(f"false_positive finding {finding_id} missing evidence")
        if severity == "P2" and status == "accepted":
            if not str(item.get("defer_reason") or "").strip():
                errors.append(f"P2 finding {finding_id} accepted without defer_reason")
            if not str(item.get("risk_acceptance") or "").strip():
                errors.append(f"P2 finding {finding_id} accepted without risk_acceptance")

    high_risk_by_path = any(_is_high_risk_path(path) for path in changed_files)
    requires_official = bool(payload.get("requires_official_codex_review")) or risk_level != "low" or high_risk_by_path
    if high_risk_by_path and risk_level == "low":
        errors.append("high-risk changed files cannot be risk_level low")
        risk_level = "high"
        requires_official = True
    review_scope = build_codex_review_scope(payload, requires_official=requires_official)
    return AiReviewValidation(not errors, risk_level, requires_official, tuple(errors), review_scope)


def build_codex_review_scope(payload: dict[str, Any], *, requires_official: bool) -> str:
    changed_files = _string_list(payload.get("changed_files"))
    high_risk_files = [path for path in changed_files if _is_high_risk_path(path)]
    risk_files = high_risk_files or changed_files
    finding_lines = []
    for item in payload.get("findings") or []:
        if not isinstance(item, dict):
            continue
        severity = str(item.get("severity") or "")
        if severity in {"P0", "P1", "P2"}:
            finding_lines.append(
                f"- {item.get('id')}: {severity} {item.get('title')} ({item.get('path')}) status={item.get('status')}"
            )
    scope_files = "\n".join(f"- `{path}`" for path in risk_files)
    findings_text = "\n".join(finding_lines) if finding_lines else "- 无未关闭 P0/P1；无必须交给官方复核的本地发现。"
    if not requires_official:
        return "本 PR 当前不要求官方 Codex Review。"
    return (
        "@codex review\n\n"
        "请只审以下高风险范围的 P0/P1 逻辑风险，不做全量风格审查。\n\n"
        "## Review Scope\n\n"
        "### 高风险文件\n"
        f"{scope_files}\n\n"
        "### 本地 AI Review 结果\n"
        f"{findings_text}\n\n"
        "### 审查重点\n"
        "- 交易逻辑、治理门禁、安全边界、数据解释是否存在 P0/P1 风险。\n"
        "- 不需要重复给出 P2/P3 风格建议。\n"
    )


def _is_high_risk_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    return any(normalized.startswith(prefix) for prefix in HIGH_RISK_PREFIXES)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "risk", "scope"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--report", type=Path, required=True)
        if name == "scope":
            subparser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_report_file(args.report)
    if args.command == "scope":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result.review_scope, encoding="utf-8")
    if args.command == "risk":
        print(result.risk_level)
    if args.command == "validate":
        print("AI review report ok" if result.ok else "AI review report failed")
    for error in result.errors:
        print(f"error: {error}", file=sys.stderr)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: 运行测试确认通过**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_ai_review_gate.py -q
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```bash
git add scripts/research/governance/ai_review_gate.py scripts/research/governance/tests/test_ai_review_gate.py
git commit -m "新增 AI review 风险 gate"
```

---

### Task 4: 让 PR 证据按风险分级校验

**Files:**
- Modify: `scripts/research/governance/pr_review_evidence.py`
- Modify: `scripts/research/governance/tests/test_governance.py`
- Modify: `.github/pull_request_template.md`

- [ ] **Step 1: 写失败测试：低风险不要求 Codex review 链接**

Add to `scripts/research/governance/tests/test_governance.py`:

```python
def test_low_risk_pr_body_does_not_require_codex_review() -> None:
    body = """
## AI Review 风险分级

- 风险等级: low
- 是否需要官方 Codex Review: 否
- 本地 AI review: `.local/ai-review/latest.md`
- P0/P1 未关闭项: 无

## P2 保留项

- 无
"""

    report = validate_pr_body(body, comments=[])

    assert report.ok, report.errors
```

- [ ] **Step 2: 写失败测试：高风险仍要求 Codex review**

Add:

```python
def test_high_risk_pr_body_requires_codex_review() -> None:
    body = """
## AI Review 风险分级

- 风险等级: high
- 是否需要官方 Codex Review: 是
- 本地 AI review: `.local/ai-review/latest.md`
- P0/P1 未关闭项: 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review 按 AGENTS.md 和 docs/rules/review-guidelines.md 审；逐条检查 docs/rules/*.md`
- 结论: 未执行
- 阻断问题: 未确认
- 关键证据:
  - Codex review 链接：https://github.com/example/repo/pull/1#pullrequestreview-1
  - `scripts.research.governance gate`
"""

    report = validate_pr_body(body, comments=[])

    assert not report.ok
    assert any("PR comments must include the required @codex review trigger" in error for error in report.errors)
```

- [ ] **Step 3: 修改 `pr_review_evidence.py`**

Change `validate_pr_body` behavior:

```python
AI_REVIEW_SECTION_HEADER = "AI Review 风险分级"


def _extract_named_section(body: str, header: str) -> str | None:
    lines = body.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if re.match(rf"^\s*##+\s+{re.escape(header)}\s*$", line):
            start = index + 1
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start, len(lines)):
        if re.match(r"^\s*##+\s+\S+", lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def _official_codex_required(body: str) -> tuple[bool, list[str]]:
    errors: list[str] = []
    section = _extract_named_section(body, AI_REVIEW_SECTION_HEADER)
    if section is None:
        return True, [f"PR body missing section: {AI_REVIEW_SECTION_HEADER}"]
    risk = _normalize_value(_read_field(section, "风险等级"))
    requires = _normalize_value(_read_field(section, "是否需要官方 Codex Review"))
    blockers = _normalize_value(_read_field(section, "P0/P1 未关闭项"))
    if risk not in {"low", "high", "unknown"}:
        errors.append("风险等级 must be low, high, or unknown")
        return True, errors
    if blockers != "无":
        errors.append("P0/P1 未关闭项 must be 无")
    if risk in {"high", "unknown"}:
        return True, errors
    if requires not in {"否", "不需要", "false", "False"}:
        errors.append("低风险 PR must mark 是否需要官方 Codex Review as 否")
        return True, errors
    return False, errors
```

At the start of `validate_pr_body`, call `_official_codex_required(body)`. If it returns `False`, skip the existing `Codex Code Review 结论` section validation and return the AI review errors only.

- [ ] **Step 4: 修改 PR 模板**

Replace the review section in `.github/pull_request_template.md` with:

```markdown
## AI Review 风险分级

- 风险等级: low / high / unknown
- 是否需要官方 Codex Review: 是 / 否
- 本地 AI review: `.local/ai-review/latest.md`
- Codex Review Scope: `.local/ai-review/codex-review-scope.md`
- P0/P1 未关闭项: 无

## P2 保留项

- 无

## Codex Code Review 结论

- Reviewer: `Codex`
- 触发方式: `@codex review 按 AGENTS.md 和 docs/rules/review-guidelines.md 审；逐条检查 docs/rules/*.md`
- 结论: 未要求 / 未执行 / 通过
- 阻断问题: 无 / 未确认
- 关键证据:
  - Codex review 链接：
  - `.\.venv\Scripts\python.exe -m scripts.research.governance gate`
```

- [ ] **Step 5: 运行测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py::test_low_risk_pr_body_does_not_require_codex_review scripts\research\governance\tests\test_governance.py::test_high_risk_pr_body_requires_codex_review -q
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```bash
git add scripts/research/governance/pr_review_evidence.py scripts/research/governance/tests/test_governance.py .github/pull_request_template.md
git commit -m "按风险分级校验 PR review 证据"
```

---

### Task 5: 修改 CI 为本地检查和风险分级复验

**Files:**
- Modify: `.github/workflows/research-governance.yml`
- Modify: `scripts/research/governance/rules.py`
- Modify: `scripts/research/governance/tests/test_governance.py`

- [ ] **Step 1: 写失败测试：workflow 必须包含新 gate**

Add to `scripts/research/governance/tests/test_governance.py`:

```python
def test_governance_workflow_contains_ai_review_gate(tmp_path: Path) -> None:
    _write_minimal_repo(tmp_path)
    workflow = tmp_path / ".github/workflows/research-governance.yml"
    workflow.write_text(
        "name: Research Governance\n"
        "on:\n  pull_request:\n    types: [opened, synchronize, reopened, edited, ready_for_review]\n"
        "jobs:\n"
        "  governance:\n"
        "    steps:\n"
        "      - run: python -m scripts.research.governance gate\n"
        "      - run: python -m scripts.research.governance.ai_review_gate validate --report .local/ai-review/latest.json\n"
        "      - run: python -m mypy scripts strategies\n"
        "      - run: python -m pip_audit\n",
        encoding="utf-8",
    )

    report = run_audit(tmp_path, check_cli_help=False, check_pathrefs=False)

    assert report.ok, [finding.message for finding in report.findings]
```

- [ ] **Step 2: 修改 workflow**

In `.github/workflows/research-governance.yml`, update dependencies and jobs:

```yaml
      - name: Install dependencies
        run: python -m pip install -r requirements-dev.txt
      - name: Ruff
        run: python -m ruff check scripts strategies
      - name: Bandit
        run: python -m bandit -q -r scripts strategies
      - name: Mypy
        run: python -m mypy scripts strategies
      - name: Pip audit
        run: python -m pip_audit
      - name: Tests
        run: python -m pytest
      - name: AI review risk gate
        run: python -m scripts.research.governance.ai_review_gate validate --report .local/ai-review/latest.json
      - name: Run governance gate
        run: python -m scripts.research.governance gate
```

Keep `pr-review-evidence` job, but let the modified Python validator decide whether official Codex evidence is required.

- [ ] **Step 3: 扩展 governance audit workflow tokens**

Modify `_audit_governance_gate` in `scripts/research/governance/rules.py`:

```python
        for token in (
            "scripts.research.governance gate",
            "scripts.research.governance.ai_review_gate",
            "ruff",
            "bandit",
            "mypy",
            "pip_audit",
            "pytest",
        ):
            if token not in text:
                findings.append(AuditFinding("governance_gate", "error", f"CI workflow missing {token}"))
```

- [ ] **Step 4: 运行 workflow 审计测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests\test_governance.py::test_governance_workflow_contains_ai_review_gate -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/research-governance.yml scripts/research/governance/rules.py scripts/research/governance/tests/test_governance.py
git commit -m "在 CI 中复验风险分级评审"
```

---

### Task 6: 同步索引、入口文档和全量验证

**Files:**
- Modify: `indexes.md`
- Modify: `docs/indexes/docs_catalog.json`
- Modify: `docs/indexes/reports_catalog.json`
- Modify: `docs/indexes/datasets_catalog.json`
- Modify: `docs/indexes/variants_catalog.json`
- Modify: `CLAUDE.md`

- [ ] **Step 1: 检查是否需要同步 `CLAUDE.md`**

Open `CLAUDE.md` and add a short pointer only if it has a PR/review workflow section:

```markdown
- PR 评审流程以 [docs/rules/review-guidelines.md](../../rules/review-guidelines.md) <!-- pathref: docs/rules/review-guidelines.md --> 为准；本地 AI review 和风险分级由 governance gate 校验。
```

- [ ] **Step 2: 重新生成或校验索引**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.research.governance gate --skip-cli-help
```

Expected: exits `0`. If it reports stale catalog files, run the existing catalog generation command shown by the error message, then rerun the gate.

- [ ] **Step 3: 跑路径引用校验**

Run:

```powershell
.\.venv\Scripts\python.exe -m scripts.tools.path_tools.refactor check
```

Expected: exits `0`.

- [ ] **Step 4: 跑治理测试**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest scripts\research\governance\tests -q
```

Expected: all tests pass.

- [ ] **Step 5: 跑最终本地入口**

Run:

```powershell
make pre-pr
```

Expected: Ruff、Bandit、mypy、pip-audit、pytest、pathref 和 governance gate pass.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md indexes.md docs/indexes docs/superpowers/plans/2026-05-20-pr-risk-tiered-review-workflow.md
git commit -m "同步风险分级评审计划和索引"
```

---

## 验收标准

- `make pre-pr` 可作为开 PR 前的统一本地入口。
- `make ai-review` 会校验 `.local/ai-review/latest.json` 并生成 `.local/ai-review/codex-review-scope.md`。
- AI review 报告中任何 open P0/P1 都会阻塞。
- P2 保留项缺少 `defer_reason` 或 `risk_acceptance` 会阻塞。
- 低风险 PR 不再强制要求官方 Codex Review 链接。
- 高风险或 unknown PR 仍要求官方 Codex Review 证据。
- 大型高风险 PR 的官方 Codex Review 请求包含明确 scope。
- `scripts.research.governance gate` 能发现规则、模板、workflow 和本地入口漂移。
- `scripts\research\governance\tests` 全部通过。

## 执行建议

按任务顺序执行。每个任务都独立提交，避免一次性改坏完整 PR 链路。先不要改 GitHub required checks；等 CI workflow 和 `pr_review_evidence.py` 在一个测试 PR 中跑通后，再把 required checks 调整为新的组合。
