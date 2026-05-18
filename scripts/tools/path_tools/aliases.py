"""Resolve repository path aliases from path_aliases.json.

Public helpers are intentionally small:
  - resolve(alias, **vars) returns a repo-relative POSIX path string.
  - resolve_path(alias, **vars) returns an absolute pathlib.Path.
  - ensure_dir(alias, **vars) creates and returns the absolute path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


CONFIG_NAME = "path_aliases.json"
PLACEHOLDER_RE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ALIAS_LIFECYCLES = {"active", "superseded", "archived"}


class PathAliasError(ValueError):
    """Raised when a path alias cannot be resolved safely."""


def find_repo_root(start: str | Path | None = None) -> Path:
    """Find the repository root by walking upward to path_aliases.json."""
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent

    for candidate in (current, *current.parents):
        if (candidate / CONFIG_NAME).is_file():
            return candidate

    fallback = Path(__file__).resolve().parents[2]
    if (fallback / CONFIG_NAME).is_file():
        return fallback

    raise PathAliasError(f"Could not find {CONFIG_NAME}")


def load_config(root: str | Path | None = None) -> dict[str, Any]:
    """Load the path alias configuration."""
    repo = Path(root).resolve() if root else find_repo_root()
    config_path = repo / CONFIG_NAME
    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    config.setdefault("roots", {})
    config.setdefault("aliases", {})
    return config


def validate_config(config: dict[str, Any]) -> list[str]:
    """Validate the path alias registry without resolving user variables."""

    errors: list[str] = []
    if config.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(config.get("owner"), str) or not config["owner"].strip():
        errors.append("owner is required")
    if config.get("lifecycle") not in ALIAS_LIFECYCLES:
        errors.append(f"lifecycle must be one of {sorted(ALIAS_LIFECYCLES)}")
    roots = config.get("roots")
    aliases = config.get("aliases")
    if not isinstance(roots, dict) or not roots:
        errors.append("roots must be a non-empty object")
        roots = {}
    if not isinstance(aliases, dict):
        errors.append("aliases must be an object")
        aliases = {}
    for section, values in (("roots", roots), ("aliases", aliases)):
        for name, expression in values.items():
            if not isinstance(name, str) or not NAME_RE.fullmatch(name):
                errors.append(f"{section}.{name}: invalid name")
            if not isinstance(expression, str) or not expression.strip():
                errors.append(f"{section}.{name}: expression must be a non-empty string")
                continue
            try:
                _validate_path_expression(expression)
            except PathAliasError as exc:
                errors.append(f"{section}.{name}: {exc}")
    errors.extend(_validate_alias_cycles(aliases))
    return errors


def validate_config_file(root: str | Path | None = None) -> list[str]:
    """Validate ``path_aliases.json`` from a repository root."""

    return validate_config(load_config(root))


def repo_relative(path: str | Path, root: str | Path | None = None) -> str:
    """Return a POSIX repo-relative path and reject paths outside the repo."""
    repo = Path(root).resolve() if root else find_repo_root()
    absolute = Path(path)
    if not absolute.is_absolute():
        absolute = repo / absolute
    absolute = absolute.resolve()
    try:
        relative = absolute.relative_to(repo)
    except ValueError as exc:
        raise PathAliasError(f"Path escapes repository root: {path}") from exc
    return relative.as_posix()


def resolve(alias: str, **variables: str) -> str:
    """Resolve an alias to a repo-relative POSIX path string."""
    return repo_relative(resolve_path(alias, **variables))


def resolve_path(alias: str, **variables: str) -> Path:
    """Resolve an alias to an absolute path inside the repository."""
    repo = find_repo_root()
    config = load_config(repo)
    rendered = _render_named(alias, variables, config, stack=[])
    candidate = Path(rendered)
    if candidate.is_absolute():
        absolute = candidate.resolve()
    else:
        absolute = (repo / candidate).resolve()

    repo_relative(absolute, repo)
    return absolute


def ensure_dir(alias: str, **variables: str) -> Path:
    """Resolve an alias, create the directory, and return its absolute path."""
    directory = resolve_path(alias, **variables)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _render_named(
    name: str,
    variables: dict[str, str],
    config: dict[str, Any],
    stack: list[str],
) -> str:
    roots = config.get("roots", {})
    aliases = config.get("aliases", {})

    if name in variables:
        return str(variables[name])
    if name in roots:
        return _render_expression(str(roots[name]), variables, config, stack)
    if name not in aliases:
        raise PathAliasError(f"Unknown path alias or variable: {name}")
    if name in stack:
        cycle = " -> ".join([*stack, name])
        raise PathAliasError(f"Circular path alias reference: {cycle}")

    return _render_expression(str(aliases[name]), variables, config, [*stack, name])


def _render_expression(
    expression: str,
    variables: dict[str, str],
    config: dict[str, Any],
    stack: list[str],
) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        return _render_named(token, variables, config, stack)

    rendered = PLACEHOLDER_RE.sub(replace, expression)
    normalized = Path(rendered.replace("\\", "/"))
    if normalized.is_absolute():
        raise PathAliasError(f"Absolute paths are not allowed in aliases: {expression}")
    if ".." in normalized.parts:
        raise PathAliasError(f"Alias escapes repository root: {expression}")
    return normalized.as_posix()


def _validate_path_expression(expression: str) -> None:
    normalized = Path(expression.replace("\\", "/"))
    if normalized.is_absolute():
        raise PathAliasError(f"absolute paths are not allowed: {expression}")
    if ".." in normalized.parts:
        raise PathAliasError(f"path escapes repository root: {expression}")


def _validate_alias_cycles(aliases: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(name: str, stack: list[str]) -> None:
        if name in visited:
            return
        if name in visiting:
            errors.append(f"circular path alias reference: {' -> '.join([*stack, name])}")
            return
        visiting.add(name)
        expression = str(aliases.get(name, ""))
        for token in PLACEHOLDER_RE.findall(expression):
            if token in aliases:
                visit(token, [*stack, name])
        visiting.remove(name)
        visited.add(name)

    for alias_name in aliases:
        visit(str(alias_name), [])
    return errors


def _parse_assignments(items: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise PathAliasError(f"Expected key=value assignment, got: {item}")
        key, value = item.split("=", 1)
        if not key:
            raise PathAliasError(f"Empty assignment key: {item}")
        values[key] = value
    return values


def _cmd_resolve(args: argparse.Namespace) -> int:
    variables = _parse_assignments(args.assignments)
    path = resolve_path(args.alias, **variables)
    print(str(path) if args.absolute else repo_relative(path))
    return 0


def _cmd_list(_: argparse.Namespace) -> int:
    config = load_config()
    print("roots:")
    for name, value in sorted(config.get("roots", {}).items()):
        print(f"  {name}: {value}")
    print("aliases:")
    for name, value in sorted(config.get("aliases", {}).items()):
        print(f"  {name}: {value}")
    return 0


def _cmd_validate(_: argparse.Namespace) -> int:
    errors = validate_config_file()
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve", help="resolve one alias")
    resolve_parser.add_argument("alias")
    resolve_parser.add_argument("assignments", nargs="*")
    resolve_parser.add_argument("--absolute", action="store_true")
    resolve_parser.set_defaults(func=_cmd_resolve)

    list_parser = subparsers.add_parser("list", help="list configured aliases")
    list_parser.set_defaults(func=_cmd_list)

    validate_parser = subparsers.add_parser("validate", help="validate path_aliases.json")
    validate_parser.set_defaults(func=_cmd_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except PathAliasError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

