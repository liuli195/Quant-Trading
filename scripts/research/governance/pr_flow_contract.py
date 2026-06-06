"""Load and apply the PR Flow machine interface contract."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONTRACT_PATH = Path("docs") / "rules" / "pr-flow-interface-contract.yaml"
SUBMIT_STATUS_SCHEMA_VERSION = 3
SUBMIT_STATUS_CHECKPOINT_NAMES = (
    "official_codex_review",
    "required_checks",
    "pr_evidence",
    "review_threads",
    "local_review_fragments",
)
SUBMIT_STATUS_FIELDS = (
    "schema_version",
    "snapshot_subject",
    "pr_submit_stop",
    "checkpoint_statuses",
    "blocking_signals",
    "diagnostic_signals",
    "suggested_next_actions",
    "evidence_artifacts",
)
LEGACY_SUBMIT_STATUS_FIELDS = {"schema", "head", "failures"}


@dataclass(frozen=True)
class PRFlowContract:
    version: int
    json_indent: int
    json_ensure_ascii: bool
    required_settings: dict[str, bool]
    required_checks: tuple[str, ...]
    reviewer_fragments: dict[str, Path]
    review_fragments_handoff_path: Path
    resolve_threads_plan_path: Path
    thread_closure_evidence_path: Path
    local_stabilization_path: Path
    submit_status_path: Path
    marker_start: str
    marker_end: str
    fenced_language: str
    pr_evidence_fields: tuple[str, ...]
    fragment_fields: tuple[str, ...]
    fragment_finding_fields: tuple[str, ...]
    fragment_security_review_fields: tuple[str, ...]
    fragment_security_review_default_tool: str
    fragment_security_review_fallback_required_when_tool_not: str
    submit_status_fields: tuple[str, ...]
    submit_failure_fields: tuple[str, ...]
    blocking_severities: tuple[str, ...]
    retained_severities: tuple[str, ...]
    retained_sources: tuple[str, ...]
    detail_max_chars: int
    detail_single_line: bool
    official_codex_command: str
    official_codex_fields: tuple[str, ...]
    target_spec_wins: bool
    fragment_freshness_same_diff_head_refresh: bool
    github_native_closing_links_from_per_commit_evidence: bool
    local_stable_required_checks: tuple[str, ...]
    local_stable_excluded_checks: tuple[str, ...]
    local_stable_pending_reason_code: str
    local_stable_pending_phase: str
    codex_thread_p0_p1_requires_closure_evidence: bool
    codex_thread_human_never_auto_resolve: bool
    codex_thread_no_severity_never_auto_resolve: bool
    codex_thread_p2_p3_auto_accept: bool
    workflow_pending_before_execution: bool


@dataclass(frozen=True)
class SubmitFailure:
    check: str
    source: str
    detail: str


def load_contract(repo_root: str | Path = ".") -> PRFlowContract:
    root = Path(repo_root).resolve()
    path = root / CONTRACT_PATH
    if not path.is_file():
        path = Path.cwd() / CONTRACT_PATH
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"PR Flow contract must be a mapping: {path}")

    artifacts = _mapping(payload.get("artifacts"), "artifacts")
    reviewer_fragments = _mapping(
        artifacts.get("reviewer_fragments"),
        "artifacts.reviewer_fragments",
    )
    submit_status = _single_line(artifacts.get("submit_status"))
    rules = _mapping(payload.get("rules"), "rules")
    pr_evidence = _mapping(payload.get("pr_evidence"), "pr_evidence")
    fragment = _mapping(payload.get("fragment"), "fragment")
    fragment_security_review = _mapping(
        fragment.get("security_review"),
        "fragment.security_review",
    )
    status = _mapping(payload.get("submit_status"), "submit_status")
    severity = _mapping(payload.get("severity"), "severity")
    sources = _mapping(payload.get("sources"), "sources")
    detail = _mapping(payload.get("detail"), "detail")
    github = _mapping(payload.get("github"), "github")
    official = _mapping(payload.get("official_codex_request"), "official_codex_request")
    submit_status_fields = _string_tuple(status.get("fields"))
    _validate_submit_status_fields(submit_status_fields)

    fragment_freshness = _mapping(rules.get("fragment_freshness"), "rules.fragment_freshness")
    local_stable_gate = _mapping(rules.get("local_stable_gate"), "rules.local_stable_gate")
    closing_links = _mapping(
        rules.get("github_native_closing_links"),
        "rules.github_native_closing_links",
    )
    codex_thread = _mapping(
        rules.get("codex_thread_automation"),
        "rules.codex_thread_automation",
    )
    workflow_pending = _mapping(
        rules.get("workflow_pending"),
        "rules.workflow_pending",
    )

    return PRFlowContract(
        version=_int(payload.get("version"), "version"),
        json_indent=_int(_mapping(payload.get("json"), "json").get("indent"), "json.indent"),
        json_ensure_ascii=bool(
            _mapping(payload.get("json"), "json").get("ensure_ascii")
        ),
        required_settings={
            str(key): bool(value)
            for key, value in _mapping(
                github.get("required_settings"),
                "github.required_settings",
            ).items()
        },
        required_checks=_string_tuple(payload.get("required_checks")),
        reviewer_fragments={
            role: Path(_single_line(path_value))
            for role, path_value in reviewer_fragments.items()
        },
        review_fragments_handoff_path=Path(
            _single_line(artifacts.get("review_fragments_handoff"))
        ),
        resolve_threads_plan_path=Path(_single_line(artifacts.get("resolve_threads_plan"))),
        thread_closure_evidence_path=Path(
            _single_line(artifacts.get("thread_closure_evidence"))
        ),
        local_stabilization_path=Path(_single_line(artifacts.get("local_stabilization"))),
        submit_status_path=Path(submit_status),
        marker_start=_single_line(pr_evidence.get("marker_start")),
        marker_end=_single_line(pr_evidence.get("marker_end")),
        fenced_language=_single_line(pr_evidence.get("fenced_language")),
        pr_evidence_fields=_string_tuple(pr_evidence.get("fields")),
        fragment_fields=_string_tuple(fragment.get("fields")),
        fragment_finding_fields=_string_tuple(fragment.get("finding_fields")),
        fragment_security_review_fields=_string_tuple(
            fragment_security_review.get("fields")
        ),
        fragment_security_review_default_tool=_single_line(
            fragment_security_review.get("default_tool")
        ),
        fragment_security_review_fallback_required_when_tool_not=_single_line(
            fragment_security_review.get("fallback_reason_required_when_tool_not")
        ),
        submit_status_fields=submit_status_fields,
        submit_failure_fields=_string_tuple(status.get("failure_fields")),
        blocking_severities=_string_tuple(_mapping(severity, "severity").get("blocking")),
        retained_severities=_string_tuple(_mapping(severity, "severity").get("retained")),
        retained_sources=_string_tuple(_mapping(sources, "sources").get("retained")),
        detail_max_chars=_int(detail.get("max_chars"), "detail.max_chars"),
        detail_single_line=bool(detail.get("single_line")),
        official_codex_command=_single_line(official.get("command")),
        official_codex_fields=_string_tuple(official.get("fields")),
        target_spec_wins=bool(rules.get("target_spec_wins")),
        fragment_freshness_same_diff_head_refresh=bool(
            fragment_freshness.get("same_diff_head_refresh")
        ),
        github_native_closing_links_from_per_commit_evidence=bool(
            closing_links.get("from_per_commit_evidence")
        ),
        local_stable_required_checks=_string_tuple(
            local_stable_gate.get("required_checks")
        ),
        local_stable_excluded_checks=_string_tuple(
            local_stable_gate.get("excluded_checks")
        ),
        local_stable_pending_reason_code=_single_line(
            local_stable_gate.get("pending_reason_code")
        ),
        local_stable_pending_phase=_single_line(local_stable_gate.get("pending_phase")),
        codex_thread_p0_p1_requires_closure_evidence=bool(
            codex_thread.get("p0_p1_requires_closure_evidence")
        ),
        codex_thread_human_never_auto_resolve=bool(
            codex_thread.get("human_never_auto_resolve")
        ),
        codex_thread_no_severity_never_auto_resolve=bool(
            codex_thread.get("no_severity_never_auto_resolve")
        ),
        codex_thread_p2_p3_auto_accept=bool(
            codex_thread.get("p2_p3_auto_accept")
        ),
        workflow_pending_before_execution=bool(
            workflow_pending.get("before_execution")
        ),
    )


def write_submit_status(
    repo_root: str | Path,
    contract: PRFlowContract,
    *,
    head: str,
    failures: Sequence[SubmitFailure | Mapping[str, object]],
    repository: str = "",
    pr_number: str = "",
    head_branch: str = "",
    stop_state: str = "",
    reason_code: str = "",
    phase: str = "",
    retryable: bool = False,
    diagnostics: Sequence[SubmitFailure | Mapping[str, object]] = (),
    checkpoint_statuses: Sequence[Mapping[str, object]] = (),
    suggested_next_actions: Sequence[Mapping[str, object]] = (),
    evidence_artifacts: Sequence[Mapping[str, object]] = (),
) -> Path:
    root = Path(repo_root).resolve()
    path = root / contract.submit_status_path
    blocking_signals = [
        _signal_from_failure(
            failure,
            contract=contract,
            currentness="current",
            retryable=retryable,
        )
        for failure in failures
    ]
    diagnostic_signals = [
        _signal_from_failure(
            failure,
            contract=contract,
            currentness="stale",
            retryable=_failure_retryable(failure),
        )
        for failure in diagnostics
    ]
    summary = _single_line(
        "; ".join(
            f"{_failure_value(failure, 'check')}: "
            f"{normalize_detail(_failure_value(failure, 'detail'), max_chars=contract.detail_max_chars)}"
            for failure in failures
        )
    )
    payload = {
        "schema_version": SUBMIT_STATUS_SCHEMA_VERSION,
        "snapshot_subject": {
            "repository": _single_line(repository),
            "pr_number": _single_line(pr_number),
            "head_sha": _single_line(head),
            "head_branch": _single_line(head_branch),
        },
        "pr_submit_stop": {
            "state": _single_line(stop_state),
            "reason_code": _single_line(reason_code),
            "phase": _single_line(phase),
            "is_retryable": bool(retryable),
            "summary": normalize_detail(summary, max_chars=contract.detail_max_chars),
        },
        "checkpoint_statuses": _merged_checkpoint_statuses(
            checkpoint_statuses,
            failures=failures,
            diagnostics=diagnostics,
            contract=contract,
        ),
        "blocking_signals": blocking_signals,
        "diagnostic_signals": diagnostic_signals,
        "suggested_next_actions": _suggested_next_actions(
            suggested_next_actions,
            blocking_signals=blocking_signals,
            diagnostic_signals=diagnostic_signals,
        ),
        "evidence_artifacts": _existing_evidence_artifacts(root, evidence_artifacts),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=contract.json_ensure_ascii,
            indent=contract.json_indent,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _signal_from_failure(
    failure: SubmitFailure | Mapping[str, object],
    *,
    contract: PRFlowContract,
    currentness: str,
    retryable: bool,
) -> dict[str, object]:
    check = _failure_value(failure, "check")
    detail = normalize_detail(
        _failure_value(failure, "detail"),
        max_chars=contract.detail_max_chars,
    )
    return {
        "signal_type": _signal_type_for_failure(check, detail, contract=contract),
        "summary": detail,
        "source_context": check,
        "evidence_location": _failure_value(failure, "source"),
        "currentness": currentness,
        "is_retryable": bool(retryable or _failure_retryable(failure)),
    }


def _signal_type_for_failure(
    check: str,
    detail: str,
    *,
    contract: PRFlowContract,
) -> str:
    normalized = f"{check} {detail}".casefold()
    if "stale required check ignored" in normalized:
        return "stale_required_check_ignored"
    if check in contract.required_checks or "required check" in normalized:
        if "pending" in normalized or "timed out" in normalized:
            return "required_check_pending"
        return "required_check_failed"
    if "thread" in normalized:
        return "review_thread_unresolved"
    if "fragment" in normalized or check in {"standards", "spec", "security"}:
        return "local_review_fragment_invalid"
    if "github" in normalized:
        return "github_unavailable"
    return "pr_submit_blocked"


def _failure_retryable(failure: SubmitFailure | Mapping[str, object]) -> bool:
    detail = _failure_value(failure, "detail").casefold()
    check = _failure_value(failure, "check").casefold()
    return (
        "pending" in detail
        or "timed out" in detail
        or "stale" in detail
        or "github" in check
    )


def _merged_checkpoint_statuses(
    checkpoint_statuses: Sequence[Mapping[str, object]],
    *,
    failures: Sequence[SubmitFailure | Mapping[str, object]],
    diagnostics: Sequence[SubmitFailure | Mapping[str, object]],
    contract: PRFlowContract,
) -> list[dict[str, str]]:
    by_name = {
        name: {
            "checkpoint_name": name,
            "status": "unknown",
            "summary": "",
            "evidence_location": "",
        }
        for name in SUBMIT_STATUS_CHECKPOINT_NAMES
    }
    for checkpoint in checkpoint_statuses:
        name = _single_line(checkpoint.get("checkpoint_name"))
        if name not in by_name:
            continue
        by_name[name] = {
            "checkpoint_name": name,
            "status": _single_line(checkpoint.get("status")) or "unknown",
            "summary": normalize_detail(
                _single_line(checkpoint.get("summary")),
                max_chars=contract.detail_max_chars,
            ),
            "evidence_location": _single_line(checkpoint.get("evidence_location")),
        }
    for failure in failures:
        _apply_failure_to_checkpoints(by_name, failure, contract=contract, status="failed")
    for diagnostic in diagnostics:
        _apply_failure_to_checkpoints(by_name, diagnostic, contract=contract, status="stale")
    return [by_name[name] for name in SUBMIT_STATUS_CHECKPOINT_NAMES]


def _apply_failure_to_checkpoints(
    by_name: dict[str, dict[str, str]],
    failure: SubmitFailure | Mapping[str, object],
    *,
    contract: PRFlowContract,
    status: str,
) -> None:
    check = _failure_value(failure, "check")
    detail = normalize_detail(
        _failure_value(failure, "detail"),
        max_chars=contract.detail_max_chars,
    )
    source = _failure_value(failure, "source")
    normalized = f"{check} {detail}".casefold()
    names: list[str] = []
    if check in contract.required_checks or "required check" in normalized:
        names.append("required_checks")
    if check == "PR Flow / evidence" or "pr evidence" in normalized:
        names.append("pr_evidence")
    if "thread" in normalized:
        names.append("review_threads")
    if "official-codex-review" in normalized or "official codex" in normalized:
        names.append("official_codex_review")
    if "fragment" in normalized or check in {"standards", "spec", "security"}:
        names.append("local_review_fragments")
    for name in names:
        checkpoint = by_name[name]
        if checkpoint["status"] == "failed" and status != "failed":
            continue
        checkpoint["status"] = status
        checkpoint["summary"] = detail
        checkpoint["evidence_location"] = source


def _suggested_next_actions(
    actions: Sequence[Mapping[str, object]],
    *,
    blocking_signals: Sequence[Mapping[str, object]],
    diagnostic_signals: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    normalized_actions: list[dict[str, object]] = []
    for action in actions:
        signal_types = action.get("applies_to_signal_types")
        normalized_actions.append(
            {
                "action_summary": _single_line(action.get("action_summary")),
                "recommended_command": _single_line(action.get("recommended_command")),
                "applies_to_signal_types": _string_tuple(signal_types),
            }
        )
    if normalized_actions:
        return normalized_actions
    signal_types = [
        _single_line(signal.get("signal_type"))
        for signal in [*blocking_signals, *diagnostic_signals]
    ]
    unique_signal_types = tuple(dict.fromkeys(signal_type for signal_type in signal_types if signal_type))
    if "review_thread_unresolved" in unique_signal_types:
        return [
            {
                "action_summary": "inspect unresolved review threads and resolve explicit IDs after evidence is ready",
                "recommended_command": ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.pr_flow resolve-threads <THREAD_ID>",
                "applies_to_signal_types": ("review_thread_unresolved",),
            }
        ]
    if any(signal_type.startswith("required_check") for signal_type in unique_signal_types):
        return [
            {
                "action_summary": "rerun pr-submit after the current required-check state changes",
                "recommended_command": ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.pr_flow submit --title \"<PR标题>\"",
                "applies_to_signal_types": unique_signal_types,
            }
        ]
    if unique_signal_types:
        return [
            {
                "action_summary": "inspect status snapshot and rerun pr-submit after fixing the blocker",
                "recommended_command": ".\\.venv\\Scripts\\python.exe -m scripts.research.governance.pr_flow submit --title \"<PR标题>\"",
                "applies_to_signal_types": unique_signal_types,
            }
        ]
    return []


def _existing_evidence_artifacts(
    root: Path,
    evidence_artifacts: Sequence[Mapping[str, object]],
) -> list[dict[str, str]]:
    artifacts: list[dict[str, str]] = []
    for artifact in evidence_artifacts:
        artifact_path = _single_line(artifact.get("artifact_path"))
        if not artifact_path:
            continue
        path = Path(artifact_path)
        if path.is_absolute() or not (root / path).is_file():
            continue
        artifacts.append(
            {
                "artifact_type": _single_line(artifact.get("artifact_type")),
                "artifact_path": artifact_path.replace("\\", "/"),
                "artifact_summary": _single_line(artifact.get("artifact_summary")),
            }
        )
    return artifacts


def _validate_submit_status_fields(fields: tuple[str, ...]) -> None:
    legacy = sorted(LEGACY_SUBMIT_STATUS_FIELDS.intersection(fields))
    if legacy:
        raise ValueError(
            "legacy submit_status fields are not allowed: " + ", ".join(legacy)
        )
    missing = [field for field in SUBMIT_STATUS_FIELDS if field not in fields]
    if missing:
        raise ValueError(
            "submit_status v3 missing required fields: " + ", ".join(missing)
        )


def normalize_detail(value: object, *, max_chars: int) -> str:
    detail = " ".join(_single_line(value).split())
    if len(detail) <= max_chars:
        return detail
    return detail[: max_chars - 3].rstrip() + "..."


def _failure_value(
    failure: SubmitFailure | Mapping[str, object],
    field: str,
) -> str:
    if isinstance(failure, SubmitFailure):
        return getattr(failure, field)
    return _single_line(failure.get(field))


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"PR Flow contract field must be a mapping: {label}")
    return value


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(_single_line(item) for item in value if _single_line(item))


def _single_line(value: object) -> str:
    return " ".join(str(value or "").splitlines()).strip()


def _int(value: object, label: str) -> int:
    try:
        return int(_single_line(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"PR Flow contract field must be an integer: {label}") from exc
