"""Strategy variant registry and guarded Git operation planning."""

from __future__ import annotations

import ast
import hashlib
import json
import pprint
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VARIANT_TYPES = {"parameter", "structural"}
VARIANT_STATUSES = (
    "candidate",
    "in_research",
    "cloud_confirmed",
    "merge_ready",
    "merged_pending_validation",
    "merged_confirmed",
)
STRUCTURAL_TRANSITIONS = {
    "candidate": {"in_research"},
    "in_research": {"cloud_confirmed"},
    "cloud_confirmed": {"merge_ready"},
    "merge_ready": {"merged_pending_validation"},
    "merged_pending_validation": {"merged_confirmed"},
}
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MERGE_STATUSES = {"not_merged", "merged_pending_validation", "merged_confirmed"}
LIFECYCLE_STATES = {"active", "superseded", "archived"}
VARIANT_UPDATE_FIELDS = {
    "description",
    "code_source",
    "params_diff",
    "research_refs",
    "backtest_refs",
    "report_refs",
    "payload",
    "owner",
    "updated_by",
    "lifecycle",
}


class VariantError(RuntimeError):
    """Raised when a strategy variant cannot be registered or materialized."""


class GitAuthorizationError(PermissionError):
    """Raised when a protected Git operation is requested without approval."""


@dataclass(frozen=True)
class StrategyManifest:
    """Resolved strategy manifest with repo-relative paths."""

    strategy: str
    root: Path
    code_path: Path
    manifest_path: Path
    payload: dict[str, Any]


