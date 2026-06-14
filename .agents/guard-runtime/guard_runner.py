"""项目级 Guard Runtime（守卫运行时）统一 CLI 入口。"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import yaml


PROFILE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
BRIEF_TTL_SECONDS = 30 * 60


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def future_iso(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} 不是有效 YAML（YAML 配置格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是 YAML mapping（YAML 映射）。")
    return data


def read_json_arg(value: str | None, field: str) -> dict[str, Any]:
    if value is None or value.strip() == "":
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} 不是有效 JSON（JSON 格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{field} 必须是 JSON object（JSON 对象）。")
    return data


def read_json_file(path: Path, field: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} 不是有效 JSON（JSON 格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{field} 顶层必须是 JSON object（JSON 对象）。")
    return data


def value_at(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict)) and not value:
        return False
    return True


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def validate_profile_id(profile_id: str) -> str:
    normalized = profile_id.strip()
    if not PROFILE_ID_PATTERN.fullmatch(normalized):
        raise ValueError("Guard Profile（守卫画像）ID 只能使用 ASCII 字母、数字、点、下划线和连字符，且不能包含路径分隔符。")
    return normalized


def field_source(field: str) -> str:
    return field.split(".", 1)[0]


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def profile_dir(project: Path, profile_id: str) -> Path:
    return project / ".agents" / "guards" / profile_id


def run_dir(project: Path, profile_id: str, run_id: str) -> Path:
    return project / ".local" / "guard" / "runs" / profile_id / run_id


def write_audit(
    project: Path,
    profile_id: str,
    run_id: str,
    status: str,
    envelope: dict[str, Any],
    detail: dict[str, Any],
) -> Path:
    directory = run_dir(project, profile_id, run_id)
    raw_event_path = directory / "raw-event.json"
    audit_path = directory / "audit.json"
    write_json(raw_event_path, envelope)
    write_json(
        audit_path,
        {
            "run_id": run_id,
            "guard_profile_id": profile_id,
            "status": status,
            "created_at": now_iso(),
            "raw_event_path": str(raw_event_path),
            "envelope": envelope,
            "detail": detail,
        },
    )
    return audit_path


CORE_OUTPUT_KEYS = {"status", "decision", "reason", "details"}


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    return value


def default_decision(status: str) -> str:
    return {
        "allow": "guard_passed",
        "ask": "confirmation_required",
        "deny": "denied",
        "error": "failed",
        "lock_timeout": "failed",
        "not_found": "failed",
        "stale_brief": "failed",
        "expired_brief": "failed",
        "ambiguous_subject": "unresolved",
        "no_subject_match": "unresolved",
        "activated": "guard_passed",
        "injectable": "guard_passed",
        "already_injected": "ignored",
        "ok": "guard_passed",
    }.get(status, "failed")


def default_reason(status: str, decision: str) -> str:
    if decision == "guard_passed":
        return "ok"
    if decision == "confirmation_required":
        return "confirmation_required"
    if status:
        return status
    return "unknown"


def output_envelope(output: dict[str, Any]) -> dict[str, Any]:
    if "status" not in output:
        return output
    normalized = dict(output)
    status = str(normalized["status"])
    decision = str(normalized.get("decision") or default_decision(status))
    reason = str(normalized.get("reason") or default_reason(status, decision))
    details = normalized.get("details")
    details = dict(details) if isinstance(details, dict) else {}
    for key, value in normalized.items():
        if key not in CORE_OUTPUT_KEYS and key not in details:
            details[key] = value

    ordered: dict[str, Any] = {
        "status": status,
        "decision": decision,
        "reason": reason,
        "details": json_safe(details),
    }
    for key, value in normalized.items():
        if key not in ordered:
            ordered[key] = json_safe(value)
    return ordered


def subject_resolution_fix_suggestions(reason: str | None, missing_fields: list[str] | None = None) -> list[str]:
    if reason == "missing_required_fields":
        fields = ", ".join(missing_fields or [])
        return [f"补齐 Subject Resolver（主体解析器）必填字段：{fields}。"]
    if reason == "instance_not_found":
        return ["先显式 activate（激活）该 Guard Profile（守卫画像）和 Subject（主体），再提交事件。"]
    if reason == "ambiguous_subject":
        return ["收窄 Subject Resolver（主体解析器）的 identity_fields（身份字段）或 optional_fields（可选字段），确保只匹配一个 Guard Instance（守卫实例）。"]
    return ["检查事件 context（上下文）、subject（主体）和 Guard Profile（守卫画像）的 Subject Resolver（主体解析器）配置。"]


def print_lines(lines: dict[str, Any]) -> None:
    lines = output_envelope(lines)
    for key, value in lines.items():
        if isinstance(value, (list, dict)):
            rendered = json.dumps(json_safe(value), ensure_ascii=False, sort_keys=True)
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        print(f"{key}: {rendered}")


def load_profile_documents(profile: Path) -> dict[str, dict[str, Any]]:
    concurrency = profile / "concurrency.yaml"
    manifest = load_yaml_mapping(profile / "GUARD-MANIFEST.yaml")
    if "mode" in manifest:
        raise ValueError("GUARD-MANIFEST.yaml 中的 `mode` 已废弃；删除它，并改用 state-machine.yaml 的 states[].permissions。")
    return {
        "manifest": manifest,
        "activation": load_yaml_mapping(profile / "activation-model.yaml"),
        "subject": load_yaml_mapping(profile / "subject-resolver.yaml"),
        "state_machine": load_yaml_mapping(profile / "state-machine.yaml"),
        "execution": load_yaml_mapping(profile / "execution-model.yaml"),
        "guard_points": load_yaml_mapping(profile / "guard-points.yaml"),
        "artifacts": load_yaml_mapping(profile / "artifacts.yaml"),
        "concurrency": load_yaml_mapping(concurrency) if concurrency.exists() else {},
    }


def list_value(data: dict[str, Any], field: str) -> list[str]:
    value = value_at(data, field)
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def scalar_value(data: dict[str, Any], field: str) -> str | None:
    value = value_at(data, field)
    return value if isinstance(value, str) else None


def validate_activation_request(
    docs: dict[str, dict[str, Any]],
    envelope: dict[str, Any],
) -> tuple[bool, str]:
    activation = docs["activation"]
    allowed_sources = set(list_value(activation, "activation.allowed_sources"))
    scopes = set(list_value(activation, "activation.scopes"))

    source = envelope.get("source")
    scope = envelope.get("scope")
    if allowed_sources and source not in allowed_sources:
        return False, f"source_not_allowed:{source}"
    if scopes and scope not in scopes:
        return False, f"scope_not_allowed:{scope}"
    if value_at(activation, "activation.required_profile_ref") is True and not envelope.get("guard_profile_id"):
        return False, "profile_ref_required"
    return True, "ok"


def unique_fields(fields: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for field in fields:
        if field in seen:
            continue
        seen.add(field)
        result.append(field)
    return result


def resolve_subject(
    docs: dict[str, dict[str, Any]],
    envelope: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str], str | None]:
    subject_doc = docs["subject"]
    identity_fields = list_value(subject_doc, "subject.identity_fields")
    required_fields = list_value(subject_doc, "subject.required_fields")
    optional_fields = list_value(subject_doc, "subject.optional_fields")
    context_sources = set(list_value(subject_doc, "subject.context_sources"))

    configured_fields = unique_fields(identity_fields + optional_fields)
    missing: list[str] = []
    values: dict[str, Any] = {}

    for field in unique_fields(required_fields + identity_fields):
        if context_sources and field_source(field) not in context_sources:
            missing.append(field)
            continue
        if not is_present(value_at(envelope, field)):
            missing.append(field)

    if missing:
        return None, unique_fields(missing), "missing_required_fields"

    for field in configured_fields:
        if context_sources and field_source(field) not in context_sources:
            continue
        value = value_at(envelope, field)
        if is_present(value):
            values[field] = value

    subject_key = json.dumps(values, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        {
            "identity_fields": identity_fields,
            "required_fields": required_fields,
            "optional_fields": optional_fields,
            "values": values,
            "subject_key": subject_key,
            "subject_key_hash": stable_hash(subject_key),
        },
        [],
        None,
    )


def state_root(project: Path, profile_id: str) -> Path:
    return project / ".local" / "guard" / "state" / profile_id


def lock_timeout_seconds(docs: dict[str, dict[str, Any]]) -> float:
    value = value_at(docs.get("concurrency", {}), "concurrency.timeout_seconds")
    if isinstance(value, (int, float)) and value >= 0:
        return float(value)
    return 30.0


def lock_path(project: Path, profile_id: str, subject_hash: str) -> Path:
    return project / ".local" / "guard" / "locks" / profile_id / f"{subject_hash}.lock"


def acquire_subject_lock(project: Path, profile_id: str, subject_hash: str, timeout_seconds: float) -> dict[str, Any]:
    path = lock_path(project, profile_id, subject_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "guard_profile_id": profile_id,
                        "subject_key_hash": subject_hash,
                        "pid": os.getpid(),
                        "created_at": now_iso(),
                    },
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")
            return {"acquired": True, "path": path}
        except FileExistsError:
            if time.monotonic() >= deadline:
                return {"acquired": False, "path": path, "reason": "lock_timeout"}
            time.sleep(0.05)


def release_subject_lock(lock: dict[str, Any]) -> None:
    if not lock.get("acquired"):
        return
    path = lock.get("path")
    if isinstance(path, Path):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
    lock["acquired"] = False


def write_lock_timeout(
    project: Path,
    profile_id: str,
    run_id: str,
    envelope: dict[str, Any],
    subject: dict[str, Any],
    lock: dict[str, Any],
) -> Path:
    return write_audit(
        project,
        profile_id,
        run_id,
        "lock_timeout",
        envelope,
        {
            "reason": "lock_timeout",
            "subject_key": subject["subject_key"],
            "subject_key_hash": subject["subject_key_hash"],
            "lock_path": str(lock.get("path", "")),
        },
    )


def load_state(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def find_matching_instances(project: Path, profile_id: str, subject: dict[str, Any]) -> list[tuple[Path, dict[str, Any]]]:
    root = state_root(project, profile_id)
    if not root.exists():
        return []
    matches: list[tuple[Path, dict[str, Any]]] = []
    for state_path in root.glob("*/state.json"):
        state = load_state(state_path)
        if not state:
            continue
        if state.get("subject_key") == subject["subject_key"]:
            matches.append((state_path, state))
    return matches


def execution_state_summary(docs: dict[str, dict[str, Any]], state_id: str) -> dict[str, Any]:
    execution = docs["execution"]
    states = execution.get("states")
    if not isinstance(states, list):
        return {"allowed_next": [], "forbidden_next": [], "missing_artifacts": [], "next_step": ""}
    for state in states:
        if not isinstance(state, dict) or state.get("id") != state_id:
            continue
        brief = state.get("brief") if isinstance(state.get("brief"), dict) else {}
        return {
            "allowed_next": state.get("allowed_next", []),
            "forbidden_next": state.get("forbidden_next", []),
            "missing_artifacts": state.get("missing_artifacts", []),
            "next_step": brief.get("next_step", "") if isinstance(brief, dict) else "",
        }
    return {"allowed_next": [], "forbidden_next": [], "missing_artifacts": [], "next_step": ""}


def state_machine_state(docs: dict[str, dict[str, Any]], state_id: str) -> dict[str, Any]:
    states = docs["state_machine"].get("states")
    for state in states if isinstance(states, list) else []:
        if isinstance(state, dict) and state.get("id") == state_id:
            return state
    return {}


def outgoing_transition_summaries(docs: dict[str, dict[str, Any]], state_id: str) -> list[dict[str, Any]]:
    transitions = docs["state_machine"].get("transitions")
    summaries: list[dict[str, Any]] = []
    for transition in transitions if isinstance(transitions, list) else []:
        if not isinstance(transition, dict):
            continue
        if transition.get("from") != state_id or transition.get("on_event") != "state_completed":
            continue
        summaries.append(
            {
                "transition_id": transition.get("id"),
                "to": transition.get("to"),
                "conditions": transition.get("conditions", []),
                "required_artifacts": transition.get("required_artifacts", []),
                "guard_points": transition.get("guard_points", []),
            }
        )
    return summaries


def state_machine_brief_summary(docs: dict[str, dict[str, Any]], state_id: str) -> dict[str, Any]:
    state = state_machine_state(docs, state_id)
    terminal_states = docs["state_machine"].get("terminal_states")
    is_terminal = isinstance(terminal_states, list) and state_id in terminal_states
    transitions = outgoing_transition_summaries(docs, state_id)
    summary = {
        "permissions": state.get("permissions", {}) if isinstance(state.get("permissions"), dict) else {},
        "transition_conditions": transitions,
    }
    if is_terminal:
        summary["state_completion_instruction"] = "流程已完成；只需查看 Audit（审计）位置。"
    elif transitions:
        summary["completable_state_id"] = state_id
        summary["state_completion_instruction"] = f"提交 event_type=state_completed，completed_state_id={state_id}。"
    else:
        summary["state_completion_instruction"] = "当前状态没有可完成转换；查看 Audit（审计）位置。"
    return summary


def format_brief_value(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "[]"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    if value is None:
        return ""
    return str(value)


def load_brief_template(profile: Path) -> str:
    path = profile / "brief-template.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """# Guard Brief（守卫简报）

