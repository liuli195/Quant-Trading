"""Hook（钩子）事件到标准 Guard envelope（信封）的适配器。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import yaml


CODEX_EVENT_TYPES = {
    "UserPromptSubmit": "codex.user_prompt_submit",
    "SubagentStart": "codex.subagent_start",
    "SubagentStop": "codex.subagent_stop",
    "PreToolUse": "codex.pre_tool_use",
    "PostToolUse": "codex.post_tool_use",
}

PAYLOAD_TOOL_FIELDS = {
    "command",
    "cmd",
    "path",
    "paths",
    "file",
    "files",
    "file_path",
    "file_paths",
    "args",
    "arguments",
    "cwd",
}

TOOL_INPUT_CONTAINERS = {"tool_input", "input", "parameters", "params"}
PARAMETER_FIELDS = PAYLOAD_TOOL_FIELDS | {
    "pattern",
    "query",
    "regex",
    "glob",
    "selector",
    "target",
    "name",
    "key",
    "mode",
    "operation",
}
CONTEXT_FIELDS = {
    "scope",
    "repo",
    "repository",
    "repository_id",
    "worktree",
    "branch",
    "pr_number",
    "pull_request",
    "pull_request_number",
    "agent_id",
    "session_id",
    "task_id",
    "object_type",
    "object_id",
    "target_id",
    "target_object_id",
    "execution_context_id",
    "external_system_id",
    "issue",
    "issue_number",
    "project_id",
    "workflow_id",
    "run_id",
}
MAX_STRING_VALUE_LENGTH = 500


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json_text(text: str, label: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} 不是有效 JSON（JSON 格式）：{exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{label} 顶层必须是 JSON object（JSON 对象）。")
    return data


def load_payload(path: Path | None) -> dict[str, Any]:
    if path is not None:
        return load_json_text(path.read_text(encoding="utf-8"), str(path))
    return load_json_text(sys.stdin.read(), "stdin")


def filtered_tool_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {key: safe_parameter_value(value[key]) for key in PAYLOAD_TOOL_FIELDS if key in value}


def safe_parameter_value(value: Any) -> Any:
    if isinstance(value, str):
        return value[:MAX_STRING_VALUE_LENGTH]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [safe_parameter_value(item) for item in value[:20]]
    if isinstance(value, dict):
        return {
            key: safe_parameter_value(item)
            for key, item in value.items()
            if isinstance(key, str) and key in PARAMETER_FIELDS
        }
    return str(value)[:MAX_STRING_VALUE_LENGTH]


def filtered_parameter_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: safe_parameter_value(item)
        for key, item in value.items()
        if isinstance(key, str) and key in PARAMETER_FIELDS
    }


def filtered_context_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: safe_parameter_value(item)
        for key, item in value.items()
        if isinstance(key, str) and key in CONTEXT_FIELDS
    }


def add_repo_context_summary(context: dict[str, Any], raw_value: Any, prefix: str) -> None:
    summary = remote_url_summary(str(raw_value or ""), preserve_plain_name=True)
    context.pop(prefix, None)
    if summary.get("url_hash"):
        context[f"{prefix}_url_hash"] = summary["url_hash"]
    if summary.get("host"):
        context[f"{prefix}_host"] = summary["host"]
    if summary.get("path"):
        context[f"{prefix}_path"] = summary["path"]
    if summary.get("name"):
        context[prefix] = summary["name"]
    if summary.get("host") or summary.get("path"):
        context[prefix] = f"{summary.get('host', '')}{summary.get('path', '')}"[:MAX_STRING_VALUE_LENGTH]


def list_value(data: dict[str, Any], dotted_path: str) -> list[str]:
    current: Any = data
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return []
        current = current[part]
    return [item for item in current if isinstance(item, str)] if isinstance(current, list) else []


def profile_subject_fields(project: Path, profile_id: str) -> set[str]:
    path = profile_dir(project, profile_id) / "subject-resolver.yaml"
    if not path.exists():
        return set(CONTEXT_FIELDS)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return set(CONTEXT_FIELDS)
    if not isinstance(data, dict):
        return set(CONTEXT_FIELDS)
    fields: set[str] = set(CONTEXT_FIELDS)
    for field in (
        list_value(data, "subject.identity_fields")
        + list_value(data, "subject.required_fields")
        + list_value(data, "subject.optional_fields")
    ):
        if field.startswith("subject."):
            fields.add(field.split(".", 1)[1])
    return fields


def filtered_subject_mapping(project: Path, profile_id: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    allowed = profile_subject_fields(project, profile_id)
    return {
        key: safe_parameter_value(item)
        for key, item in value.items()
        if isinstance(key, str) and key in allowed
    }


def codex_runtime_payload(payload: dict[str, Any]) -> dict[str, Any]:
    runtime_payload = filtered_tool_mapping(payload)
    for nested_key in TOOL_INPUT_CONTAINERS:
        nested = filtered_parameter_mapping(payload.get(nested_key))
        if nested:
            runtime_payload[nested_key] = nested
    return runtime_payload


def subject_from_payload(project: Path, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    return filtered_subject_mapping(project, profile_id, payload.get("subject"))


def tool_name_from_payload(payload: dict[str, Any]) -> str:
    tool_name = payload.get("tool_name")
    if isinstance(tool_name, str):
        return tool_name[:MAX_STRING_VALUE_LENGTH]
    tool = payload.get("tool")
    if isinstance(tool, str):
        return tool[:MAX_STRING_VALUE_LENGTH]
    if isinstance(tool, dict) and isinstance(tool.get("name"), str):
        return tool["name"][:MAX_STRING_VALUE_LENGTH]
    return ""


def profile_dir(project: Path, profile_id: str) -> Path:
    return project / ".agents" / "guards" / profile_id


def load_hook_bindings(project: Path, profile_id: str) -> list[dict[str, Any]]:
    path = profile_dir(project, profile_id) / "hook-bindings.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return []
    bindings = data.get("hook_bindings")
    if not isinstance(bindings, list):
        return []
    return [binding for binding in bindings if isinstance(binding, dict)]


def binding_trigger_values(binding: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for field in ["trigger_event", "codex_event", "git_event", "hook_event"]:
        value = binding.get(field)
        if isinstance(value, str):
            values.add(value)
    trigger = binding.get("trigger")
    if isinstance(trigger, dict):
        for field in ["event", "name", "type"]:
            value = trigger.get(field)
            if isinstance(value, str):
                values.add(value)
    trigger_events = binding.get("trigger_events")
    if isinstance(trigger_events, list):
        values.update(value for value in trigger_events if isinstance(value, str))
    return values


def matching_binding(
    project: Path,
    profile_id: str,
    source: str,
    trigger_event: str,
) -> dict[str, Any] | None:
    for binding in load_hook_bindings(project, profile_id):
        if binding.get("source") != source:
            continue
        triggers = binding_trigger_values(binding)
        if trigger_event in triggers:
            return binding
    return None


def mapped_event_type(
    project: Path,
    profile_id: str,
    source: str,
    trigger_event: str,
    default_event_type: str,
) -> tuple[str, str | None]:
    binding = matching_binding(project, profile_id, source, trigger_event)
    if binding is None:
        return default_event_type, None
    event_type = binding.get("event_type")
    if source in {"codex", "git"} and event_type == "state_completed":
        return default_event_type, binding.get("id")
    return event_type if isinstance(event_type, str) and event_type else default_event_type, binding.get("id")


def git_value(project: Path, args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-C", str(project), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def context_from_payload(project: Path, payload: dict[str, Any]) -> dict[str, Any]:
    payload_context = filtered_context_mapping(payload.get("context"))
    session_id = (
        payload.get("session_id")
        or payload_context.get("session_id")
        or os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("AGENT_SESSION_ID")
        or os.environ.get("CLAUDE_SESSION_ID")
        or ""
    )
    context = dict(payload_context)
    context["session_id"] = safe_parameter_value(context.get("session_id") or session_id)
    add_repo_context_summary(context, context.get("repo") or git_value(project, ["config", "--get", "remote.origin.url"]), "repo")
    if context.get("repository"):
        add_repo_context_summary(context, context.get("repository"), "repository")
    context["worktree"] = safe_parameter_value(context.get("worktree") or str(project.resolve()))
    context["branch"] = safe_parameter_value(context.get("branch") or git_value(project, ["branch", "--show-current"]))
    return context


def write_event_file(project: Path, profile_id: str, envelope: dict[str, Any], output: Path | None) -> Path:
    if output is None:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", prefix="agent-guard-event-", delete=False)
        with handle:
            json.dump(envelope, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return Path(handle.name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def run_runtime(project: Path, event_path: Path) -> tuple[int, str]:
    runner = project / ".agents" / "guard-runtime" / "guard_runner.py"
    if not runner.exists():
        print(f"status: runtime_missing\nexpected_runner: {runner}", file=sys.stderr)
        return 2, ""
    completed = subprocess.run(
        [sys.executable, str(runner), "run", "--event", str(event_path)],
        cwd=project,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode, completed.stdout


def cleanup_event_file(event_path: Path) -> None:
    try:
        event_path.unlink()
    except FileNotFoundError:
        pass


def maybe_print_or_run(args: argparse.Namespace, envelope: dict[str, Any]) -> int:
    if args.print_envelope:
        print(json.dumps(envelope, ensure_ascii=False, indent=2))
        return 0
    event_path = write_event_file(args.project, args.profile, envelope, args.out)
    return_code, runtime_stdout = run_runtime(args.project, event_path)
    if args.out is None:
        cleanup_event_file(event_path)
    return return_code


def build_codex_envelope(args: argparse.Namespace) -> dict[str, Any]:
    payload = load_payload(args.payload_file)
    default_event_type = CODEX_EVENT_TYPES.get(args.codex_event, f"codex.{args.codex_event.lower()}")
    event_type, binding_id = mapped_event_type(
        args.project,
        args.profile,
        "codex",
        args.codex_event,
        default_event_type,
    )
    context = context_from_payload(args.project, payload)
    tool_name = tool_name_from_payload(payload)
    if not tool_name and args.codex_event == "SubagentStart":
        tool_name = "codex.subagent"
    return {
        "event_id": payload.get("event_id") or uuid.uuid4().hex,
        "event_type": event_type,
        "source": "codex",
        "timestamp": payload.get("timestamp") or now_iso(),
        "guard_profile_id": args.profile,
        "context": context,
        "subject": subject_from_payload(args.project, args.profile, payload),
        "payload": codex_runtime_payload(payload),
        "tool": {"name": tool_name},
        "action": {"name": args.codex_event},
        "raw_event_summary": f"Codex lifecycle hook（生命周期钩子）：{args.codex_event}",
        "hook": {
            "source": "codex",
            "trigger_event": args.codex_event,
            "binding_id": binding_id,
        },
    }


def parse_pre_push_refs(stdin_text: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for line in stdin_text.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        refs.append(
            {
                "local_ref": parts[0],
                "local_sha": parts[1],
                "remote_ref": parts[2],
                "remote_sha": parts[3],
            }
        )
    return refs


def remote_url_summary(remote_url: str, preserve_plain_name: bool = False) -> dict[str, Any]:
    if not remote_url:
        return {}
    summary = {"url_hash": hashlib.sha256(remote_url.encode("utf-8")).hexdigest()}
    parsed = urlsplit(remote_url)
    if parsed.scheme and parsed.hostname:
        summary["scheme"] = parsed.scheme
        summary["host"] = parsed.hostname
        summary["path"] = parsed.path[:MAX_STRING_VALUE_LENGTH]
        return summary
    if "@" in remote_url and ":" in remote_url.rsplit("@", 1)[-1]:
        host_path = remote_url.rsplit("@", 1)[-1]
        host, path = host_path.split(":", 1)
        summary["host"] = host[:MAX_STRING_VALUE_LENGTH]
        summary["path"] = path[:MAX_STRING_VALUE_LENGTH]
        return summary
    if preserve_plain_name and "@" not in remote_url and "://" not in remote_url:
        summary["name"] = remote_url[:MAX_STRING_VALUE_LENGTH]
    return summary


def build_git_pre_push_envelope(args: argparse.Namespace) -> dict[str, Any]:
    refs = parse_pre_push_refs(sys.stdin.read())
    event_type, binding_id = mapped_event_type(args.project, args.profile, "git", "pre-push", "git.pre_push")
    payload = {
        "git": {
            "hook": "pre-push",
            "remote_name": args.remote_name,
            "remote": remote_url_summary(args.remote_url),
            "refs": refs,
        }
    }
    return {
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "source": "git",
        "timestamp": now_iso(),
        "guard_profile_id": args.profile,
        "context": context_from_payload(args.project, {}),
        "subject": {},
        "payload": payload,
        "tool": {"name": "git"},
        "action": {"name": "pre_push"},
        "raw_event_summary": "Git pre-push hook（Git 推送前钩子）。",
        "hook": {
            "source": "git",
            "trigger_event": "pre-push",
            "binding_id": binding_id,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="把 Hook（钩子）输入转换为标准 Guard envelope（信封）。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    codex = subparsers.add_parser("codex", help="适配 Codex lifecycle hook（生命周期钩子）。")
    codex.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录")
    codex.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    codex.add_argument("--codex-event", required=True, help="Codex hook（钩子）事件名")
    codex.add_argument("--payload-file", type=Path, help="Codex hook payload（载荷）JSON 文件")
    codex.add_argument("--out", type=Path, help="写入 envelope（信封）的路径")
    codex.add_argument("--print-envelope", action="store_true", help="只输出 envelope（信封），不调用 Runtime（运行时）")

    git_pre_push = subparsers.add_parser("git-pre-push", help="适配 Git pre-push hook（推送前钩子）。")
    git_pre_push.add_argument("--project", type=Path, default=Path.cwd(), help="目标项目目录")
    git_pre_push.add_argument("--profile", required=True, help="Guard Profile（守卫画像）ID")
    git_pre_push.add_argument("--remote-name", default="", help="Git remote（远端）名称")
    git_pre_push.add_argument("--remote-url", default="", help="Git remote（远端）URL")
    git_pre_push.add_argument("--out", type=Path, help="写入 envelope（信封）的路径")
    git_pre_push.add_argument("--print-envelope", action="store_true", help="只输出 envelope（信封），不调用 Runtime（运行时）")

    args = parser.parse_args(argv)
    args.project = args.project.resolve()
    try:
        if args.command == "codex":
            return maybe_print_or_run(args, build_codex_envelope(args))
        if args.command == "git-pre-push":
            return maybe_print_or_run(args, build_git_pre_push_envelope(args))
    except ValueError as exc:
        print(f"status: error\nreason: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(main())