class StrategyManifestReader:
    """Read explicit or inferred strategy metadata."""

    def __init__(self, strategies_root: str | Path = "strategies") -> None:
        self.strategies_root = Path(strategies_root)

    def read(self, strategy: str | Path) -> StrategyManifest:
        strategy_root = Path(strategy)
        if not strategy_root.exists():
            strategy_root = self.strategies_root / str(strategy)
        strategy_root = strategy_root.resolve()
        manifest_path = strategy_root / "strategy.json"
        if manifest_path.is_file():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        else:
            payload = self._infer_manifest(strategy_root)
        errors = _validate_strategy_manifest_payload(payload)
        if errors:
            raise VariantError(f"invalid strategy manifest {manifest_path}: {'; '.join(errors)}")
        raw_code_path = payload.get("code_path") or payload.get("strategy_file")
        if raw_code_path is None:
            raise VariantError(f"strategy manifest missing code_path or strategy_file: {manifest_path}")
        raw_code_path = str(raw_code_path)
        if Path(raw_code_path).is_absolute():
            code_path = Path(raw_code_path).resolve()
        else:
            code_path = (strategy_root / raw_code_path).resolve()
            if not code_path.is_file():
                repo_relative = (strategy_root.parent.parent / raw_code_path).resolve()
                if repo_relative.is_file():
                    code_path = repo_relative
        if not code_path.is_file():
            raise VariantError(f"strategy code file not found: {code_path}")
        return StrategyManifest(
            strategy=str(payload["strategy"]),
            root=strategy_root,
            code_path=code_path,
            manifest_path=manifest_path,
            payload=payload,
        )

    def ensure(self, strategy: str | Path) -> StrategyManifest:
        manifest = self.read(strategy)
        if not manifest.manifest_path.exists():
            manifest.manifest_path.write_text(
                json.dumps(manifest.payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return manifest

    def _infer_manifest(self, strategy_root: Path) -> dict[str, Any]:
        strategy = strategy_root.name
        preferred = strategy_root / f"{strategy}.py"
        if preferred.is_file():
            code_path = preferred
        else:
            candidates = sorted(
                path for path in strategy_root.glob("*.py")
                if path.name != "__init__.py" and "__upload" not in path.stem
            )
            if not candidates:
                raise VariantError(f"no strategy source file found in {strategy_root}")
            code_path = candidates[0]
        return {
            "schema_version": 1,
            "strategy": strategy,
            "owner": "research-platform",
            "created_by": "research-platform",
            "updated_by": "research-platform",
            "lifecycle": "active",
            "code_path": code_path.relative_to(strategy_root).as_posix(),
            "variants_path": "variants/variants.json",
            "reports_path": "reports",
            "backtest_runs_path": "backtest_runs",
            "test_batches_path": "test_batches",
            "constraints": {
                "git_operations_require_authorization": True,
                "default_parameter_writeback_requires_authorization": True,
            },
        }


class VariantRegistry:
    """Persist parameter and structural variants under ``strategies/<name>/variants``."""

    def __init__(self, strategy_root: str | Path) -> None:
        self.strategy_root = Path(strategy_root)
        self.variants_dir = self.strategy_root / "variants"
        self.index_path = self.variants_dir / "variants.json"

    def ensure(self) -> None:
        self.variants_dir.mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self.index_path.write_text(
                json.dumps({"schema_version": 1, "variants": []}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def list(self) -> list[dict[str, Any]]:
        self.ensure()
        return list(self._read_index().get("variants", []))

    def get(self, variant_id: str) -> dict[str, Any]:
        detail_path = self.variants_dir / f"{variant_id}.json"
        if not detail_path.is_file():
            raise VariantError(f"variant not found: {variant_id}")
        return json.loads(detail_path.read_text(encoding="utf-8"))

    def register(
        self,
        *,
        variant_id: str,
        variant_type: str,
        payload: dict[str, Any] | None = None,
        description: str = "",
        status: str = "candidate",
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if not SAFE_ID_RE.fullmatch(variant_id):
            raise VariantError("variant_id must be 1-128 chars of letters, digits, dot, underscore or hyphen")
        if variant_type not in VARIANT_TYPES:
            raise VariantError(f"variant_type must be one of {sorted(VARIANT_TYPES)}")
        if status not in VARIANT_STATUSES:
            raise VariantError(f"status must be one of {list(VARIANT_STATUSES)}")
        payload = payload or {}
        code_source = payload.get("code_source")
        params_diff = payload.get("params_diff", payload.get("param_overrides", {}))
        if variant_type == "structural" and not code_source:
            raise VariantError("structural variants require payload.code_source")
        if variant_type == "structural" and status in {"merge_ready", "merged_pending_validation", "merged_confirmed"}:
            raise VariantError("structural variants must reach merge states through explicit status transitions")
        for value in params_diff.values():
            _ensure_supported_literal(value)

        self.ensure()
        detail_path = self.variants_dir / f"{variant_id}.json"
        if detail_path.exists() and not overwrite:
            raise VariantError(f"variant already exists: {variant_id}")

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        existing = self.get(variant_id) if detail_path.exists() else {}
        record = {
            "schema_version": 1,
            "variant_id": variant_id,
            "variant_type": variant_type,
            "status": status,
            "merge_status": existing.get("merge_status", "not_merged"),
            "description": description,
            "code_source": code_source,
            "params_diff": params_diff,
            "research_refs": payload.get("research_refs", []),
            "backtest_refs": payload.get("backtest_refs", []),
            "report_refs": payload.get("report_refs", []),
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "owner": payload.get("owner", existing.get("owner", "research-platform")),
            "created_by": existing.get("created_by", payload.get("created_by", "research-platform")),
            "updated_by": payload.get("updated_by", "research-platform"),
            "lifecycle": payload.get("lifecycle", existing.get("lifecycle", "active")),
            "payload": payload,
        }
        _validate_variant_record(record)
        detail_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        self._upsert_index_record(record)
        return record

    def transition_status(self, variant_id: str, status: str, *, yes: bool = False) -> dict[str, Any]:
        if status not in VARIANT_STATUSES:
            raise VariantError(f"status must be one of {list(VARIANT_STATUSES)}")
        record = self.get(variant_id)
        current = str(record["status"])
        if record["variant_type"] == "structural":
            if status == "merged_confirmed" and not yes:
                raise GitAuthorizationError("marking merged_confirmed requires explicit authorization")
            allowed = STRUCTURAL_TRANSITIONS.get(current, set())
            if status not in allowed and status != current:
                raise VariantError(f"invalid structural status transition: {current} -> {status}")
        record["status"] = status
        if status == "merged_pending_validation":
            record["merge_status"] = "merged_pending_validation"
        elif status == "merged_confirmed":
            record["merge_status"] = "merged_confirmed"
        record["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record.setdefault("owner", "research-platform")
        record["updated_by"] = record.get("updated_by") or "research-platform"
        record.setdefault("lifecycle", "active")
        _validate_variant_record(record)
        (self.variants_dir / f"{variant_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._upsert_index_record(record)
        return record

    def update(self, variant_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        forbidden = sorted(set(updates) - VARIANT_UPDATE_FIELDS)
        if forbidden:
            blocked_status = {"status", "merge_status"} & set(forbidden)
            if blocked_status:
                raise VariantError("status and merge_status must use transition_status or merge helpers")
            raise VariantError(f"unknown variant update field(s): {', '.join(forbidden)}")
        record = self.get(variant_id)
        record.update(updates)
        record["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record.setdefault("owner", "research-platform")
        record.setdefault("created_by", "research-platform")
        record.setdefault("updated_by", "research-platform")
        record.setdefault("lifecycle", "active")
        _validate_variant_record(record)
        (self.variants_dir / f"{variant_id}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._upsert_index_record(record)
        return record

    def _read_index(self) -> dict[str, Any]:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _upsert_index_record(self, record: dict[str, Any]) -> None:
        index = self._read_index()
        rows = [row for row in index.get("variants", []) if row.get("variant_id") != record["variant_id"]]
        rows.append({
            "variant_id": record["variant_id"],
            "variant_type": record["variant_type"],
            "status": record["status"],
            "merge_status": record.get("merge_status", "not_merged"),
            "description": record.get("description", ""),
            "updated_at": record["updated_at"],
            "detail": f"{record['variant_id']}.json",
        })
        index["variants"] = sorted(rows, key=lambda item: item["variant_id"])
        self.index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


class StrategyMaterializer:
    """Create uploadable strategy snapshots from registered variants."""

    def __init__(self, strategy_root: str | Path, output_root: str | Path = ".local/research-materialized") -> None:
        self.strategy_root = Path(strategy_root)
        self.output_root = Path(output_root)
        self.registry = VariantRegistry(self.strategy_root)
        self.manifest = StrategyManifestReader(self.strategy_root.parent).read(self.strategy_root)

    def materialize(self, variant_id: str, *, run_id: str | None = None) -> Path:
        variant = self.registry.get(variant_id)
        source, source_ref = self._source_for_variant(variant)
        overrides = dict(
            variant.get("params_diff")
            or variant.get("payload", {}).get("params_diff")
            or variant.get("payload", {}).get("param_overrides")
            or {}
        )
        materialized = _apply_param_overrides(source, overrides) if overrides else source
        code_hash = hashlib.sha256(materialized.encode("utf-8")).hexdigest()

        safe_run = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = self.output_root / self.manifest.strategy / variant_id / safe_run
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / self.manifest.code_path.name
        out_path.write_text(materialized, encoding="utf-8")
        (out_dir / "materialized.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "strategy": self.manifest.strategy,
                    "variant_id": variant_id,
                    "source": source_ref,
                    "param_overrides": overrides,
                    "output": out_path.as_posix(),
                    "uploaded_code_sha256": f"sha256:{code_hash}",
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return out_path

    def _source_for_variant(self, variant: dict[str, Any]) -> tuple[str, str]:
        if variant.get("variant_type") != "structural":
            return self.manifest.code_path.read_text(encoding="utf-8"), self.manifest.code_path.as_posix()

        code_source = variant.get("code_source") or variant.get("payload", {}).get("code_source")
        if not code_source:
            raise VariantError("structural variant missing code_source")
        source_type = code_source.get("type", "git")
        rel_path = code_source.get("path") or _repo_relative_path(self.manifest.code_path)
        if source_type != "git":
            raise VariantError(f"unsupported structural code_source type: {source_type}")
        ref = code_source.get("commit") or code_source.get("ref")
        if ref:
            repo_root = _git_repo_root(self.strategy_root)
            payload = _git(repo_root, ["show", f"{ref}:{rel_path}"])
            return payload, f"git:{ref}:{rel_path}"
        path = Path(rel_path)
        if not path.is_absolute():
            path = _git_repo_root(self.strategy_root) / rel_path
        if not path.is_file():
            raise VariantError(f"structural code_source path not found: {path}")
        return path.read_text(encoding="utf-8"), path.as_posix()


class StructuralBranchManager:
    """Prepare and optionally execute protected branch creation."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root)

    def branch_plan(self, *, variant_id: str, branch_name: str | None = None, base_ref: str = "HEAD") -> dict[str, Any]:
        target_branch = branch_name or f"research/{variant_id}"
        base_sha = self._git(["rev-parse", "--verify", f"{base_ref}^{{commit}}"])
        status = self._git(["status", "--short"], check=False)
        return {
            "action": "create_branch",
            "variant_id": variant_id,
            "branch_name": target_branch,
            "base_ref": base_ref,
            "base_sha": base_sha.strip(),
            "working_tree_clean": status.strip() == "",
            "working_tree_status": status.splitlines(),
            "commands": [
                ["git", "switch", "-c", target_branch, base_sha.strip()],
            ],
            "requires_authorization": True,
        }

    def create_branch(
        self,
        *,
        variant_id: str,
        branch_name: str | None = None,
        base_ref: str = "HEAD",
        yes: bool = False,
    ) -> dict[str, Any]:
        if not yes:
            raise GitAuthorizationError("branch creation requires explicit authorization")
        plan = self.branch_plan(variant_id=variant_id, branch_name=branch_name, base_ref=base_ref)
        if not plan["working_tree_clean"]:
            raise VariantError("working tree must be clean before creating a structural variant branch")
        self._git(["switch", "-c", plan["branch_name"], plan["base_sha"]])
        return {**plan, "executed": True}

    def _git(self, args: list[str], *, check: bool = True) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if check and result.returncode != 0:
            raise VariantError(result.stderr.strip() or result.stdout.strip())
        return result.stdout


class VariantMergeManager:
    """Prepare and optionally execute protected structural variant merges."""

    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root)
        self.branch_manager = StructuralBranchManager(repo_root)

    def merge_plan(
        self,
        *,
        source_ref: str | None = None,
        target_ref: str = "HEAD",
        strategy_root: str | Path | None = None,
        variant_id: str | None = None,
    ) -> dict[str, Any]:
        variant: dict[str, Any] | None = None
        if variant_id is not None:
            if strategy_root is None:
                raise VariantError("variant merge plan requires strategy_root")
            variant = VariantRegistry(strategy_root).get(variant_id)
            if variant.get("variant_type") != "structural":
                raise VariantError("merge-plan only supports structural variants")
            if variant.get("status") != "merge_ready":
                raise VariantError(f"variant must be merge_ready before merge-plan: {variant.get('status')}")
            code_source = variant.get("code_source") or {}
            source_ref = str(code_source.get("commit") or code_source.get("ref") or "")
            if not source_ref:
                raise VariantError("structural variant code_source requires ref or commit for merge-plan")
        if not source_ref:
            raise VariantError("merge-plan requires source_ref or variant_id")
        source_sha = self.branch_manager._git(["rev-parse", "--verify", f"{source_ref}^{{commit}}"]).strip()
        target_sha = self.branch_manager._git(["rev-parse", "--verify", f"{target_ref}^{{commit}}"]).strip()
        diff_summary = self.branch_manager._git(["diff", "--stat", target_sha, source_sha], check=False)
        plan = {
            "action": "merge",
            "variant_id": variant_id,
            "source_ref": source_ref,
            "source_sha": source_sha,
            "target_ref": target_ref,
            "target_sha": target_sha,
            "diff_summary": diff_summary.splitlines(),
            "commands": [["git", "merge", "--no-ff", "--no-edit", source_sha]],
            "conflict_policy": "stop_and_report_only",
            "post_merge_status": "merged_pending_validation" if variant_id else None,
            "requires_authorization": True,
        }
        if variant is not None:
            plan["post_merge_validation"] = [
                "run cloud regression for merged main strategy",
                "compare merged main strategy against pre-merge baseline",
                "mark merged_confirmed only after cloud confirmation passes",
            ]
        return plan

    def apply_merge(
        self,
        *,
        source_ref: str | None = None,
        target_ref: str = "HEAD",
        yes: bool = False,
        strategy_root: str | Path | None = None,
        variant_id: str | None = None,
    ) -> dict[str, Any]:
        if not yes:
            raise GitAuthorizationError("merge requires explicit authorization")
        plan = self.merge_plan(
            source_ref=source_ref,
            target_ref=target_ref,
            strategy_root=strategy_root,
            variant_id=variant_id,
        )
        result = subprocess.run(
            ["git", "merge", "--no-ff", "--no-edit", plan["source_sha"]],
            cwd=self.repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            conflicts = self.branch_manager._git(["diff", "--name-only", "--diff-filter=U"], check=False)
            return {
                **plan,
                "executed": False,
                "status": "conflict_or_failed",
                "stdout": result.stdout,
                "stderr": result.stderr,
                "conflict_files": conflicts.splitlines(),
            }
        if variant_id is not None and strategy_root is not None:
            registry = VariantRegistry(strategy_root)
            record = registry.get(variant_id)
            code_source = dict(record.get("code_source") or {})
            code_source["commit"] = plan["source_sha"]
            registry.update(variant_id, {"code_source": code_source})
            registry.transition_status(variant_id, "merged_pending_validation")
        return {**plan, "executed": True, "status": "merged"}


def _apply_param_overrides(source: str, overrides: dict[str, Any]) -> str:
    replacements = _build_param_replacements(source, overrides)
    lines = source.splitlines(keepends=True)
    for start_lineno, end_lineno, replacement in sorted(replacements, reverse=True):
        line_end = _line_ending(lines[end_lineno - 1])
        lines[start_lineno - 1:end_lineno] = [replacement + line_end]
    materialized = "".join(lines)
    try:
        ast.parse(materialized)
    except SyntaxError as exc:
        raise VariantError(f"parameter overrides produced invalid Python: {exc}") from exc
    return materialized


def _build_param_replacements(source: str, overrides: dict[str, Any]) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise VariantError(f"strategy source is not valid Python: {exc}") from exc

    set_parameter = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "set_parameter"
        ),
        None,
    )
    if set_parameter is None:
        raise VariantError("set_parameter function not found in strategy source")

    all_g_names = {
        name
        for node in ast.walk(tree)
        for name in _assigned_g_names(node)
    }
    parameter_assignments: dict[str, ast.AST] = {}
    duplicates: set[str] = set()
    for node in ast.walk(set_parameter):
        for name in _assigned_g_names(node):
            if name in parameter_assignments:
                duplicates.add(name)
            parameter_assignments[name] = node

    replacements: list[tuple[int, int, str]] = []
    for name, value in overrides.items():
        _ensure_supported_literal(value)
        node = parameter_assignments.get(name)
        if node is None:
            if name in all_g_names:
                raise VariantError(
                    f"g.{name} exists outside set_parameter; refusing to override non-parameter assignment"
                )
            raise VariantError(f"parameter override target not found in set_parameter: {name}")
        if name in duplicates:
            raise VariantError(f"parameter g.{name} is assigned more than once in set_parameter")
        end_lineno = getattr(node, "end_lineno", None)
        if end_lineno is None:
            raise VariantError(f"cannot determine source span for parameter g.{name}")
        if end_lineno != node.lineno:
            raise VariantError(f"parameter g.{name} uses a multi-line assignment")
        indent = " " * node.col_offset
        replacements.append((node.lineno, end_lineno, f"{indent}g.{name} = {_python_literal(value)}"))
    return replacements


def _assigned_g_names(node: ast.AST) -> list[str]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]

    names: list[str] = []
    for target in targets:
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "g"
        ):
            names.append(target.attr)
    return names


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def _python_literal(value: Any) -> str:
    try:
        ast.literal_eval(repr(value))
    except (ValueError, SyntaxError):
        return pprint.pformat(value, width=100, sort_dicts=True)
    return pprint.pformat(value, width=100, sort_dicts=True)


def _ensure_supported_literal(value: Any) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _ensure_supported_literal(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool)):
                raise VariantError(f"unsupported parameter literal key type: {type(key).__name__}")
            _ensure_supported_literal(item)
        return
    raise VariantError(f"unsupported parameter literal type: {type(value).__name__}")


def _validate_variant_record(record: dict[str, Any]) -> None:
    if record.get("schema_version") != 1:
        raise VariantError("variant schema_version must be 1")
    variant_id = str(record.get("variant_id", ""))
    if not SAFE_ID_RE.fullmatch(variant_id):
        raise VariantError("variant_id must be 1-128 chars of letters, digits, dot, underscore or hyphen")
    if record.get("variant_type") not in VARIANT_TYPES:
        raise VariantError(f"variant_type must be one of {sorted(VARIANT_TYPES)}")
    if record.get("status") not in VARIANT_STATUSES:
        raise VariantError(f"status must be one of {list(VARIANT_STATUSES)}")
    if record.get("merge_status") not in MERGE_STATUSES:
        raise VariantError(f"merge_status must be one of {sorted(MERGE_STATUSES)}")
    if not str(record.get("owner", "")).strip():
        raise VariantError("variant owner is required")
    if record.get("lifecycle") not in LIFECYCLE_STATES:
        raise VariantError(f"variant lifecycle must be one of {sorted(LIFECYCLE_STATES)}")
    if record["variant_type"] == "structural" and not record.get("code_source"):
        raise VariantError("structural variants require code_source")
    if record.get("code_source") is not None and not isinstance(record["code_source"], dict):
        raise VariantError("code_source must be an object or null")
    params_diff = record.get("params_diff", {})
    if not isinstance(params_diff, dict):
        raise VariantError("params_diff must be an object")
    for value in params_diff.values():
        _ensure_supported_literal(value)
    for field_name in ("research_refs", "backtest_refs", "report_refs"):
        value = record.get(field_name, [])
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise VariantError(f"{field_name} must be a list of strings")


def _validate_strategy_manifest_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("strategy", "owner", "lifecycle"):
        if not isinstance(payload.get(field), str) or not str(payload.get(field)).strip():
            errors.append(f"{field} is required")
    if payload.get("lifecycle") not in LIFECYCLE_STATES:
        errors.append(f"lifecycle must be one of {sorted(LIFECYCLE_STATES)}")
    if not payload.get("code_path") and not payload.get("strategy_file"):
        errors.append("code_path or strategy_file is required")
    constraints = payload.get("constraints", {})
    if constraints and not isinstance(constraints, dict):
        errors.append("constraints must be an object")
    return errors


def _git_repo_root(path: str | Path) -> Path:
    return Path(_git(Path(path), ["rev-parse", "--show-toplevel"]).strip())


def _git(cwd: Path, args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if result.returncode != 0:
        raise VariantError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def _repo_relative_path(path: Path) -> str:
    root = _git_repo_root(path.parent)
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()
