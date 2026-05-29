"""Move files and rewrite path references using repository path aliases."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

try:
    from .aliases import PathAliasError, find_repo_root, repo_relative, resolve_path
except ImportError:  # pragma: no cover - supports direct script execution.
    from aliases import PathAliasError, find_repo_root, repo_relative, resolve_path  # type: ignore[no-redef]


TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
}
EXCLUDED_DIR_NAMES = {
    ".git",
    ".local",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

MD_LINK_RE = re.compile(r"(?P<prefix>!?\[[^\]]*]\()(?P<link>[^)\n]+)(?P<suffix>\))")
PATHREF_LINK_RE = re.compile(
    r"(?P<prefix>!?\[[^\]]*]\()"
    r"(?P<link>[^)\n]+)"
    r"(?P<suffix>\)\s*<!--\s*pathref:\s*(?P<pathref>[^>]+?)\s*-->)"
)
PATHREF_COMMENT_RE = re.compile(r"<!--\s*pathref:\s*(?P<pathref>[^>]+?)\s*-->")
PATHREF_RE = re.compile(
    r"^(?P<alias>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\((?P<args>[^)]*)\))?"
    r"(?:/(?P<tail>.*))?$"
)


@dataclass(frozen=True)
class Move:
    old: Path
    new: Path


@dataclass(frozen=True)
class PathRef:
    alias: str
    args: dict[str, str]
    tail: str

    def format(self) -> str:
        args = ""
        if self.args:
            args = "(" + ", ".join(f"{key}={value}" for key, value in self.args.items()) + ")"
        tail = f"/{self.tail}" if self.tail else ""
        return f"{self.alias}{args}{tail}"


def is_external_link(link: str) -> bool:
    lowered = link.lower()
    return (
        lowered.startswith(("http://", "https://", "mailto:", "tel:"))
        or lowered.startswith("#")
        or not link.strip()
    )


def split_link_suffix(link: str) -> tuple[str, str]:
    indexes = [idx for idx in (link.find("#"), link.find("?")) if idx >= 0]
    if not indexes:
        return link, ""
    split_at = min(indexes)
    return link[:split_at], link[split_at:]


def parse_pathref(raw: str) -> PathRef:
    match = PATHREF_RE.match(raw.strip())
    if not match:
        raise PathAliasError(f"Invalid pathref: {raw}")

    args: dict[str, str] = {}
    args_raw = match.group("args") or ""
    for part in [piece.strip() for piece in args_raw.split(",") if piece.strip()]:
        if "=" not in part:
            raise PathAliasError(f"Invalid pathref argument: {part}")
        key, value = part.split("=", 1)
        args[key.strip()] = value.strip().strip("\"'")

    return PathRef(
        alias=match.group("alias"),
        args=args,
        tail=match.group("tail") or "",
    )


def resolve_pathref(raw: str) -> Path:
    pathref = parse_pathref(raw)
    base = resolve_path(pathref.alias, **pathref.args)
    target = (base / pathref.tail).resolve()
    repo_relative(target)
    return target


def relative_markdown_path(source_file: Path, target: Path, suffix: str = "") -> str:
    relative = os.path.relpath(target, source_file.parent)
    return relative.replace("\\", "/") + suffix


def should_skip(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDED_DIR_NAMES:
        return True
    if "backtest_runs" in parts and "tabs_raw" in parts:
        return True
    return False


def iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if should_skip(path) or not path.is_file():
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def target_after_moves(target: Path, moves: list[Move]) -> Path | None:
    resolved = target.resolve()
    for move in moves:
        if resolved == move.old:
            return move.new
        try:
            relative = resolved.relative_to(move.old)
        except ValueError:
            continue
        return (move.new / relative).resolve()
    return None


def update_pathref(raw: str, moves: list[Move]) -> tuple[str, str | None]:
    pathref = parse_pathref(raw)
    old_target = resolve_pathref(raw)
    new_target = target_after_moves(old_target, moves)
    if new_target is None:
        return raw, None

    base = resolve_path(pathref.alias, **pathref.args)
    try:
        new_tail = new_target.relative_to(base).as_posix()
    except ValueError:
        return raw, f"Cannot express moved target with existing alias: {raw}"

    updated = PathRef(alias=pathref.alias, args=pathref.args, tail=new_tail).format()
    return updated, None


def rewrite_pathref_comments(text: str, moves: list[Move]) -> tuple[str, list[str]]:
    warnings: list[str] = []

    def replace(match: re.Match[str]) -> str:
        raw = match.group("pathref")
        try:
            updated, warning = update_pathref(raw, moves)
        except PathAliasError as exc:
            warnings.append(str(exc))
            return match.group(0)
        if warning:
            warnings.append(warning)
            return match.group(0)
        return f"<!-- pathref: {updated} -->"

    return PATHREF_COMMENT_RE.sub(replace, text), warnings


def rewrite_markdown_links_for_moves(text: str, source_file: Path, moves: list[Move]) -> str:
    def replace(match: re.Match[str]) -> str:
        link = match.group("link")
        if is_external_link(link):
            return match.group(0)

        link_path, link_suffix = split_link_suffix(link)
        target = (source_file.parent / link_path).resolve()
        moved = target_after_moves(target, moves)
        if moved is None:
            return match.group(0)

        return (
            match.group("prefix")
            + relative_markdown_path(source_file, moved, link_suffix)
            + match.group("suffix")
        )

    return MD_LINK_RE.sub(replace, text)


def replace_literal_paths(text: str, moves: list[Move], root: Path) -> str:
    updated = text
    for move in moves:
        old_rel = repo_relative(move.old, root)
        new_rel = repo_relative(move.new, root)
        updated = updated.replace(old_rel, new_rel)
        updated = updated.replace(old_rel.replace("/", "\\"), new_rel.replace("/", "\\"))
    return updated


def apply_reference_rewrite(
    moves: list[Move],
    dry_run: bool,
    include_pathref_rewrite: bool = True,
) -> int:
    root = find_repo_root()
    changed: list[Path] = []
    warnings: list[str] = []

    for path in iter_text_files(root):
        original = read_text(path)
        if original is None:
            continue

        updated = original
        if include_pathref_rewrite and path.suffix.lower() == ".md":
            updated, pathref_warnings = rewrite_pathref_comments(updated, moves)
            warnings.extend(f"{repo_relative(path, root)}: {item}" for item in pathref_warnings)
            updated = rewrite_markdown_links_for_moves(updated, path, moves)

        updated = replace_literal_paths(updated, moves, root)

        if updated != original:
            changed.append(path)
            if not dry_run:
                path.write_text(updated, encoding="utf-8")

    for path in changed:
        print(("would update: " if dry_run else "updated: ") + repo_relative(path, root))
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)
    print(f"{'Would update' if dry_run else 'Updated'} {len(changed)} file(s).")
    return 0 if not warnings else 1


def _select_markdown_files(root: Path, files: Sequence[Path] | None) -> tuple[list[Path], list[str]]:
    if files is None:
        return [
            path for path in iter_text_files(root)
            if path.suffix.lower() == ".md"
        ], []

    selected: list[Path] = []
    errors: list[str] = []
    for item in files:
        path = (root / item).resolve() if not item.is_absolute() else item.resolve()
        try:
            rel_path = repo_relative(path, root)
        except PathAliasError as exc:
            errors.append(str(exc))
            continue
        if not path.is_file():
            errors.append(f"{rel_path}: file does not exist")
            continue
        if path.suffix.lower() != ".md":
            errors.append(f"{rel_path}: --files only accepts Markdown files")
            continue
        selected.append(path)
    return selected, errors


def check_markdown_pathrefs(
    strict: bool = False,
    files: Sequence[Path] | None = None,
) -> int:
    root = find_repo_root()
    errors: list[str] = []
    warnings: list[str] = []
    checked = 0
    markdown_files, selection_errors = _select_markdown_files(root, files)
    errors.extend(selection_errors)

    for path in markdown_files:
        text = read_text(path)
        if text is None:
            continue

        pathref_spans = [match.span() for match in PATHREF_LINK_RE.finditer(text)]
        for match in PATHREF_LINK_RE.finditer(text):
            checked += 1
            link = match.group("link")
            link_path, link_suffix = split_link_suffix(link)
            try:
                target = resolve_pathref(match.group("pathref"))
            except PathAliasError as exc:
                errors.append(f"{repo_relative(path, root)}: {exc}")
                continue

            if not target.exists():
                errors.append(f"{repo_relative(path, root)}: missing pathref target {repo_relative(target, root)}")
                continue

            expected = relative_markdown_path(path, target, link_suffix)
            if link_path.replace("\\", "/") != expected.replace("\\", "/").removesuffix(link_suffix):
                errors.append(
                    f"{repo_relative(path, root)}: link '{link}' should be '{expected}'"
                )

        if strict:
            for match in MD_LINK_RE.finditer(text):
                if any(start <= match.start() < end for start, end in pathref_spans):
                    continue
                link = match.group("link")
                if is_external_link(link):
                    continue
                link_path, _ = split_link_suffix(link)
                if (path.parent / link_path).exists():
                    warnings.append(f"{repo_relative(path, root)}: internal link lacks pathref: {link}")

    for item in errors:
        print(f"error: {item}", file=sys.stderr)
    for item in warnings:
        print(f"warning: {item}", file=sys.stderr)
    print(f"Checked {len(markdown_files)} Markdown file(s).")
    print(f"Checked {checked} pathref link(s).")
    if selection_errors:
        return 2
    return 1 if errors or (strict and warnings) else 0


def rewrite_markdown_from_pathrefs(dry_run: bool) -> int:
    root = find_repo_root()
    changed: list[Path] = []
    errors: list[str] = []

    for path in iter_text_files(root):
        if path.suffix.lower() != ".md":
            continue
        original = read_text(path)
        if original is None:
            continue

        def replace(match: re.Match[str]) -> str:
            link = match.group("link")
            _, link_suffix = split_link_suffix(link)
            try:
                target = resolve_pathref(match.group("pathref"))
            except PathAliasError as exc:
                errors.append(f"{repo_relative(path, root)}: {exc}")
                return match.group(0)
            rewritten = relative_markdown_path(path, target, link_suffix)
            return match.group("prefix") + rewritten + match.group("suffix")

        updated = PATHREF_LINK_RE.sub(replace, original)
        if updated != original:
            changed.append(path)
            if not dry_run:
                path.write_text(updated, encoding="utf-8")

    for item in errors:
        print(f"error: {item}", file=sys.stderr)
    for path in changed:
        print(("would update: " if dry_run else "updated: ") + repo_relative(path, root))
    print(f"{'Would update' if dry_run else 'Updated'} {len(changed)} Markdown file(s).")
    return 1 if errors else 0


def normalize_move(old: str, new: str) -> Move:
    root = find_repo_root()
    old_path = (root / old).resolve() if not Path(old).is_absolute() else Path(old).resolve()
    new_path = (root / new).resolve() if not Path(new).is_absolute() else Path(new).resolve()
    repo_relative(old_path, root)
    repo_relative(new_path, root)
    return Move(old=old_path, new=new_path)


def git_mv_or_shutil(move: Move, dry_run: bool) -> None:
    root = find_repo_root()
    if dry_run:
        print(f"would move: {repo_relative(move.old, root)} -> {repo_relative(move.new, root)}")
        return

    if not move.old.exists():
        if move.new.exists():
            print(f"move skipped, old path missing and new path exists: {repo_relative(move.new, root)}")
            return
        raise FileNotFoundError(f"Old path does not exist: {move.old}")

    move.new.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["git", "mv", str(move.old), str(move.new)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0:
        return

    shutil.move(str(move.old), str(move.new))
    stderr = result.stderr.strip()
    if stderr:
        print(f"git mv failed, used shutil.move instead: {stderr}", file=sys.stderr)


def load_moves_from_map(path: str) -> list[Move]:
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    moves_raw = data.get("moves", data if isinstance(data, list) else [])
    return [normalize_move(item["old"], item["new"]) for item in moves_raw]


def _cmd_check(args: argparse.Namespace) -> int:
    files = [Path(item) for item in args.files] if args.files else None
    return check_markdown_pathrefs(strict=args.strict, files=files)


def _cmd_rewrite_md(args: argparse.Namespace) -> int:
    return rewrite_markdown_from_pathrefs(dry_run=args.dry_run)


def _cmd_replace(args: argparse.Namespace) -> int:
    move = normalize_move(args.old, args.new)
    return apply_reference_rewrite([move], dry_run=args.dry_run)


def _cmd_move(args: argparse.Namespace) -> int:
    move = normalize_move(args.old, args.new)
    git_mv_or_shutil(move, dry_run=args.dry_run)
    return apply_reference_rewrite([move], dry_run=args.dry_run)


def _cmd_rewrite(args: argparse.Namespace) -> int:
    moves = load_moves_from_map(args.map)
    return apply_reference_rewrite(moves, dry_run=args.dry_run)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="check Markdown pathref links")
    check_parser.add_argument("--strict", action="store_true", help="also fail on unmanaged internal links")
    check_parser.add_argument(
        "--files",
        nargs="+",
        default=None,
        help="check only the given Markdown files",
    )
    check_parser.set_defaults(func=_cmd_check)

    rewrite_md_parser = subparsers.add_parser("rewrite-md", help="rewrite Markdown links from pathref comments")
    rewrite_md_parser.add_argument("--dry-run", action="store_true")
    rewrite_md_parser.set_defaults(func=_cmd_rewrite_md)

    replace_parser = subparsers.add_parser("replace", help="rewrite references from old path to new path")
    replace_parser.add_argument("old")
    replace_parser.add_argument("new")
    replace_parser.add_argument("--dry-run", action="store_true")
    replace_parser.set_defaults(func=_cmd_replace)

    move_parser = subparsers.add_parser("move", help="move a file or directory and rewrite references")
    move_parser.add_argument("old")
    move_parser.add_argument("new")
    move_parser.add_argument("--dry-run", action="store_true")
    move_parser.set_defaults(func=_cmd_move)

    rewrite_parser = subparsers.add_parser("rewrite", help="rewrite references from a moves JSON file")
    rewrite_parser.add_argument("--map", required=True)
    rewrite_parser.add_argument("--dry-run", action="store_true")
    rewrite_parser.set_defaults(func=_cmd_rewrite)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (OSError, PathAliasError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
