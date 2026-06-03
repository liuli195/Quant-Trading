"""Load and apply the PR Flow machine interface contract."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


CONTRACT_PATH = Path("docs") / "rules" / "pr-flow-interface-contract.yaml"


@dataclass(frozen=True)
class PRFlowContract:
    version: int
    json_indent: int
    json_ensure_ascii: bool
    required_settings: dict[str, bool]
    required_checks: tuple[str, ...]
    reviewer_fragments: dict[str, Path]
    submit_status_path: Path
    handoff_status_path: Path
    stop_state_fields: tuple[str, ...]
    marker_start: str
    marker_end: str
    fenced_language: str
    pr_evidence_fields: tuple[str, ...]
    fragment_fields: tuple[str, ...]
    fragment_finding_fields: tuple[str, ...]
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
    codex_thread_auto_resolve_outdated: bool
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
    handoff_status = _single_line(artifacts.get("handoff_status"))
    stop_state = _mapping(payload.get("stop_state"), "stop_state")
    rules = _mapping(payload.get("rules"), "rules")
    pr_evidence = _mapping(payload.get("pr_evidence"), "pr_evidence")
    fragment = _mapping(payload.get("fragment"), "fragment")
    status = _mapping(payload.get("submit_status"), "submit_status")
    severity = _mapping(payload.get("severity"), "severity")
    sources = _mapping(payload.get("sources"), "sources")
    detail = _mapping(payload.get("detail"), "detail")
    github = _mapping(payload.get("github"), "github")
    official = _mapping(payload.get("official_codex_request"), "official_codex_request")

    fragment_freshness = _mapping(rules.get("fragment_freshness"), "rules.fragment_freshness")
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
        submit_status_path=Path(submit_status),
        handoff_status_path=Path(handoff_status) if handoff_status else Path(".local/pr-flow/last-status.json"),
        stop_state_fields=_string_tuple(stop_state.get("fields")),
        marker_start=_single_line(pr_evidence.get("marker_start")),
        marker_end=_single_line(pr_evidence.get("marker_end")),
        fenced_language=_single_line(pr_evidence.get("fenced_language")),
        pr_evidence_fields=_string_tuple(pr_evidence.get("fields")),
        fragment_fields=_string_tuple(fragment.get("fields")),
        fragment_finding_fields=_string_tuple(fragment.get("finding_fields")),
        submit_status_fields=_string_tuple(status.get("fields")),
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
        codex_thread_auto_resolve_outdated=bool(
            codex_thread.get("auto_resolve_outdated")
        ),
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
) -> Path:
    root = Path(repo_root).resolve()
    path = root / contract.submit_status_path
    payload = {
        "schema": contract.version,
        "head": _single_line(head),
        "failures": [
            {
                "check": _failure_value(failure, "check"),
                "source": _failure_value(failure, "source"),
                "detail": normalize_detail(
                    _failure_value(failure, "detail"),
                    max_chars=contract.detail_max_chars,
                ),
            }
            for failure in failures
        ],
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