Guard Profile（守卫画像）：{{ guard_profile_id }}
Subject（主体）：{{ subject_key }}
当前状态：{{ state }}
允许下一步：{{ allowed_next }}
禁止下一步：{{ forbidden_next }}
缺失 Artifacts（产物）：{{ missing_artifacts }}
最近拒绝原因：{{ recent_denial_reasons }}
状态权限：{{ permissions }}
完成条件：{{ transition_conditions }}
下一步：{{ next_step }}
状态推进：{{ state_completion_instruction }}
Audit（审计）：{{ audit_path }}
"""


def render_brief_text(template: str, values: dict[str, Any]) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{{ " + key + " }}", format_brief_value(value))
        rendered = rendered.replace("{{" + key + "}}", format_brief_value(value))
    return rendered.rstrip() + "\n"


def brief_hash_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "guard_profile_id": payload["guard_profile_id"],
        "subject_key_hash": payload["subject_key_hash"],
        "state": payload["state"],
        "state_version": payload["state_version"],
        "allowed_next": payload["allowed_next"],
        "forbidden_next": payload["forbidden_next"],
        "missing_artifacts": payload["missing_artifacts"],
        "recent_denial_reasons": payload["recent_denial_reasons"],
        "permissions": payload["permissions"],
        "transition_conditions": payload["transition_conditions"],
        "completable_state_id": payload.get("completable_state_id", ""),
        "state_completion_instruction": payload["state_completion_instruction"],
        "next_step": payload["next_step"],
    }


def injection_record_path(project: Path, profile_id: str, subject_hash: str, session: str) -> Path:
    return project / ".local" / "guard" / "injections" / profile_id / subject_hash / f"{stable_hash(session)}.json"


def record_brief_injection(
    project: Path,
    profile_id: str,
    subject_hash: str,
    session: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    path = injection_record_path(project, profile_id, subject_hash, session)
    existing = load_state(path) if path.exists() else None
    record = existing or {
        "guard_profile_id": profile_id,
        "subject_key_hash": subject_hash,
        "session": session,
        "brief_hashes": [],
        "records": [],
    }
    brief_hash = str(payload.get("brief_hash", ""))
    hashes = record.get("brief_hashes")
    if not isinstance(hashes, list):
        hashes = []
        record["brief_hashes"] = hashes

    already_injected = brief_hash in hashes
    if not already_injected:
        hashes.append(brief_hash)
        records = record.get("records")
        if not isinstance(records, list):
            records = []
            record["records"] = records
        records.append(
            {
                "brief_hash": brief_hash,
                "state": payload.get("state"),
                "state_version": payload.get("state_version"),
                "injected_at": now_iso(),
                "context": context,
            }
        )
    record["updated_at"] = now_iso()
    write_json(path, record)
    return {"already_injected": already_injected, "injection_record_path": str(path)}


def write_latest_brief(
    project: Path,
    profile_id: str,
    run_id: str,
    subject: dict[str, Any],
    state: dict[str, Any],
    docs: dict[str, dict[str, Any]],
    audit_path: Path,
    recent_denial_reasons: list[str] | None = None,
    missing_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    current_state = str(state.get("current_state", ""))
    summary = execution_state_summary(docs, current_state)
    if missing_artifacts is not None:
        summary["missing_artifacts"] = missing_artifacts
    runtime_summary = state_machine_brief_summary(docs, current_state)

    payload = {
        "guard_profile_id": profile_id,
        "subject_key": subject["subject_key"],
        "subject_key_hash": subject["subject_key_hash"],
        "state": current_state,
        "state_version": state.get("state_version"),
        "audit_path": str(audit_path),
        "generated_at": now_iso(),
        "generated_from_run_id": run_id,
        "source": "guard-runtime",
        "recent_denial_reasons": recent_denial_reasons or [],
        "expires_at": future_iso(BRIEF_TTL_SECONDS),
        **summary,
        **runtime_summary,
    }
    template = load_brief_template(profile_dir(project, profile_id))
    payload["brief_text"] = render_brief_text(template, payload)
    payload["brief_hash"] = stable_hash(
        json.dumps(brief_hash_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )

    directory = run_dir(project, profile_id, run_id)
    brief_json = directory / "brief.json"
    brief_text = directory / "brief.md"
    brief_input = directory / "brief-input.json"
    write_json(brief_json, payload)
    brief_text.write_text(payload["brief_text"], encoding="utf-8")
    write_json(brief_input, payload)

    latest = project / ".local" / "guard" / "latest" / profile_id / subject["subject_key_hash"]
    latest_json = latest / "brief.json"
    latest_text = latest / "brief.md"
    latest_input = latest / "brief-input.json"
    write_json(latest_json, payload)
    latest_text.write_text(payload["brief_text"], encoding="utf-8")
    write_json(latest_input, payload)
    return {
        "brief_input_path": brief_input,
        "brief_path": brief_json,
        "latest_brief_path": latest_json,
        "brief_hash": payload["brief_hash"],
    }


def create_instance_state(
    project: Path,
    profile_id: str,
    docs: dict[str, dict[str, Any]],
    envelope: dict[str, Any],
    subject: dict[str, Any],
    run_id: str,
) -> tuple[Path, dict[str, Any]]:
    initial_state = scalar_value(docs["activation"], "activation.initial_state")
    if initial_state is None:
        initial_state = scalar_value(docs["state_machine"], "initial_state") or "unknown"

    path = state_root(project, profile_id) / subject["subject_key_hash"] / "state.json"
    entered_at = now_iso()
    state = {
        "guard_profile_id": profile_id,
        "profile_ref": profile_id,
        "subject_key": subject["subject_key"],
        "subject_key_hash": subject["subject_key_hash"],
        "subject": {
            "identity_fields": subject["identity_fields"],
            "required_fields": subject["required_fields"],
            "optional_fields": subject["optional_fields"],
            "values": subject["values"],
        },
        "current_state": initial_state,
        "state_version": 1,
        "created_at": entered_at,
        "current_state_entered_at": entered_at,
        "created_by": envelope.get("source"),
        "last_run_id": run_id,
    }
    write_json(path, state)
    return path, state


def activate_guard(args: argparse.Namespace) -> int:
    project = project_root()
    try:
        profile_id = validate_profile_id(args.profile)
    except ValueError as exc:
        print_lines({"status": "error", "reason": exc})
        return 2
    profile = profile_dir(project, profile_id)
    if not profile.exists():
        print_lines({"status": "error", "reason": "profile_not_found", "guard_profile_id": profile_id})
        return 2

    try:
        docs = load_profile_documents(profile)
        context = read_json_arg(args.context_json, "--context-json")
        subject_input = read_json_arg(args.subject_json, "--subject-json")
    except ValueError as exc:
        print_lines({"status": "error", "reason": exc})
        return 2

    envelope = {
        "action": "activate_guard",
        "guard_profile_id": profile_id,
        "scope": args.scope,
        "source": args.source,
        "context": context,
        "subject": subject_input,
    }
    run_id = uuid.uuid4().hex

    accepted, reason = validate_activation_request(docs, envelope)
    if not accepted:
        audit_path = write_audit(project, profile_id, run_id, "activation_rejected", envelope, {"reason": reason})
        print_lines(
            {
                "status": "activation_rejected",
                "guard_profile_id": profile_id,
                "reason": reason,
                "audit_path": audit_path,
            }
        )
        return 1

    subject, missing, failure_reason = resolve_subject(docs, envelope)
    if subject is None:
        fix_suggestions = subject_resolution_fix_suggestions(failure_reason, missing)
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "no_subject_match",
            envelope,
            {"reason": failure_reason, "missing_fields": missing, "fix_suggestions": fix_suggestions},
        )
        print_lines(
            {
                "status": "no_subject_match",
                "guard_profile_id": profile_id,
                "reason": failure_reason,
                "missing_fields": missing,
                "fix_suggestions": fix_suggestions,
                "audit_path": audit_path,
            }
        )
        return 0

    lock = acquire_subject_lock(project, profile_id, subject["subject_key_hash"], lock_timeout_seconds(docs))
    if not lock["acquired"]:
        audit_path = write_lock_timeout(project, profile_id, run_id, envelope, subject, lock)
        print_lines(
            {
                "status": "lock_timeout",
                "guard_profile_id": profile_id,
                "subject_key_hash": subject["subject_key_hash"],
                "lock_path": lock["path"],
                "audit_path": audit_path,
            }
        )
        return 1
    atexit.register(release_subject_lock, lock)

    try:
        matches = find_matching_instances(project, profile_id, subject)
        if len(matches) > 1:
            fix_suggestions = subject_resolution_fix_suggestions("ambiguous_subject")
            audit_path = write_audit(
                project,
                profile_id,
                run_id,
                "ambiguous_subject",
                envelope,
                {
                    "subject_key": subject["subject_key"],
                    "subject_key_hash": subject["subject_key_hash"],
                    "candidate_state_paths": [str(path) for path, _state in matches],
                    "fix_suggestions": fix_suggestions,
                },
            )
            print_lines(
                {
                    "status": "ambiguous_subject",
                    "guard_profile_id": profile_id,
                    "subject_key_hash": subject["subject_key_hash"],
                    "candidate_count": len(matches),
                    "fix_suggestions": fix_suggestions,
                    "audit_path": audit_path,
                }
            )
            return 0

        if len(matches) == 1:
            state_path, state = matches[0]
            resolution = "matched"
        else:
            create_policy = scalar_value(docs["subject"], "subject.create_policy")
            on_missing = scalar_value(docs["activation"], "activation.on_missing_subject")
            if create_policy != "explicit_activation_only" or on_missing != "create":
                fix_suggestions = subject_resolution_fix_suggestions("instance_not_found")
                audit_path = write_audit(
                    project,
                    profile_id,
                    run_id,
                    "no_subject_match",
                    envelope,
                    {
                        "reason": "creation_not_allowed",
                        "create_policy": create_policy,
                        "on_missing_subject": on_missing,
                        "subject_key": subject["subject_key"],
                        "subject_key_hash": subject["subject_key_hash"],
                        "fix_suggestions": fix_suggestions,
                    },
                )
                print_lines(
                    {
                        "status": "no_subject_match",
                        "guard_profile_id": profile_id,
                        "reason": "creation_not_allowed",
                        "subject_key_hash": subject["subject_key_hash"],
                        "fix_suggestions": fix_suggestions,
                        "audit_path": audit_path,
                    }
                )
                return 0
            state_path, state = create_instance_state(project, profile_id, docs, envelope, subject, run_id)
            resolution = "created"

        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "activated",
            envelope,
            {
                "resolution": resolution,
                "state_path": str(state_path),
                "subject_key": subject["subject_key"],
                "subject_key_hash": subject["subject_key_hash"],
                "current_state": state["current_state"],
            },
        )
        brief_paths = write_latest_brief(
            project,
            profile_id,
            run_id,
            subject,
            state,
            docs,
            audit_path,
        )
        print_lines(
            {
                "status": "activated",
                "resolution": resolution,
                "guard_profile_id": profile_id,
                "subject_key_hash": subject["subject_key_hash"],
                "state": state["current_state"],
                "state_path": state_path,
                "audit_path": audit_path,
                "brief_input_path": brief_paths["brief_input_path"],
                "brief_path": brief_paths["brief_path"],
                "brief_hash": brief_paths["brief_hash"],
            }
        )
        return 0
    finally:
        release_subject_lock(lock)


def mapping_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def normalize_event(raw: dict[str, Any], event_path: Path) -> dict[str, Any]:
    event_obj = mapping_or_empty(raw.get("event"))
    profile_id = raw.get("guard_profile_id") or raw.get("profile_ref")
    event_type = raw.get("event_type") or event_obj.get("type")
    source = raw.get("source") or event_obj.get("source") or "unknown"
    event_id = raw.get("event_id") or event_obj.get("id") or uuid.uuid4().hex
    timestamp = raw.get("timestamp") or event_obj.get("timestamp") or now_iso()
    completed_state_id = raw.get("completed_state_id") or event_obj.get("completed_state_id")

    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ValueError("标准事件缺少 `guard_profile_id` 或 `profile_ref`。")
    profile_id = validate_profile_id(profile_id)
    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("标准事件缺少 `event_type`。")

    normalized_event = {
        **event_obj,
        "id": str(event_id),
        "type": event_type.strip(),
        "source": str(source),
        "timestamp": str(timestamp),
    }
    return {
        "event_id": str(event_id),
        "event_type": event_type.strip(),
        "completed_state_id": completed_state_id,
        "source": str(source),
        "timestamp": str(timestamp),
        "guard_profile_id": profile_id,
        "profile_ref": profile_id,
        "event": normalized_event,
        "context": mapping_or_empty(raw.get("context")),
        "subject": mapping_or_empty(raw.get("subject")),
        "payload": mapping_or_empty(raw.get("payload")),
        "tool": mapping_or_empty(raw.get("tool")),
        "action": mapping_or_empty(raw.get("action")),
        "hook": mapping_or_empty(raw.get("hook")),
        "raw_event_summary": raw.get("raw_event_summary", ""),
        "raw_event_path": str(event_path),
    }


def transitions_for_state(docs: dict[str, dict[str, Any]], current_state: str, envelope: dict[str, Any]) -> list[dict[str, Any]]:
    transitions = docs["state_machine"].get("transitions")
    if not isinstance(transitions, list):
        return []

    event_type = envelope["event_type"]
    matches: list[dict[str, Any]] = []
    for transition in transitions:
        if not isinstance(transition, dict):
            continue
        if transition.get("from") != current_state:
            continue
        if transition.get("on_event") != event_type:
            continue
        if transition_conditions_match(transition, envelope):
            matches.append(transition)
    return matches


def is_hook_state_completed_event(envelope: dict[str, Any]) -> bool:
    if envelope.get("event_type") != "state_completed":
        return False
    return bool(mapping_or_empty(envelope.get("hook")))


def is_hook_event(envelope: dict[str, Any]) -> bool:
    return bool(mapping_or_empty(envelope.get("hook")))


def state_by_id(docs: dict[str, dict[str, Any]], state_id: str) -> dict[str, Any] | None:
    states = docs["state_machine"].get("states")
    if not isinstance(states, list):
        return None
    for state in states:
        if isinstance(state, dict) and state.get("id") == state_id:
            return state
    return None


def command_from_envelope(envelope: dict[str, Any]) -> str:
    payload = mapping_or_empty(envelope.get("payload"))
    action = mapping_or_empty(envelope.get("action"))
    for value in [
        payload.get("command"),
        payload.get("cmd"),
        value_at(payload, "tool_input.command"),
        value_at(payload, "input.command"),
        action.get("command"),
    ]:
        if isinstance(value, str):
            return value
    return ""


def command_prefix_matches(command: str, expected_prefix: Any) -> bool:
    if isinstance(expected_prefix, str):
        return command.strip().startswith(expected_prefix.strip())
    if isinstance(expected_prefix, list):
        prefix = " ".join(str(item).strip() for item in expected_prefix if str(item).strip())
        return command.strip().startswith(prefix)
    return False


def string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        values: list[str] = []
        for item in value:
            values.extend(string_values(item))
        return values
    return []


def normalized_path(value: str) -> str:
    return value.replace("\\", "/")


def path_matches(value: str, expected: Any) -> bool:
    path = normalized_path(value)
    for pattern in string_values(expected):
        normalized = normalized_path(pattern)
        if any(char in normalized for char in "*?[]"):
            if fnmatchcase(path, normalized):
                return True
        elif path == normalized:
            return True
    return False


def path_prefix_matches(value: str, expected_prefix: Any) -> bool:
    path = normalized_path(value)
    for prefix in string_values(expected_prefix):
        if path.startswith(normalized_path(prefix)):
            return True
    return False


def path_values_from_envelope(envelope: dict[str, Any]) -> list[str]:
    fields = [
        "payload.path",
        "payload.paths",
        "payload.file",
        "payload.files",
        "payload.file_path",
        "payload.file_paths",
        "payload.tool_input.path",
        "payload.tool_input.paths",
        "payload.tool_input.file",
        "payload.tool_input.files",
        "payload.tool_input.file_path",
        "payload.tool_input.file_paths",
        "payload.input.path",
        "payload.input.paths",
        "payload.input.file",
        "payload.input.files",
        "payload.input.file_path",
        "payload.input.file_paths",
        "action.path",
        "action.paths",
    ]
    values: list[str] = []
    for field in fields:
        values.extend(string_values(value_at(envelope, field)))
    return unique_fields(values)


def value_condition_matches(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, dict):
        return actual == expected
    known = {"equals", "in", "contains", "exists", "prefix", "glob"}
    if not known.intersection(expected.keys()) or any(key not in known for key in expected):
        return False
    if "equals" in expected and actual != expected.get("equals"):
        return False
    if "in" in expected:
        if not isinstance(expected.get("in"), list) or actual not in expected["in"]:
            return False
    if "contains" in expected:
        contains = expected.get("contains")
        if isinstance(actual, (list, str)):
            if contains not in actual:
                return False
        elif isinstance(actual, dict):
            if contains not in actual and contains not in actual.values():
                return False
        else:
            return False
    if "exists" in expected and is_present(actual) is not bool(expected.get("exists")):
        return False
    if "prefix" in expected:
        prefixes = string_values(expected.get("prefix"))
        if not isinstance(actual, str) or not prefixes or not any(actual.startswith(prefix) for prefix in prefixes):
            return False
    if "glob" in expected:
        if not isinstance(actual, str) or not string_values(expected.get("glob")) or not path_matches(actual, expected.get("glob")):
            return False
    return True


def fields_match(envelope: dict[str, Any], fields: Any) -> bool:
    if not isinstance(fields, dict):
        return False
    for field, expected in fields.items():
        if not isinstance(field, str) or not field.strip():
            return False
        if not value_condition_matches(value_at(envelope, field), expected):
            return False
    return True


def parameter_matches(envelope: dict[str, Any], parameters: Any) -> bool:
    if not isinstance(parameters, dict):
        return False
    for name, expected in parameters.items():
        if not isinstance(name, str) or not name.strip():
            return False
        candidates = [
            value_at(envelope, f"payload.tool_input.{name}"),
            value_at(envelope, f"payload.input.{name}"),
            value_at(envelope, f"payload.parameters.{name}"),
            value_at(envelope, f"payload.params.{name}"),
            value_at(envelope, f"payload.args.{name}"),
            value_at(envelope, f"payload.arguments.{name}"),
            value_at(envelope, f"payload.{name}"),
            value_at(envelope, f"action.{name}"),
        ]
        if not any(value_condition_matches(candidate, expected) for candidate in candidates):
            return False
    return True


def permission_rule_matches(envelope: dict[str, Any], rule: dict[str, Any]) -> bool:
    tool_name = value_at(envelope, "tool.name")
    rule_tool = rule.get("tool")
    if isinstance(rule_tool, str) and rule_tool and rule_tool != tool_name:
        return False

    match = rule.get("match")
    if not isinstance(match, dict) or not match:
        return True

    supported_keys = {
        "command_prefix",
        "path",
        "paths",
        "path_glob",
        "path_prefix",
        "fields",
        "event_fields",
        "parameters",
        "field",
        "equals",
        "in",
        "contains",
        "exists",
        "prefix",
        "glob",
    }
    if any(key not in supported_keys for key in match):
        return False

    if "command_prefix" in match:
        if not command_prefix_matches(command_from_envelope(envelope), match.get("command_prefix")):
            return False

    paths = path_values_from_envelope(envelope)
    if "path" in match and not any(path_matches(path, match.get("path")) for path in paths):
        return False
    if "paths" in match and not any(path_matches(path, match.get("paths")) for path in paths):
        return False
    if "path_glob" in match and not any(path_matches(path, match.get("path_glob")) for path in paths):
        return False
    if "path_prefix" in match and not any(path_prefix_matches(path, match.get("path_prefix")) for path in paths):
        return False

    if "fields" in match and not fields_match(envelope, match.get("fields")):
        return False
    if "event_fields" in match and not fields_match(envelope, match.get("event_fields")):
        return False
    if "parameters" in match and not parameter_matches(envelope, match.get("parameters")):
        return False
    if "field" in match:
        field = match.get("field")
        if not isinstance(field, str) or not field.strip():
            return False
        condition = {key: match[key] for key in ["equals", "in", "contains", "exists", "prefix", "glob"] if key in match}
        if not condition or not value_condition_matches(value_at(envelope, field), condition):
            return False

    return True


def strictest_permission(effects: list[str], default_effect: str) -> str:
    for effect in ["deny", "ask", "allow"]:
        if effect in effects:
            return effect
    return default_effect


def shorthand_permission_rule(effect: str, value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str) or "(" not in value or not value.endswith(")"):
        return None
    tool, remainder = value.split("(", 1)
    command_pattern = remainder[:-1].strip()
    if not tool.strip() or not command_pattern:
        return None
    tool_name = tool.strip()
    if tool_name.lower() in {"read", "write", "edit", "multi_edit"}:
        return {
            "effect": effect,
            "tool": tool_name,
            "match": {"path": command_pattern},
        }
    command_prefix = command_pattern[:-1].strip() if command_pattern.endswith("*") else command_pattern
    return {
        "effect": effect,
        "tool": tool_name,
        "match": {"command_prefix": command_prefix},
    }


def normalized_permission_rules(permissions: dict[str, Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    rules = permissions.get("rules")
    if isinstance(rules, list):
        normalized.extend(rule for rule in rules if isinstance(rule, dict))
    for effect in ["allow", "ask", "deny"]:
        shorthand = permissions.get(effect)
        if not isinstance(shorthand, list):
            continue
        for value in shorthand:
            rule = shorthand_permission_rule(effect, value)
            if rule is not None:
                normalized.append(rule)
    return normalized


def tool_input_summary(envelope: dict[str, Any]) -> dict[str, Any]:
    payload = mapping_or_empty(envelope.get("payload"))
    summary: dict[str, Any] = {
        "tool": value_at(envelope, "tool.name"),
        "action": value_at(envelope, "action.name"),
        "command": command_from_envelope(envelope),
        "paths": path_values_from_envelope(envelope),
    }
    for field in ["tool_input", "input", "parameters", "params", "args", "arguments"]:
        value = payload.get(field)
        if is_present(value):
            summary[field] = json_safe(value)
    for key in ["tool", "action", "command", "paths"]:
        if not is_present(summary.get(key)):
            summary.pop(key, None)
    return summary


def evaluate_state_permission(
    docs: dict[str, dict[str, Any]],
    current_state: str,
    envelope: dict[str, Any],
) -> dict[str, Any] | None:
    state = state_by_id(docs, current_state)
    permissions = state.get("permissions") if isinstance(state, dict) else None
    if not isinstance(permissions, dict):
        return None

    default_effect = permissions.get("default")
    if default_effect not in {"allow", "ask", "deny"}:
        return {
            "error": True,
            "reason": "invalid_state_permissions",
            "field": f"states.{current_state}.permissions.default",
            "message": "`permissions.default` 必须显式声明为 `allow`、`ask` 或 `deny`。",
            "suggestion": "修正 Guard Profile（守卫画像）的 state-machine.yaml 后重试。",
        }

    matched_rules: list[dict[str, Any]] = []
    for rule in normalized_permission_rules(permissions):
        if (
            isinstance(rule, dict)
            and rule.get("effect") in {"allow", "ask", "deny"}
            and permission_rule_matches(envelope, rule)
        ):
            matched_rules.append(rule)
    effect = strictest_permission([str(rule["effect"]) for rule in matched_rules], str(default_effect))
    selected_rule = next((rule for rule in matched_rules if rule.get("effect") == effect), {})
    reason = selected_rule.get("reason") if isinstance(selected_rule.get("reason"), str) else f"状态 `{current_state}` 权限结果为 `{effect}`。"
    suggestion = selected_rule.get("suggestion") if isinstance(selected_rule.get("suggestion"), str) else ""
    return {
        "effect": effect,
        "reason": reason,
        "suggestion": suggestion,
        "matched_rules": matched_rules,
        "default": default_effect,
        "tool": value_at(envelope, "tool.name"),
        "command": command_from_envelope(envelope),
        "input_summary": tool_input_summary(envelope),
    }


def permission_output_details(permission: dict[str, Any]) -> dict[str, Any]:
    return {
        "permission": {
            "effect": permission.get("effect"),
            "default": permission.get("default"),
            "tool": permission.get("tool"),
            "command": permission.get("command"),
            "input_summary": permission.get("input_summary", {}),
            "matched_rules": permission.get("matched_rules", []),
        }
    }


def tool_input_hash(envelope: dict[str, Any]) -> str:
    payload = {
        "tool": mapping_or_empty(envelope.get("tool")),
        "action": mapping_or_empty(envelope.get("action")),
        "payload": mapping_or_empty(envelope.get("payload")),
    }
    return stable_hash(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def confirmation_request(
    project: Path,
    profile_id: str,
    subject: dict[str, Any],
    current_state: str,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    input_hash = tool_input_hash(envelope)
    confirmation_id = stable_hash(
        json.dumps(
            {
                "guard_profile_id": profile_id,
                "subject_key_hash": subject["subject_key_hash"],
                "state": current_state,
                "tool": value_at(envelope, "tool.name"),
                "tool_input_hash": input_hash,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    path = project / ".local" / "guard" / "confirmations" / profile_id / subject["subject_key_hash"] / f"{confirmation_id}.json"
    return {
        "confirmation_id": confirmation_id,
        "confirmation_path": str(path),
        "tool_input_hash": input_hash,
    }


def validate_permission_confirmation(
    project: Path,
    profile_id: str,
    subject: dict[str, Any],
    current_state: str,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    request = confirmation_request(project, profile_id, subject, current_state, envelope)
    path = Path(request["confirmation_path"])
    result = {**request, "valid": False, "reason": "confirmation_not_found"}
    if not path.exists():
        return result
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {**result, "reason": "confirmation_invalid_json"}
    if not isinstance(record, dict):
        return {**result, "reason": "confirmation_not_object"}
    expected = {
        "guard_profile_id": profile_id,
        "subject_key_hash": subject["subject_key_hash"],
        "confirmation_id": request["confirmation_id"],
        "state": current_state,
        "tool": value_at(envelope, "tool.name"),
        "tool_input_hash": request["tool_input_hash"],
    }
    for field, expected_value in expected.items():
        if record.get(field) != expected_value:
            return {**result, "reason": f"confirmation_{field}_mismatch", "record": record}
    expires_at = parse_time(record.get("expires_at"))
    if expires_at is None:
        return {**result, "reason": "confirmation_expiry_missing", "record": record}
    if expires_at <= datetime.now(timezone.utc):
        return {**result, "reason": "confirmation_expired", "record": record}
    for field in ["approved_by", "approved_at", "reason"]:
        if not is_present(record.get(field)):
            return {**result, "reason": f"confirmation_{field}_missing", "record": record}
    return {**result, "valid": True, "reason": "confirmation_valid", "record": record}


def condition_matches(envelope: dict[str, Any], condition: dict[str, Any]) -> bool:
    field = condition.get("field")
    if not isinstance(field, str) or not field.strip():
        return False
    if envelope.get("event_type") == "state_completed" and (field == "payload" or field.startswith("payload.")):
        return False
    actual = value_at(envelope, field)
    if "equals" in condition:
        return actual == condition.get("equals")
    if "in" in condition and isinstance(condition.get("in"), list):
        return actual in condition["in"]
    if "contains" in condition:
        expected = condition.get("contains")
        if isinstance(actual, (list, str)):
            return expected in actual
        if isinstance(actual, dict):
            return expected in actual or expected in actual.values()
        return False
    if "exists" in condition:
        return is_present(actual) is bool(condition.get("exists"))
    return False


def transition_conditions_match(transition: dict[str, Any], envelope: dict[str, Any]) -> bool:
    conditions = transition.get("conditions")
    if conditions in (None, []):
        return True
    if not isinstance(conditions, list):
        return False
    for condition in conditions:
        if not isinstance(condition, dict):
            return False
        if not condition_matches(envelope, condition):
            return False
    return True


def guard_points_by_id(docs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    guard_points = docs["guard_points"].get("guard_points")
    if not isinstance(guard_points, list):
        return {}
    return {item["id"]: item for item in guard_points if isinstance(item, dict) and isinstance(item.get("id"), str)}


def transition_required_artifacts(docs: dict[str, dict[str, Any]], transition: dict[str, Any]) -> list[str]:
    required = [item for item in transition.get("required_artifacts", []) if isinstance(item, str)]
    guard_points = guard_points_by_id(docs)
    for guard_point_id in transition.get("guard_points", []):
        guard_point = guard_points.get(guard_point_id)
        if not guard_point:
            continue
        inputs = guard_point.get("inputs")
        artifacts = value_at(inputs, "artifacts") if isinstance(inputs, dict) else None
        if isinstance(artifacts, list):
            required.extend(item for item in artifacts if isinstance(item, str))
    return unique_fields(required)


def event_artifact_present(envelope: dict[str, Any], artifact_id: str) -> bool:
    return artifact_evidence(envelope, {}, Path.cwd(), artifact_id)["present"]


def artifacts_by_id(docs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    artifacts_doc = docs.get("artifacts", {})
    artifacts = artifacts_doc.get("artifacts") if isinstance(artifacts_doc, dict) else None
    if not isinstance(artifacts, list):
        return {}
    return {item["id"]: item for item in artifacts if isinstance(item, dict) and isinstance(item.get("id"), str)}


def render_artifact_path(
    project: Path,
    template: str,
    envelope: dict[str, Any],
    subject: dict[str, Any] | None,
    state: dict[str, Any] | None,
) -> Path:
    values = {
        "guard_profile_id": str(envelope.get("guard_profile_id") or envelope.get("profile_ref") or ""),
        "subject_key_hash": str((subject or {}).get("subject_key_hash") or ""),
        "current_state": str((state or {}).get("current_state") or ""),
        "state_version": str((state or {}).get("state_version") or ""),
        "event_id": str(envelope.get("event_id") or ""),
    }
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", value)
    path = Path(rendered)
    return path if path.is_absolute() else project / path


def artifact_evidence(
    envelope: dict[str, Any],
    docs: dict[str, dict[str, Any]],
    project: Path,
    artifact_id: str,
    subject: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = mapping_or_empty(envelope.get("payload"))
    if envelope.get("event_type") != "state_completed":
        artifacts = payload.get("artifacts")
        if isinstance(artifacts, dict) and is_present(artifacts.get(artifact_id)):
            return {
                "present": True,
                "source": "payload.artifacts",
                "value": artifacts.get(artifact_id),
            }
        if isinstance(artifacts, list):
            for item in artifacts:
                if item == artifact_id:
                    return {"present": True, "source": "payload.artifacts", "value": item}
                if isinstance(item, dict) and item.get("id") == artifact_id and is_present(item.get("value", True)):
                    return {"present": True, "source": "payload.artifacts", "value": item}
        artifact_ids = payload.get("artifact_ids")
        if isinstance(artifact_ids, list) and artifact_id in artifact_ids:
            return {"present": True, "source": "payload.artifact_ids", "value": artifact_id}
        if is_present(payload.get(artifact_id)):
            return {"present": True, "source": f"payload.{artifact_id}", "value": payload.get(artifact_id)}

    artifact_def = artifacts_by_id(docs).get(artifact_id, {})
    artifact_path = artifact_def.get("path")
    if isinstance(artifact_path, str) and artifact_path.strip():
        path = render_artifact_path(project, artifact_path, envelope, subject, state)
        if path.exists():
            evidence = {
                "present": True,
                "source": "artifact.path",
                "value": artifact_id,
                "path": str(path),
                "mtime": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            if not artifact_belongs_to_current_state(artifact_def, evidence, state):
                return {
                    **evidence,
                    "present": False,
                    "reason": "artifact_reuse_denied",
                }
            return evidence

    return {"present": False, "source": "not_found", "value": artifact_id}


def state_entry_time(state: dict[str, Any] | None) -> datetime | None:
    if not isinstance(state, dict):
        return None
    for field in ["current_state_entered_at", "updated_at", "created_at"]:
        parsed = parse_time(state.get(field))
        if parsed is not None:
            return parsed
    return None


def artifact_belongs_to_current_state(
    artifact_def: dict[str, Any],
    evidence: dict[str, Any],
    state: dict[str, Any] | None,
) -> bool:
    reuse_policy = artifact_def.get("reuse_policy", "deny")
    if reuse_policy == "allow":
        return True
    if reuse_policy != "deny":
        return False
    artifact_path = artifact_def.get("path")
    if isinstance(artifact_path, str) and "{state_version}" in artifact_path and is_present((state or {}).get("state_version")):
        return True
    freshness = mapping_or_empty(artifact_def.get("freshness"))
    if freshness.get("scope") != "current_state_entry":
        return False
    artifact_time = parse_time(evidence.get("mtime"))
    entry_time = state_entry_time(state)
    if artifact_time is None or entry_time is None:
        return False
    return artifact_time >= entry_time


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def list_string_value(data: dict[str, Any], field: str) -> list[str]:
    value = value_at(data, field)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def guard_point_artifacts(guard_point: dict[str, Any]) -> list[str]:
    artifacts = []
    artifacts.extend([item for item in guard_point.get("required_artifacts", []) if isinstance(item, str)])
    inputs = guard_point.get("inputs")
    if isinstance(inputs, dict):
        artifacts.extend(list_string_value(inputs, "artifacts"))
    return unique_fields(artifacts)


def guard_point_checks(guard_point: dict[str, Any]) -> list[dict[str, Any]]:
    checks = guard_point.get("checks")
    normalized = [item for item in checks if isinstance(item, dict)] if isinstance(checks, list) else []
    covered_artifacts = {
        check.get("artifact") or check.get("artifact_id")
        for check in normalized
        if check.get("type") in {"artifact_exists", "artifact_freshness"}
    }
    for artifact_id in guard_point_artifacts(guard_point):
        if artifact_id in covered_artifacts:
            continue
        normalized.append(
            {
                "id": f"{artifact_id}_exists",
                "type": "artifact_exists",
                "artifact": artifact_id,
                "failure_reason": f"缺少必需产物 `{artifact_id}`。",
                "fix_hint": f"提供 `{artifact_id}` 产物后重试。",
            }
        )
    return normalized


def guard_point_trigger_matches(guard_point: dict[str, Any], envelope: dict[str, Any], current_state: str) -> bool:
    trigger = guard_point.get("trigger")
    if not isinstance(trigger, dict):
        return True
    events = trigger.get("events") or trigger.get("event_types")
    if isinstance(events, str):
        events = [events]
    if isinstance(events, list) and events and envelope["event_type"] not in events:
        return False
    states = trigger.get("states") or trigger.get("current_states")
    if isinstance(states, str):
        states = [states]
    if isinstance(states, list) and states and current_state not in states:
        return False
    return True


def evaluate_event_field_check(envelope: dict[str, Any], check: dict[str, Any]) -> dict[str, Any]:
    field = check.get("field")
    if not isinstance(field, str) or not field.strip():
        return failed_check(check, "event_field", "缺少要检查的事件字段。", "在 check.field 中写入事件字段路径。")
    if envelope.get("event_type") == "state_completed" and (field == "payload" or field.startswith("payload.")):
        return failed_check(
            check,
            "event_field",
            "`state_completed` 事件不能用 payload（载荷）作为完成证据。",
            "把完成证据写入 artifacts.yaml 声明的产物路径，再重试 state_completed。",
        )
    actual = value_at(envelope, field)
    evidence = {"field": field, "value": actual}
    if "equals" in check:
        expected = check.get("equals")
        passed = actual == expected
        condition = f"{field} == {json_value(expected)}"
    elif "in" in check and isinstance(check.get("in"), list):
        expected_values = check["in"]
        passed = actual in expected_values
        condition = f"{field} in {json_value(expected_values)}"
    elif "contains" in check:
        expected = check.get("contains")
        if isinstance(actual, (list, str)):
            passed = expected in actual
        elif isinstance(actual, dict):
            passed = expected in actual or expected in actual.values()
        else:
            passed = False
        condition = f"{field} contains {json_value(expected)}"
    else:
        passed = is_present(actual)
        condition = f"{field} present"
    return checked_result(check, "event_field", passed, condition, evidence)


def evaluate_state_check(current_state: str, check: dict[str, Any]) -> dict[str, Any]:
    if "allowed_states" in check and isinstance(check.get("allowed_states"), list):
        allowed_states = [item for item in check["allowed_states"] if isinstance(item, str)]
        passed = current_state in allowed_states
        condition = f"current_state in {json_value(allowed_states)}"
    else:
        expected = check.get("current_state") or check.get("state")
        passed = current_state == expected
        condition = f"current_state == {json_value(expected)}"
    return checked_result(check, "state", passed, condition, {"current_state": current_state})


def evaluate_artifact_exists_check(
    envelope: dict[str, Any],
    docs: dict[str, dict[str, Any]],
    project: Path,
    subject: dict[str, Any],
    state: dict[str, Any],
    check: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = check.get("artifact") or check.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return failed_check(check, "artifact_exists", "缺少要检查的产物 ID。", "在 check.artifact 中写入产物 ID。")
    evidence = artifact_evidence(envelope, docs, project, artifact_id, subject, state)
    condition = f"artifact `{artifact_id}` exists"
    return checked_result(check, "artifact_exists", evidence["present"], condition, evidence)


def evidence_time(evidence: dict[str, Any], check: dict[str, Any]) -> datetime | None:
    value = evidence.get("value")
    timestamp_field = check.get("timestamp_field")
    candidates: list[Any] = []
    if isinstance(timestamp_field, str) and isinstance(value, dict):
        candidates.append(value_at(value, timestamp_field))
    if isinstance(value, dict):
        candidates.extend([value.get("updated_at"), value.get("timestamp"), value.get("created_at")])
    candidates.extend([evidence.get("updated_at"), evidence.get("timestamp"), evidence.get("mtime")])
    for candidate in candidates:
        parsed = parse_time(candidate)
        if parsed is not None:
            return parsed
    return None


def evaluate_artifact_freshness_check(
    envelope: dict[str, Any],
    docs: dict[str, dict[str, Any]],
    project: Path,
    subject: dict[str, Any],
    state: dict[str, Any],
    check: dict[str, Any],
) -> dict[str, Any]:
    artifact_id = check.get("artifact") or check.get("artifact_id")
    if not isinstance(artifact_id, str) or not artifact_id.strip():
        return failed_check(check, "artifact_freshness", "缺少要检查的产物 ID。", "在 check.artifact 中写入产物 ID。")
    evidence = artifact_evidence(envelope, docs, project, artifact_id, subject, state)
    max_age_seconds = check.get("max_age_seconds")
    if not isinstance(max_age_seconds, int) or max_age_seconds < 0:
        return failed_check(
            check,
            "artifact_freshness",
            "缺少有效的新鲜度窗口。",
            "在 check.max_age_seconds 中写入非负整数秒数。",
        )
    artifact_time = evidence_time(evidence, check)
    reference_time = parse_time(value_at(envelope, str(check.get("reference_time_field")))) if check.get("reference_time_field") else None
    reference_time = reference_time or parse_time(envelope.get("timestamp")) or datetime.now(timezone.utc)
    age_seconds = None if artifact_time is None else (reference_time - artifact_time).total_seconds()
    evidence = {**evidence, "artifact_time": artifact_time.isoformat().replace("+00:00", "Z") if artifact_time else None, "age_seconds": age_seconds}
    passed = evidence["present"] and age_seconds is not None and age_seconds <= max_age_seconds
    condition = f"artifact `{artifact_id}` age <= {max_age_seconds}s"
    return checked_result(check, "artifact_freshness", passed, condition, evidence)


def confirmation_from_payload(envelope: dict[str, Any], confirmation_id: str) -> dict[str, Any] | None:
    if envelope.get("event_type") == "state_completed":
        return None
    confirmations = mapping_or_empty(envelope.get("payload")).get("confirmations")
    if isinstance(confirmations, dict):
        value = confirmations.get(confirmation_id)
        if isinstance(value, dict):
            return value
        if value is True:
            return {"confirmed": True, "id": confirmation_id}
    if isinstance(confirmations, list):
        for item in confirmations:
            if isinstance(item, dict) and item.get("id") == confirmation_id:
                return item
    return None


def evaluate_human_confirmation_check(
    project: Path,
    profile_id: str,
    subject: dict[str, Any],
    guard_point_id: str,
    envelope: dict[str, Any],
    check: dict[str, Any],
) -> dict[str, Any]:
    confirmation_id = check.get("confirmation_id") or guard_point_id
    if not isinstance(confirmation_id, str) or not confirmation_id.strip():
        return failed_check(
            check,
            "human_confirmation",
            "缺少人工确认记录 ID。",
            "在 check.confirmation_id 中写入人工确认记录 ID。",
        )
    record = confirmation_from_payload(envelope, confirmation_id)
    record_path = project / ".local" / "guard" / "confirmations" / profile_id / subject["subject_key_hash"] / f"{confirmation_id}.json"
    if record is None and record_path.exists():
        try:
            loaded = json.loads(record_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            loaded = None
        if isinstance(loaded, dict):
            record = loaded
    evidence = {"confirmation_id": confirmation_id, "record": record, "record_path": str(record_path)}
    passed = isinstance(record, dict) and record.get("confirmed") is True
    if passed and record.get("guard_profile_id") not in (None, profile_id):
        passed = False
    if passed and record.get("subject_key_hash") not in (None, subject["subject_key_hash"]):
        passed = False
    if passed and record.get("guard_point_id") not in (None, guard_point_id):
        passed = False
    expires_at = parse_time(record.get("expires_at")) if isinstance(record, dict) else None
    if passed and expires_at is not None and expires_at <= datetime.now(timezone.utc):
        passed = False
    condition = f"human confirmation `{confirmation_id}` is valid"
    return checked_result(check, "human_confirmation", passed, condition, evidence)


def failed_check(check: dict[str, Any], check_type: str, reason: str, fix_hint: str) -> dict[str, Any]:
    return {
        "id": check.get("id") or check_type,
        "type": check_type,
        "passed": False,
        "condition": check.get("condition", check_type),
        "evidence": {},
        "failure_reason": check.get("failure_reason") or reason,
        "fix_hint": check.get("fix_hint") or fix_hint,
    }


def checked_result(
    check: dict[str, Any],
    check_type: str,
    passed: bool,
    condition: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": check.get("id") or check_type,
        "type": check_type,
        "passed": passed,
        "condition": condition,
        "evidence": evidence,
        "failure_reason": "" if passed else check.get("failure_reason") or f"未满足条件：{condition}",
        "fix_hint": "" if passed else check.get("fix_hint") or f"满足条件后重试：{condition}",
    }


def evaluate_check(
    project: Path,
    profile_id: str,
    docs: dict[str, dict[str, Any]],
    subject: dict[str, Any],
    current_state: str,
    state: dict[str, Any],
    guard_point_id: str,
    envelope: dict[str, Any],
    check: dict[str, Any],
) -> dict[str, Any]:
    check_type = check.get("type")
    if check_type == "event_field":
        return evaluate_event_field_check(envelope, check)
    if check_type == "state":
        return evaluate_state_check(current_state, check)
    if check_type == "artifact_exists":
        return evaluate_artifact_exists_check(envelope, docs, project, subject, state, check)
    if check_type == "artifact_freshness":
        return evaluate_artifact_freshness_check(envelope, docs, project, subject, state, check)
    if check_type == "human_confirmation":
        return evaluate_human_confirmation_check(project, profile_id, subject, guard_point_id, envelope, check)
    return failed_check(
        check,
        str(check_type or "unknown"),
        f"不支持的检查类型 `{check_type}`。",
        "改用 event_field、state、artifact_exists、artifact_freshness 或 human_confirmation。",
    )


def override_record_path(project: Path, profile_id: str, subject: dict[str, Any], guard_point: dict[str, Any]) -> Path:
    policy = guard_point.get("override_policy") if isinstance(guard_point.get("override_policy"), dict) else {}
    if not policy and isinstance(guard_point.get("override"), dict):
        policy = guard_point["override"]
    template = policy.get("record_path") if isinstance(policy.get("record_path"), str) else None
    relative = template or ".local/guard/overrides/{guard_profile_id}/{subject_key_hash}/{guard_point_id}.json"
    rendered = relative.format(
        guard_profile_id=profile_id,
        subject_key_hash=subject["subject_key_hash"],
        guard_point_id=guard_point["id"],
    )
    path = Path(rendered)
    return path if path.is_absolute() else project / path


def validate_override_record(
    project: Path,
    profile_id: str,
    subject: dict[str, Any],
    guard_point: dict[str, Any],
) -> dict[str, Any]:
    policy = guard_point.get("override_policy") if isinstance(guard_point.get("override_policy"), dict) else {}
    if not policy and isinstance(guard_point.get("override"), dict):
        policy = guard_point["override"]
    allowed = policy.get("allowed") is True
    path = override_record_path(project, profile_id, subject, guard_point)
    result = {"allowed": allowed, "valid": False, "record_path": str(path), "reason": "override_disabled"}
    if not allowed:
        return result
    if not path.exists():
        return {**result, "reason": "override_not_found"}
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {**result, "reason": "override_invalid_json"}
    if not isinstance(record, dict):
        return {**result, "reason": "override_not_object"}
    if record.get("guard_profile_id") != profile_id:
        return {**result, "reason": "override_profile_mismatch", "record": record}
    if record.get("subject_key_hash") != subject["subject_key_hash"]:
        return {**result, "reason": "override_subject_mismatch", "record": record}
    if record.get("guard_point_id") != guard_point["id"]:
        return {**result, "reason": "override_guard_point_mismatch", "record": record}
    expires_at = parse_time(record.get("expires_at"))
    if expires_at is None:
        return {**result, "reason": "override_expiry_missing", "record": record}
    if expires_at <= datetime.now(timezone.utc):
        return {**result, "reason": "override_expired", "record": record}
    if not is_present(record.get("reason")):
        return {**result, "reason": "override_reason_missing", "record": record}
    return {**result, "valid": True, "reason": "override_valid", "record": record}


def execute_guard_point(
    project: Path,
    profile_id: str,
    docs: dict[str, dict[str, Any]],
    subject: dict[str, Any],
    current_state: str,
    state: dict[str, Any],
    envelope: dict[str, Any],
    guard_point: dict[str, Any],
) -> dict[str, Any]:
    if not guard_point_trigger_matches(guard_point, envelope, current_state):
        return {"id": guard_point["id"], "result": "skipped", "checks": [], "override": validate_override_record(project, profile_id, subject, guard_point)}

    checks = guard_point_checks(guard_point)
    check_results = [
        evaluate_check(project, profile_id, docs, subject, current_state, state, guard_point["id"], envelope, check)
        for check in checks
    ]
    failed = [check for check in check_results if not check["passed"]]
    override = validate_override_record(project, profile_id, subject, guard_point)
    if failed and override["valid"]:
        result = "overridden"
    elif failed:
        result = "failed"
    else:
        result = "passed"
    return {
        "id": guard_point["id"],
        "description": guard_point.get("description", ""),
        "result": result,
        "checks": check_results,
        "failed_checks": failed,
        "failure_reason": guard_point.get("failure_reason") or (failed[0]["failure_reason"] if failed else ""),
        "fix_hint": guard_point.get("fix_hint") or (failed[0]["fix_hint"] if failed else ""),
        "missing_conditions": [check["condition"] for check in failed],
        "override": override,
    }


def synthetic_transition_guard_point(
    docs: dict[str, dict[str, Any]],
    transition: dict[str, Any],
    covered_artifacts: set[str],
) -> dict[str, Any] | None:
    missing_from_guard_points = [
        artifact_id
        for artifact_id in transition.get("required_artifacts", [])
        if isinstance(artifact_id, str) and artifact_id not in covered_artifacts
    ]
    if not missing_from_guard_points:
        return None
    return {
        "id": f"{transition.get('id', 'transition')}.required_artifacts",
        "description": "状态转换必需产物检查。",
        "required_artifacts": missing_from_guard_points,
    }


def execute_guard_points(
    project: Path,
    profile_id: str,
    docs: dict[str, dict[str, Any]],
    subject: dict[str, Any],
    current_state: str,
    state: dict[str, Any],
    envelope: dict[str, Any],
    transition: dict[str, Any],
) -> dict[str, Any]:
    guard_points = guard_points_by_id(docs)
    guard_point_items = [
        guard_points[guard_point_id]
        for guard_point_id in transition.get("guard_points", [])
        if guard_point_id in guard_points
    ]
    covered_artifacts: set[str] = set()
    for guard_point in guard_point_items:
        covered_artifacts.update(guard_point_artifacts(guard_point))
        for check in guard_point_checks(guard_point):
            artifact_id = check.get("artifact") or check.get("artifact_id")
            if isinstance(artifact_id, str):
                covered_artifacts.add(artifact_id)
    synthetic = synthetic_transition_guard_point(docs, transition, covered_artifacts)
    if synthetic is not None:
        guard_point_items.append(synthetic)

    results = [
        execute_guard_point(project, profile_id, docs, subject, current_state, state, envelope, guard_point)
        for guard_point in guard_point_items
    ]
    failed = [result for result in results if result["result"] == "failed"]
    if not failed:
        return {"passed": True, "status": "allow", "return_code": 0, "decision": "guard_passed", "guard_results": results}

    missing_conditions: list[str] = []
    fix_suggestions: list[str] = []
    failure_reasons: list[str] = []
    missing_artifacts: list[str] = []
    override_paths: list[str] = []
    override_allowed = False
    for result in failed:
        missing_conditions.extend(result["missing_conditions"])
        if result["fix_hint"]:
            fix_suggestions.append(result["fix_hint"])
        if result["failure_reason"]:
            failure_reasons.append(result["failure_reason"])
        if result["override"]["allowed"]:
            override_allowed = True
            override_paths.append(result["override"]["record_path"])
        for check in result["failed_checks"]:
            if check["type"] in {"artifact_exists", "artifact_freshness"}:
                artifact_id = check["evidence"].get("value")
                if isinstance(artifact_id, str):
                    missing_artifacts.append(artifact_id)
                else:
                    condition = check["condition"]
                    if condition.startswith("artifact `"):
                        missing_artifacts.append(condition.split("`", 2)[1])

    return {
        "passed": False,
        "status": "error",
        "return_code": 1,
        "decision": "guard_failed",
        "guard_results": results,
        "failed_guard_points": [result["id"] for result in failed],
        "failure_reasons": unique_fields(failure_reasons),
        "missing_conditions": unique_fields(missing_conditions),
        "missing_artifacts": unique_fields(missing_artifacts),
        "fix_suggestions": unique_fields(fix_suggestions),
        "override_allowed": override_allowed,
        "override_record_paths": unique_fields(override_paths),
        "override_record_path": override_paths[0] if override_paths else "",
    }


def subject_from_state(state: dict[str, Any]) -> dict[str, Any]:
    subject = mapping_or_empty(state.get("subject"))
    return {
        "identity_fields": subject.get("identity_fields", []),
        "required_fields": subject.get("required_fields", []),
        "optional_fields": subject.get("optional_fields", []),
        "values": subject.get("values", {}),
        "subject_key": state.get("subject_key"),
        "subject_key_hash": state.get("subject_key_hash"),
    }


def validate_latest_brief(
    project: Path,
    profile_id: str,
    subject_hash: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if payload.get("guard_profile_id") != profile_id:
        return {"valid": False, "status": "stale_brief", "reason": "profile_mismatch"}
    if payload.get("subject_key_hash") != subject_hash:
        return {"valid": False, "status": "stale_brief", "reason": "subject_mismatch"}

    expires_at = parse_time(payload.get("expires_at"))
    if expires_at is None:
        return {"valid": False, "status": "expired_brief", "reason": "missing_or_invalid_expires_at"}
    if expires_at <= datetime.now(timezone.utc):
        return {"valid": False, "status": "expired_brief", "reason": "expires_at_elapsed"}

    state_path = state_root(project, profile_id) / subject_hash / "state.json"
    state = load_state(state_path) if state_path.exists() else None
    if state is None:
        return {"valid": False, "status": "stale_brief", "reason": "state_not_found", "state_path": str(state_path)}
    if state.get("subject_key_hash") != subject_hash:
        return {"valid": False, "status": "stale_brief", "reason": "state_subject_mismatch"}
    matches = find_matching_instances(project, profile_id, subject_from_state(state))
    if len(matches) != 1 or matches[0][0] != state_path:
        return {
            "valid": False,
            "status": "ambiguous_subject",
            "reason": "guard_instance_not_unique",
            "candidate_count": len(matches),
        }
    if payload.get("state_version") != state.get("state_version"):
        return {
            "valid": False,
            "status": "stale_brief",
            "reason": "state_version_mismatch",
            "brief_state_version": payload.get("state_version"),
            "current_state_version": state.get("state_version"),
        }
    return {"valid": True}


def brief_injection_envelope(profile_id: str, subject_hash: str, session_id: str | None) -> dict[str, Any]:
    return {
        "event_id": uuid.uuid4().hex,
        "event_type": "guard_brief_injection",
        "completed_state_id": None,
        "source": "guard-runtime",
        "timestamp": now_iso(),
        "guard_profile_id": profile_id,
        "profile_ref": profile_id,
        "context": {"session_id": session_id} if session_id else {},
        "subject": {"subject_key_hash": subject_hash},
        "payload": {},
        "tool": {},
        "action": {},
        "hook": {},
        "raw_event_summary": "brief injection validation",
        "raw_event_path": "",
    }


def advance_state(
    state_path: Path,
    state: dict[str, Any],
    transition: dict[str, Any],
    run_id: str,
    event_id: str,
    audit_path: Path,
) -> dict[str, Any]:
    previous = state.get("current_state")
    version = int(state.get("state_version", 0)) + 1
    entered_at = now_iso()
    state["current_state"] = transition["to"]
    state["state_version"] = version
    state["updated_at"] = entered_at
    state["current_state_entered_at"] = entered_at
    state["last_run_id"] = run_id
    state["last_event_id"] = event_id
    state["last_transition_id"] = transition.get("id")
    state["last_audit_path"] = str(audit_path)
    state["previous_state"] = previous
    write_json(state_path, state)
    return state


def run_event(args: argparse.Namespace) -> int:
    project = project_root()
    event_path = Path(args.event).resolve()
    run_id = uuid.uuid4().hex

    try:
        raw_event = read_json_file(event_path, "--event")
        envelope = normalize_event(raw_event, event_path)
    except ValueError as exc:
        print_lines({"status": "error", "reason": exc})
        return 2

    profile_id = envelope["guard_profile_id"]
    profile = profile_dir(project, profile_id)
    if not profile.exists():
        print_lines({"status": "error", "reason": "profile_not_found", "guard_profile_id": profile_id})
        return 2

    try:
        docs = load_profile_documents(profile)
    except ValueError as exc:
        print_lines({"status": "error", "reason": exc})
        return 2

    subject, missing, failure_reason = resolve_subject(docs, envelope)
    if subject is None:
        if is_hook_event(envelope):
            print_lines(
                {
                    "status": "allow",
                    "decision": "ignored",
                    "reason": "no_guard_instance",
                    "guard_profile_id": profile_id,
                }
            )
            return 0
        fix_suggestions = subject_resolution_fix_suggestions(failure_reason, missing)
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "no_subject_match",
            envelope,
            {"reason": failure_reason, "missing_fields": missing, "fix_suggestions": fix_suggestions},
        )
        print_lines(
            {
                "status": "no_subject_match",
                "guard_profile_id": profile_id,
                "reason": failure_reason,
                "missing_fields": missing,
                "fix_suggestions": fix_suggestions,
                "audit_path": audit_path,
            }
        )
        return 0

    if is_hook_event(envelope):
        hook_matches = find_matching_instances(project, profile_id, subject)
        if len(hook_matches) != 1:
            print_lines(
                {
                    "status": "allow",
                    "decision": "ignored",
                    "reason": "no_guard_instance",
                    "guard_profile_id": profile_id,
                    "subject_key_hash": subject["subject_key_hash"],
                }
            )
            return 0

    lock = acquire_subject_lock(project, profile_id, subject["subject_key_hash"], lock_timeout_seconds(docs))
    if not lock["acquired"]:
        audit_path = write_lock_timeout(project, profile_id, run_id, envelope, subject, lock)
        print_lines(
            {
                "status": "lock_timeout",
                "guard_profile_id": profile_id,
                "subject_key_hash": subject["subject_key_hash"],
                "lock_path": lock["path"],
                "audit_path": audit_path,
            }
        )
        return 1
    atexit.register(release_subject_lock, lock)

    matches = find_matching_instances(project, profile_id, subject)
    if not matches:
        fix_suggestions = subject_resolution_fix_suggestions("instance_not_found")
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "no_subject_match",
            envelope,
            {
                "reason": "instance_not_found",
                "subject_key": subject["subject_key"],
                "subject_key_hash": subject["subject_key_hash"],
                "fix_suggestions": fix_suggestions,
            },
        )
        print_lines(
            {
                "status": "no_subject_match",
                "guard_profile_id": profile_id,
                "reason": "instance_not_found",
                "subject_key_hash": subject["subject_key_hash"],
                "fix_suggestions": fix_suggestions,
                "audit_path": audit_path,
            }
        )
        release_subject_lock(lock)
        return 0

    if len(matches) > 1:
        fix_suggestions = subject_resolution_fix_suggestions("ambiguous_subject")
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "ambiguous_subject",
            envelope,
            {
                "subject_key": subject["subject_key"],
                "subject_key_hash": subject["subject_key_hash"],
                "candidate_state_paths": [str(path) for path, _state in matches],
                "fix_suggestions": fix_suggestions,
            },
        )
        print_lines(
            {
                "status": "ambiguous_subject",
                "guard_profile_id": profile_id,
                "subject_key_hash": subject["subject_key_hash"],
                "candidate_count": len(matches),
                "fix_suggestions": fix_suggestions,
                "audit_path": audit_path,
            }
        )
        release_subject_lock(lock)
        return 0

    state_path, state = matches[0]
    current_state = str(state.get("current_state", ""))

    if envelope["event_type"] != "state_completed" and is_present(value_at(envelope, "tool.name")):
        permission = evaluate_state_permission(docs, current_state, envelope)
        if permission is not None:
            if permission.get("error") is True:
                audit_path = write_audit(
                    project,
                    profile_id,
                    run_id,
                    "error",
                    envelope,
                    {
                        "decision": "failed",
                        "reason": permission["reason"],
                        "current_state": current_state,
                        "state_version": state.get("state_version"),
                        "permission": permission,
                    },
                )
                print_lines(
                    {
                        "status": "error",
                        "decision": "failed",
                        "guard_profile_id": profile_id,
                        "state": current_state,
                        "state_version": state.get("state_version"),
                        "reason": permission["reason"],
                        "field": permission.get("field", ""),
                        "suggestion": permission.get("suggestion", ""),
                        "audit_path": audit_path,
                    }
                )
                release_subject_lock(lock)
                return 1
            effect = permission["effect"]
            confirmation_validation: dict[str, Any] = {}
            if effect == "ask":
                confirmation_validation = validate_permission_confirmation(project, profile_id, subject, current_state, envelope)
                if confirmation_validation["valid"]:
                    effect = "allow"
                    permission = {
                        **permission,
                        "effect": "allow",
                        "original_effect": "ask",
                        "reason": "confirmation_valid",
                        "confirmation": confirmation_validation,
                    }
            decision = {
                "deny": "denied",
                "ask": "confirmation_required",
                "allow": "guard_passed",
            }[effect]
            confirmation = (
                confirmation_validation or confirmation_request(project, profile_id, subject, current_state, envelope)
                if effect == "ask"
                else {}
            )
            confirmation_output = {
                key: confirmation[key]
                for key in ["confirmation_id", "confirmation_path", "tool_input_hash"]
                if key in confirmation
            }
            audit_path = write_audit(
                project,
                profile_id,
                run_id,
                effect,
                envelope,
                {
                    "decision": decision,
                    "current_state": current_state,
                    "state_version": state.get("state_version"),
                    "permission": permission,
                    "confirmation": confirmation_validation,
                    **confirmation,
                },
            )
            brief_paths: dict[str, Any] = {}
            if effect == "deny":
                brief_paths = write_latest_brief(
                    project,
                    profile_id,
                    run_id,
                    subject_from_state(state),
                    state,
                    docs,
                    audit_path,
                    recent_denial_reasons=[str(permission["reason"])],
                )
            output = {
                "status": effect,
                "decision": decision,
                "guard_profile_id": profile_id,
                "state": current_state,
                "state_version": state.get("state_version"),
                "reason": permission["reason"],
                "suggestion": permission["suggestion"],
                "audit_path": audit_path,
                "details": permission_output_details(permission),
                **confirmation_output,
            }
            if brief_paths:
                output["brief_path"] = brief_paths["brief_path"]
                output["brief_hash"] = brief_paths["brief_hash"]
            print_lines(output)
            release_subject_lock(lock)
            return 0 if effect == "allow" else 1

    if envelope["event_type"] != "state_completed":
        print_lines(
            {
                "status": "allow",
                "decision": "ignored",
                "reason": "non_state_completed_event",
                "guard_profile_id": profile_id,
                "state": current_state,
                "state_version": state.get("state_version"),
            }
        )
        release_subject_lock(lock)
        return 0

    if is_hook_state_completed_event(envelope):
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "error",
            envelope,
            {
                "decision": "failed",
                "reason": "hook_state_completed_forbidden",
                "current_state": current_state,
                "state_version": state.get("state_version"),
                "hook": mapping_or_empty(envelope.get("hook")),
                "source": envelope.get("source"),
            },
        )
        print_lines(
            {
                "status": "error",
                "decision": "failed",
                "reason": "hook_state_completed_forbidden",
                "guard_profile_id": profile_id,
                "state": current_state,
                "state_version": state.get("state_version"),
                "audit_path": audit_path,
            }
        )
        release_subject_lock(lock)
        return 1

    terminal_states = docs["state_machine"].get("terminal_states")
    if isinstance(terminal_states, list) and current_state in terminal_states:
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "error",
            envelope,
            {
                "decision": "failed",
                "reason": "terminal_state_completed",
                "current_state": current_state,
                "state_version": state.get("state_version"),
            },
        )
        print_lines(
            {
                "status": "error",
                "decision": "failed",
                "reason": "terminal_state_completed",
                "guard_profile_id": profile_id,
                "state": current_state,
                "state_version": state.get("state_version"),
                "audit_path": audit_path,
            }
        )
        release_subject_lock(lock)
        return 1

    completed_state_id = envelope.get("completed_state_id")
    if completed_state_id != current_state:
        reason = "completed_state_missing" if not isinstance(completed_state_id, str) or not completed_state_id else "completed_state_mismatch"
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "error",
            envelope,
            {
                "decision": "failed",
                "reason": reason,
                "completed_state_id": completed_state_id,
                "current_state": current_state,
                "state_version": state.get("state_version"),
            },
        )
        print_lines(
            {
                "status": "error",
                "decision": "failed",
                "reason": reason,
                "guard_profile_id": profile_id,
                "state": current_state,
                "state_version": state.get("state_version"),
                "audit_path": audit_path,
            }
        )
        release_subject_lock(lock)
        return 1

    matched_transitions = transitions_for_state(docs, current_state, envelope)

    if not matched_transitions:
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            "error",
            envelope,
            {
                "decision": "failed",
                "reason": "invalid_state_machine_transition",
                "current_state": current_state,
                "state_version": state.get("state_version"),
                "event_type": envelope["event_type"],
                "matching_transitions": [],
            },
        )
        print_lines(
            {
                "status": "error",
                "decision": "failed",
                "reason": "invalid_state_machine_transition",
                "guard_profile_id": profile_id,
                "state": current_state,
                "state_version": state.get("state_version"),
                "audit_path": audit_path,
            }
        )
        release_subject_lock(lock)
        return 1

    guard_outcome: dict[str, Any] | None = None
    if len(matched_transitions) > 1:
        transition_outcomes: list[dict[str, Any]] = []
        passing_transitions: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for candidate in matched_transitions:
            candidate_outcome = execute_guard_points(project, profile_id, docs, subject, current_state, state, envelope, candidate)
            transition_outcomes.append(
                {
                    "transition_id": candidate.get("id"),
                    "passed": candidate_outcome["passed"],
                    "decision": candidate_outcome["decision"],
                    "failed_guard_points": candidate_outcome.get("failed_guard_points", []),
                    "missing_artifacts": candidate_outcome.get("missing_artifacts", []),
                }
            )
            if candidate_outcome["passed"]:
                passing_transitions.append((candidate, candidate_outcome))
        if len(passing_transitions) == 1:
            transition, guard_outcome = passing_transitions[0]
        else:
            reason = "ambiguous_transition" if len(passing_transitions) > 1 else "invalid_state_machine_transition"
            matched_ids = [transition.get("id") for transition, _outcome in passing_transitions]
            audit_path = write_audit(
                project,
                profile_id,
                run_id,
                "error",
                envelope,
                {
                    "decision": "failed",
                    "reason": reason,
                    "current_state": current_state,
                    "state_version": state.get("state_version"),
                    "event_type": envelope["event_type"],
                    "matching_transitions": matched_ids,
                    "candidate_results": transition_outcomes,
                },
            )
            print_lines(
                {
                    "status": "error",
                    "decision": "failed",
                    "reason": reason,
                    "guard_profile_id": profile_id,
                    "state": current_state,
                    "state_version": state.get("state_version"),
                    "transition_count": len(matched_ids),
                    "audit_path": audit_path,
                }
            )
            release_subject_lock(lock)
            return 1
    else:
        transition = matched_transitions[0]

    if guard_outcome is None:
        guard_outcome = execute_guard_points(project, profile_id, docs, subject, current_state, state, envelope, transition)

    if not guard_outcome["passed"]:
        audit_path = write_audit(
            project,
            profile_id,
            run_id,
            guard_outcome["status"],
            envelope,
            {
                "decision": guard_outcome["decision"],
                "transition": transition,
                "current_state": current_state,
                "state_version": state.get("state_version"),
                "failed_guard_points": guard_outcome["failed_guard_points"],
                "failure_reasons": guard_outcome["failure_reasons"],
                "missing_conditions": guard_outcome["missing_conditions"],
                "missing_artifacts": guard_outcome["missing_artifacts"],
                "fix_suggestions": guard_outcome["fix_suggestions"],
                "override_allowed": guard_outcome["override_allowed"],
                "override_record_paths": guard_outcome["override_record_paths"],
                "guard_results": guard_outcome["guard_results"],
            },
        )
        brief_paths = write_latest_brief(
            project,
            profile_id,
            run_id,
            subject_from_state(state),
            state,
            docs,
            audit_path,
            recent_denial_reasons=guard_outcome["failure_reasons"],
            missing_artifacts=guard_outcome["missing_artifacts"],
        )
        output = {
            "status": guard_outcome["status"],
            "decision": guard_outcome["decision"],
            "guard_profile_id": profile_id,
            "transition_id": transition.get("id"),
            "state": current_state,
            "state_version": state.get("state_version"),
            "failed_guard_points": guard_outcome["failed_guard_points"],
            "failure_reasons": guard_outcome["failure_reasons"],
            "missing_conditions": guard_outcome["missing_conditions"],
            "fix_suggestions": guard_outcome["fix_suggestions"],
            "override_allowed": guard_outcome["override_allowed"],
            "override_record_path": guard_outcome["override_record_path"],
            "audit_path": audit_path,
        }
        output["brief_path"] = brief_paths["brief_path"]
        output["brief_hash"] = brief_paths["brief_hash"]
        if guard_outcome["missing_artifacts"]:
            output["missing_artifacts"] = guard_outcome["missing_artifacts"]
        print_lines(output)
        release_subject_lock(lock)
        return guard_outcome["return_code"]

    audit_path = run_dir(project, profile_id, run_id) / "audit.json"
    previous_state = current_state
    state = advance_state(state_path, state, transition, run_id, envelope["event_id"], audit_path)
    audit_path = write_audit(
        project,
        profile_id,
        run_id,
        "allow",
        envelope,
        {
            "decision": "guard_passed",
            "transition": transition,
            "state_path": str(state_path),
            "subject_key": subject["subject_key"],
            "subject_key_hash": subject["subject_key_hash"],
            "state_change": {
                "from": previous_state,
                "to": state["current_state"],
                "version": state["state_version"],
            },
            "guard_results": guard_outcome["guard_results"],
        },
    )
    brief_paths = write_latest_brief(
        project,
        profile_id,
        run_id,
        subject_from_state(state),
        state,
        docs,
        audit_path,
    )
    print_lines(
        {
            "status": "allow",
            "decision": "guard_passed",
            "guard_profile_id": profile_id,
            "subject_key_hash": subject["subject_key_hash"],
            "transition_id": transition.get("id"),
            "from_state": previous_state,
            "to_state": state["current_state"],
            "state_version": state["state_version"],
            "state_path": state_path,
            "audit_path": audit_path,
            "brief_input_path": brief_paths["brief_input_path"],
            "brief_path": brief_paths["brief_path"],
            "brief_hash": brief_paths["brief_hash"],
        }
    )
    release_subject_lock(lock)
    return 0


def read_brief(args: argparse.Namespace) -> int:
    project = project_root()
    try:
        profile_id = validate_profile_id(args.profile)
    except ValueError as exc:
        print_lines({"status": "error", "reason": exc})
        return 2
    path = project / ".local" / "guard" / "latest" / profile_id / args.subject / "brief.json"
    if not path.exists():
        print_lines({"status": "not_found", "brief_path": path})
        return 1
    try:
        payload = read_json_file(path, "latest Guard Brief（最新守卫简报）")
    except ValueError as exc:
        print_lines({"status": "error", "reason": exc})
        return 2
    validation = validate_latest_brief(project, profile_id, args.subject, payload)
    if not validation["valid"]:
        output = dict(validation)
        if args.session:
            audit_path = write_audit(
                project,
                profile_id,
                uuid.uuid4().hex,
                str(validation["status"]),
                brief_injection_envelope(profile_id, args.subject, args.session),
                {
                    "decision": default_decision(str(validation["status"])),
                    "reason": validation.get("reason", ""),
                    "subject_key_hash": args.subject,
                    "validation": validation,
                },
            )
            output["audit_path"] = audit_path
        print(json.dumps(output_envelope(output), ensure_ascii=False, indent=2))
        return 1
    injection: dict[str, Any] | None = None
    if args.session:
        try:
            context = read_json_arg(args.context_json, "--context-json")
        except ValueError as exc:
            print_lines({"status": "error", "reason": exc})
            return 2
        injection = record_brief_injection(project, profile_id, args.subject, args.session, payload, context)
    if args.format == "text":
        if injection and injection["already_injected"]:
            return 0
        print(str(payload.get("brief_text", "")).rstrip())
        return 0
    status = "ok"
    if injection:
        status = "already_injected" if injection["already_injected"] else "injectable"
    print(json.dumps(output_envelope({"status": status, **(injection or {}), **payload}), ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="运行项目级 Guard Runtime（守卫运行时）。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    activate = subparsers.add_parser("activate", help="显式激活 Guard Profile（守卫画像）。")
    activate.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    activate.add_argument("--scope", default="current_context", help="激活范围")
    activate.add_argument("--source", default="manual", help="激活来源")
    activate.add_argument("--context-json", help="当前上下文字段 JSON（JSON 格式）")
    activate.add_argument("--subject-json", help="可选 Subject（主体）输入 JSON（JSON 格式）")

    run = subparsers.add_parser("run", help="处理标准事件 envelope（信封）。")
    run.add_argument("--event", required=True, help="标准事件文件")

    brief = subparsers.add_parser("brief", help="读取 latest Guard Brief（最新守卫简报）。")
    brief.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    brief.add_argument("--subject", required=True, help="subject-key-hash（主体键哈希）")
    brief.add_argument("--format", choices=["json", "text"], default="json", help="输出格式")
    brief.add_argument("--session", help="Codex session（Codex 会话）或调用上下文 ID，用于 brief_hash 去重")
    brief.add_argument("--context-json", help="可选调用上下文字段 JSON（JSON 格式），写入注入记录")

    args = parser.parse_args(argv)
    if args.command == "activate":
        return activate_guard(args)
    if args.command == "run":
        return run_event(args)
    if args.command == "brief":
        return read_brief(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
