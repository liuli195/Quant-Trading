from __future__ import annotations

import ast
import importlib.util
import py_compile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .paths import repo_root


class LocalCheckError(RuntimeError):
    """Raised when a local prerequisite fails."""


@dataclass(frozen=True)
class CompileResult:
    strategy_file: Path
    ok: bool
    message: str


def compile_strategy(strategy_file: str | Path) -> CompileResult:
    path = Path(strategy_file).resolve()
    if not path.is_file():
        raise LocalCheckError(f"Strategy file does not exist: {path}")
    try:
        py_compile.compile(str(path), doraise=True)
    except py_compile.PyCompileError as exc:
        raise LocalCheckError(str(exc)) from exc
    return CompileResult(strategy_file=path, ok=True, message="py_compile passed")


def generate_upload_file(strategy_file: str | Path, output_path: str | Path | None = None) -> Path:
    source = Path(strategy_file).resolve()
    if not source.is_file():
        raise LocalCheckError(f"Strategy file does not exist: {source}")
    target = Path(output_path).resolve() if output_path else source.with_name(f"{source.stem}__upload.py")

    strip_comments = _load_strip_comments()
    stripped = strip_comments(source.read_text(encoding="utf-8"))
    target.write_text(stripped, encoding="utf-8")
    return target


def apply_params_overrides(strategy_file: str | Path, overrides: dict[str, Any]) -> Path:
    """Write a temporary copy of the strategy file with parameter overrides applied.

    Overrides are injected into ``set_parameter`` by replacing matching
    ``g.<param_name> = ...`` assignment statements.  Returns the path of the temporary file
    (which the caller should delete after upload).

    Only scalar values (int, float, bool, str, None) and lists of those scalar
    values are supported as override values.
    """
    source = Path(strategy_file).resolve()
    code = source.read_text(encoding="utf-8")
    replacements = _build_param_replacements(code, overrides)
    lines = code.splitlines(keepends=True)
    for start_lineno, end_lineno, replacement in sorted(replacements, reverse=True):
        line_end = _line_ending(lines[end_lineno - 1])
        lines[start_lineno - 1:end_lineno] = [replacement + line_end]
    code = "".join(lines)
    try:
        ast.parse(code)
    except SyntaxError as exc:
        raise LocalCheckError(f"Parameter overrides produced invalid Python: {exc}") from exc
    tmp_path = source.with_name(f"{source.stem}__sweep_tmp.py")
    tmp_path.write_text(code, encoding="utf-8")
    return tmp_path


def _build_param_replacements(code: str, overrides: dict[str, Any]) -> list[tuple[int, int, str]]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise LocalCheckError(f"Strategy file is not valid Python: {exc}") from exc

    set_parameter = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "set_parameter"
        ),
        None,
    )
    if set_parameter is None:
        raise LocalCheckError("set_parameter function not found in strategy file")

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

    replacements = []
    for name, value in overrides.items():
        node = parameter_assignments.get(name)
        if node is None:
            if name in all_g_names:
                raise LocalCheckError(
                    f"g.{name} exists outside set_parameter; refusing to override non-parameter assignment"
                )
            raise LocalCheckError(f"Parameter g.{name} not found in set_parameter")
        if name in duplicates:
            raise LocalCheckError(f"Parameter g.{name} is assigned more than once in set_parameter")
        end_lineno = getattr(node, "end_lineno", None)
        if end_lineno is None:
            raise LocalCheckError(f"Cannot determine source span for parameter g.{name}")
        if end_lineno != node.lineno:
            raise LocalCheckError(
                f"Parameter g.{name} uses a multi-line assignment; override it manually or keep it on one line"
            )
        indent = " " * node.col_offset
        replacements.append((node.lineno, end_lineno, f"{indent}g.{name} = {_to_py_literal(value)}"))
    return replacements


def _assigned_g_names(node: ast.AST) -> list[str]:
    targets: list[ast.AST] = []
    if isinstance(node, ast.Assign):
        targets = list(node.targets)
    elif isinstance(node, ast.AnnAssign):
        targets = [node.target]

    names = []
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


def _to_py_literal(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, str):
        return repr(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        items = ", ".join(_to_py_literal(v) for v in value)
        return f"[{items}]"
    raise LocalCheckError(f"Unsupported param type: {type(value).__name__} for value {value!r}")


@lru_cache(maxsize=1)
def _load_strip_comments():
    root = repo_root()
    candidates = [
        root / "scripts" / "jq_automation" / "scripts" / "strip_comments.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_jq_strip_comments", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.strip_python_comments
    raise LocalCheckError("Could not find strip_comments.py")
