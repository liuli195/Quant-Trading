from __future__ import annotations

import importlib.util
import py_compile
from dataclasses import dataclass
from pathlib import Path

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

    Overrides are injected into the ``set_parameter`` function body by matching
    ``g.<param_name> = ...`` lines.  Returns the path of the temporary file
    (which the caller should delete after upload).

    Only scalar values (int, float, bool, str, None) and simple lists of
    strings are supported as override values.
    """
    import re
    source = Path(strategy_file).resolve()
    code = source.read_text(encoding="utf-8")
    for name, value in overrides.items():
        value_literal = _to_py_literal(value)
        pattern = re.compile(rf"(g\.{re.escape(name)}\s*=\s*)[^\n]+")
        if not pattern.search(code):
            raise LocalCheckError(f"Parameter g.{name} not found in strategy file")
        code = pattern.sub(rf"\g<1>{value_literal}", code)
    tmp_path = source.with_name(f"{source.stem}__sweep_tmp.py")
    tmp_path.write_text(code, encoding="utf-8")
    return tmp_path


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
