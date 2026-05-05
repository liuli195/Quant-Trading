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


def _load_strip_comments():
    root = repo_root()
    candidates = [
        root / ".agents" / "skills" / "jq-run" / "scripts" / "strip_comments.py",
        root / ".claude" / "skills" / "jq-run" / "scripts" / "strip_comments.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("_jq_strip_comments", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                return module.strip_python_comments
    raise LocalCheckError("Could not find jq-run strip_comments.py")
