"""Skill ownership index loader, discovery, and governance checks."""

from __future__ import annotations

import argparse
import importlib.util
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import yaml

from scripts.research.registry import default_tool_registry


REQUIRED_OWNER_SKILLS = (
    "skill-system",
    "repo-python-env",
    "repo-docs-pathref",
    "repo-pr-governance",
    "research-local-first",
    "research-data-center",
    "research-report-analysis",
    "strategy-experiment",
    "joinquant-strategy-fix",
    "joinquant-cloud-run",
)
REQUIRED_FIELDS = (
    "skill",
    "group",
    "owned_rules",
    "owned_commands",
    "owned_scripts",
    "uses",
    "adapters",
    "trigger_phrases",
    "read_rules",
    "recommended_commands",
    "status",
)
VALID_COMMAND_PREFIXES = (
    ".\\.venv\\Scripts\\python.exe",
    ".venv/bin/python",
    "make ",
    "jq-auto ",
)
OWNED_LOCAL_SCRIPT_PREFIXES = (".\\.githooks\\", ".githooks/")
VALID_PYTHON_OWNED_ARGS = {
    "scripts.research.docs": ((), ("index",)),
    "scripts.research.governance": ((), ("audit",)),
    "scripts.research.governance.pr_flow": ((), ("ready",), ("diagnose",)),
    "scripts.tools.jq_automation": (
        (),
        ("compile-check",),
        ("upload",),
        ("run",),
        ("fetch",),
        ("batch",),
        ("ab",),
    ),
    "scripts.tools.path_tools.refactor": (
        (),
        ("check",),
        ("rewrite-md",),
        ("replace",),
        ("move",),
        ("rewrite",),
    ),
    "scripts.tools.path_tools.aliases": ((), ("resolve",), ("list",), ("validate",)),
    "scripts.research.registry.tool_registry": (
        (),
        ("list",),
        ("validate",),
        ("write-layers",),
    ),
    "scripts.research.governance.skill_ownership": ((), ("check",), ("discover",)),
}
VALID_JQ_AUTO_COMMANDS = {
    "compile-check": (),
    "upload": (),
    "run": (),
    "fetch": (),
    "batch": (),
    "ab": ((), ("expand",), ("run",), ("report",)),
}
LEGACY_SKILL_DIRS = (
    ".claude/skills/agent-doc-add",
    ".claude/skills/agent-doc-refactor",
    ".claude/skills/jq-ab-test",
    ".claude/skills/jq-analyze",
    ".claude/skills/jq-fix",
    ".claude/skills/jq-param-scan",
    ".claude/skills/jq-research",
    ".claude/skills/jq-run",
    ".codex/skills/quant-pr-workflow",
    ".codex/skills/quant-research-workflow",
)
SKILLS_DOC_FORBIDDEN_DETAIL_TOKENS = (
    "owned_rules:",
    "owned_commands:",
    "owned_scripts:",
    "trigger_phrases:",
    "recommended_commands:",
)


@dataclass(frozen=True)
class SkillOwnership:
    skill: str
    group: str
    owned_rules: tuple[str, ...]
    owned_commands: tuple[str, ...]
    owned_scripts: tuple[str, ...]
    uses: tuple[str, ...]
    adapters: tuple[str, ...]
    trigger_phrases: tuple[str, ...]
    read_rules: tuple[str, ...]
    recommended_commands: tuple[str, ...]
    status: str
    source_path: str


@dataclass(frozen=True)
class DiscoveryResult:
    query: str
    matches: tuple[SkillOwnership, ...]


def _tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(str(item) for item in value)
    return (str(value),)


def _normalize_phrase(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _significant_tokens(value: str) -> set[str]:
    normalized = _normalize_phrase(value)
    ascii_tokens = set(re.findall(r"[a-z0-9_.+-]+", normalized))
    chinese = re.sub(r"[a-z0-9_.+-]+", " ", normalized)
    for token in (
        "这个",
        "仓库",
        "本地",
        "项目",
        "应该",
        "怎么",
        "如何",
        "为什么",
        "不能",
        "使用",
        "用",
        "和",
        "并",
        "吗",
    ):
        chinese = chinese.replace(token, " ")
    chinese = re.sub(r"[^\u4e00-\u9fff]+", " ", chinese)
    chinese_tokens = {token for token in chinese.split() if token}
    return ascii_tokens | chinese_tokens


def _base_rule_path(value: str) -> str:
    return value.split("#", 1)[0]


def _path_reference_errors(
    root: Path,
    ownership: SkillOwnership,
    value: str,
    field_name: str,
) -> list[str]:
    path_text, _, anchor = value.partition("#")
    if not path_text or not (root / path_text).exists():
        return [f"missing {field_name} for {ownership.skill}: {value}"]
    path = root / path_text
    if anchor and path.suffix.lower() == ".md" and not _markdown_anchor_exists(
        path, anchor
    ):
        return [
            f"missing markdown anchor in {field_name} for {ownership.skill}: {value}"
        ]
    return []


def _markdown_anchor_exists(path: Path, anchor: str) -> bool:
    return anchor in _markdown_anchors(path)


def _markdown_anchors(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    anchors: set[str] = set()
    for match in re.finditer(
        r"<a\s+(?:[^>]*\s)?(?:id|name)=[\"']([^\"']+)[\"']",
        text,
        flags=re.IGNORECASE,
    ):
        anchors.add(match.group(1))
    seen: dict[str, int] = {}
    for line in text.splitlines():
        heading_match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if heading_match is None:
            continue
        slug = _markdown_heading_slug(heading_match.group(1))
        if not slug:
            continue
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def _markdown_heading_slug(heading: str) -> str:
    heading = re.sub(r"<[^>]+>", "", heading)
    heading = heading.replace("`", "")
    heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
    slug = heading.casefold()
    slug = re.sub(r"[^\w\u4e00-\u9fff\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug


def _command_covers(owner_command: str, required_command: str) -> bool:
    owner = owner_command.strip()
    required = required_command.strip()
    if owner == required:
        return True
    if required.startswith(owner + " "):
        return not _is_bare_python_command(owner)
    if owner.startswith(required + " "):
        return _owned_command_tail_is_valid(owner)
    return False


def _is_bare_python_command(command: str) -> bool:
    return command in {".\\.venv\\Scripts\\python.exe", ".venv/bin/python"}


def _owned_command_tail_is_valid(command: str) -> bool:
    parsed = _python_command_parts(command)
    if parsed is not None:
        module, args = parsed
        return args in VALID_PYTHON_OWNED_ARGS.get(module, ((),))
    return _jq_auto_command_exists(command)


def _script_command_exists(root: Path, command: str) -> bool:
    script = command.split(maxsplit=1)[0].replace("\\", "/")
    if script.startswith("./"):
        script = script[2:]
    return (root / script).exists()


def _has_supported_command_prefix(command: str, field_name: str) -> bool:
    if command.startswith(VALID_COMMAND_PREFIXES):
        return True
    return field_name == "owned command" and command.startswith(
        OWNED_LOCAL_SCRIPT_PREFIXES
    )


def _command_reference_errors(
    root: Path,
    ownership: SkillOwnership,
    command: str,
    field_name: str,
    *,
    require_supported_prefix: bool,
) -> list[str]:
    errors: list[str] = []
    if require_supported_prefix and not _has_supported_command_prefix(
        command, field_name
    ):
        errors.append(f"unsupported {field_name} for {ownership.skill}: {command}")
        return errors
    if field_name == "owned command" and any(
        token.startswith("--") for token in command.split()
    ):
        errors.append(
            f"owned command for {ownership.skill} must be a command prefix: {command}"
        )
    module = _python_module_from_command(command)
    if module is not None and not _module_exists(root, module):
        errors.append(
            f"unknown python module in {field_name} for {ownership.skill}: {module}"
        )
    if field_name == "owned command" and module is not None:
        parsed = _python_command_parts(command)
        args = parsed[1] if parsed is not None else ()
        if args not in VALID_PYTHON_OWNED_ARGS.get(module, ((),)):
            rendered_args = " ".join(args)
            errors.append(
                f"unsupported python command arguments in {field_name} for {ownership.skill}: {module} {rendered_args}"
            )
    if not _make_target_exists(root, command):
        errors.append(
            f"unknown make target in {field_name} for {ownership.skill}: {command}"
        )
    if not _jq_auto_command_exists(command):
        errors.append(
            f"unknown jq-auto command in {field_name} for {ownership.skill}: {command}"
        )
    if command.startswith((".\\.githooks\\", ".githooks/")) and not _script_command_exists(
        root, command
    ):
        errors.append(f"missing script in {field_name} for {ownership.skill}: {command}")
    return errors


def _discover_make_targets(root: Path) -> tuple[str, ...]:
    makefile = root / "Makefile"
    if not makefile.is_file():
        return ()
    text = makefile.read_text(encoding="utf-8", errors="ignore")
    targets: list[str] = []
    for match in re.finditer(
        r"^([A-Za-z0-9_.-]+)\s*:(?!=)", text, flags=re.MULTILINE
    ):
        target = match.group(1)
        if target.startswith("."):
            continue
        targets.append(f"make {target}")
    return tuple(sorted(set(targets)))


def _registered_cli_commands() -> tuple[str, ...]:
    commands: list[str] = []
    for tool in default_tool_registry().tools:
        if tool.kind != "cli":
            continue
        command = tool.cli or ""
        if command:
            commands.append(command)
    return tuple(sorted(set(commands)))


def _description_covers_phrase(description: str, phrase: str) -> bool:
    phrase_tokens = _significant_tokens(phrase)
    if not phrase_tokens:
        return True
    description_tokens = _significant_tokens(description)
    if phrase_tokens & description_tokens:
        return True
    phrase_chinese = re.sub(r"[^\u4e00-\u9fff]+", "", phrase)
    description_chinese = re.sub(r"[^\u4e00-\u9fff]+", "", description)
    phrase_grams = {
        phrase_chinese[index : index + 2]
        for index in range(max(0, len(phrase_chinese) - 1))
    }
    return any(gram in description_chinese for gram in phrase_grams)


def _phrase_matches_query(phrase: str, query: str) -> bool:
    normalized_phrase = _normalize_phrase(phrase)
    normalized_query = _normalize_phrase(query)
    if normalized_phrase in normalized_query or normalized_query in normalized_phrase:
        return True
    query_tokens = _significant_tokens(query)
    if not query_tokens:
        return False
    return query_tokens.issubset(_significant_tokens(phrase))


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _ownership_paths(root: Path) -> tuple[Path, ...]:
    return tuple(sorted((root / ".codex" / "skills").glob("*/references/ownership.yaml")))


def _load_ownership(path: Path, root: Path) -> SkillOwnership:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: ownership.yaml must be a mapping")
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ValueError(f"{path}: missing fields: {', '.join(missing)}")
    return SkillOwnership(
        skill=str(data["skill"]),
        group=str(data["group"]),
        owned_rules=_tuple(data.get("owned_rules")),
        owned_commands=_tuple(data.get("owned_commands")),
        owned_scripts=_tuple(data.get("owned_scripts")),
        uses=_tuple(data.get("uses")),
        adapters=_tuple(data.get("adapters")),
        trigger_phrases=_tuple(data.get("trigger_phrases")),
        read_rules=_tuple(data.get("read_rules")),
        recommended_commands=_tuple(data.get("recommended_commands")),
        status=str(data.get("status", "active")),
        source_path=path.relative_to(root).as_posix(),
    )


def load_ownerships(repo_root: str | Path = ".") -> tuple[SkillOwnership, ...]:
    """Load all ownership records from `.codex/skills/*/references/ownership.yaml`."""

    root = Path(repo_root).resolve()
    return tuple(_load_ownership(path, root) for path in _ownership_paths(root))


def _discover_owner_from_ownerships(
    ownerships: Iterable[SkillOwnership], query: str
) -> DiscoveryResult:
    matches: list[SkillOwnership] = []
    for ownership in ownerships:
        if ownership.status != "active":
            continue
        phrases = (ownership.skill, *ownership.trigger_phrases)
        if any(phrase and _phrase_matches_query(phrase, query) for phrase in phrases):
            matches.append(ownership)
    return DiscoveryResult(query=query, matches=tuple(matches))


def discover_owner(repo_root: str | Path, query: str) -> DiscoveryResult:
    """Return active owner skills whose name or trigger phrases match the query."""

    return _discover_owner_from_ownerships(load_ownerships(repo_root), query)


def _python_module_from_command(command: str) -> str | None:
    parsed = _python_command_parts(command)
    return parsed[0] if parsed is not None else None


def _python_command_parts(command: str) -> tuple[str, tuple[str, ...]] | None:
    match = re.match(
        r"^(?:\.\\\.venv\\Scripts\\python\.exe|\.venv/bin/python)\s+-m\s+([A-Za-z0-9_.]+)(?:\s+(.*))?$",
        command,
    )
    if not match:
        return None
    return match.group(1), tuple((match.group(2) or "").split())


def _module_exists(root: Path, module: str) -> bool:
    if module.startswith("scripts."):
        module_path = root.joinpath(*module.split("."))
        return (
            module_path.with_suffix(".py").exists()
            or (module_path / "__init__.py").exists()
            or module_path.is_dir()
        )
    try:
        return importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        return False


def _make_target_exists(root: Path, command: str) -> bool:
    match = re.match(r"^make\s+([A-Za-z0-9_.-]+)", command)
    if not match:
        return True
    makefile = root / "Makefile"
    if not makefile.is_file():
        return False
    target = re.escape(match.group(1))
    return re.search(
        rf"^{target}\s*:",
        makefile.read_text(encoding="utf-8", errors="ignore"),
        flags=re.MULTILINE,
    ) is not None


def _jq_auto_command_exists(command: str) -> bool:
    match = re.match(r"^jq-auto\s+([A-Za-z0-9_-]+)(?:\s+([A-Za-z0-9_-]+))?$", command)
    if not match:
        return not command.startswith("jq-auto ")
    command_name = match.group(1)
    if command_name not in VALID_JQ_AUTO_COMMANDS:
        return False
    args = tuple(arg for arg in (match.group(2),) if arg)
    return args in VALID_JQ_AUTO_COMMANDS[command_name]


def validate_ownerships(repo_root: str | Path = ".") -> list[str]:
    """Validate skill ownership records for governance gate integration."""

    root = Path(repo_root).resolve()
    errors: list[str] = []
    ownerships: list[SkillOwnership] = []
    seen_records: dict[str, str] = {}

    for path in _ownership_paths(root):
        try:
            ownership = _load_ownership(path, root)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if ownership.skill in seen_records:
            errors.append(
                f"duplicate owner skill record for {ownership.skill}: "
                f"{seen_records[ownership.skill]} and {ownership.source_path}"
            )
            continue
        seen_records[ownership.skill] = ownership.source_path
        ownerships.append(ownership)

    by_skill = {item.skill: item for item in ownerships}
    for ownership in ownerships:
        expected_source = f".codex/skills/{ownership.skill}/references/ownership.yaml"
        if ownership.source_path != expected_source:
            errors.append(
                f"owner skill {ownership.skill} has mismatched ownership path: {ownership.source_path}"
            )

    for owner_path in sorted((root / ".codex" / "skills").glob("*/SKILL.md")):
        skill = owner_path.parent.name
        if skill not in seen_records:
            owner_rel = owner_path.relative_to(root).as_posix()
            errors.append(f"unowned Codex owner skill: {owner_rel}")

    for skill in REQUIRED_OWNER_SKILLS:
        required_ownership = by_skill.get(skill)
        if required_ownership is None:
            errors.append(f"missing owner skill: {skill}")
            continue
        if required_ownership.status != "active":
            errors.append(f"required owner skill must be active: {skill}")
        if not (root / ".codex" / "skills" / skill / "SKILL.md").is_file():
            errors.append(f"missing Codex owner SKILL.md: {skill}")
        if not (root / ".codex" / "skills" / skill / "agents" / "openai.yaml").is_file():
            errors.append(f"missing Codex owner openai agent manifest: {skill}")

    for legacy_dir in LEGACY_SKILL_DIRS:
        if (root / legacy_dir).exists():
            errors.append(f"legacy skill directory must be removed: {legacy_dir}")

    seen_owned: dict[tuple[str, str], str] = {}
    seen_triggers: dict[str, str] = {}
    declared_adapters = {
        adapter for ownership in ownerships for adapter in ownership.adapters
    }
    owned_rule_paths = {
        _base_rule_path(rule)
        for ownership in ownerships
        for rule in ownership.owned_rules
        if rule.startswith("docs/rules/")
    }
    owned_commands = tuple(
        command for ownership in ownerships for command in ownership.owned_commands
    )
    for ownership in ownerships:
        for field_name in ("owned_rules", "owned_commands", "owned_scripts"):
            for value in getattr(ownership, field_name):
                key = (field_name, value)
                previous = seen_owned.get(key)
                if previous is not None:
                    errors.append(
                        f"duplicate {field_name} owner for {value}: "
                        f"{previous} and {ownership.skill}"
                    )
                else:
                    seen_owned[key] = ownership.skill

        for script in ownership.owned_scripts:
            errors.extend(
                _path_reference_errors(root, ownership, script, "owned script")
            )

        for rule in ownership.owned_rules:
            errors.extend(_path_reference_errors(root, ownership, rule, "owned rule"))

        expected_adapter = f".claude/skills/{ownership.skill}/SKILL.md"
        if expected_adapter not in ownership.adapters:
            errors.append(
                f"owner skill {ownership.skill} missing same-name Claude adapter: {expected_adapter}"
            )

        if ownership.status == "active":
            for phrase in ownership.trigger_phrases:
                normalized = _normalize_phrase(phrase)
                previous = seen_triggers.get(normalized)
                if previous is not None:
                    errors.append(
                        f'duplicate trigger phrase "{phrase}": {previous} and {ownership.skill}'
                    )
                else:
                    seen_triggers[normalized] = ownership.skill

        for command in ownership.owned_commands:
            errors.extend(
                _command_reference_errors(
                    root,
                    ownership,
                    command,
                    "owned command",
                    require_supported_prefix=True,
                )
            )

        for command in ownership.recommended_commands:
            errors.extend(
                _command_reference_errors(
                    root,
                    ownership,
                    command,
                    "recommended command",
                    require_supported_prefix=True,
                )
            )

        for rule in ownership.read_rules:
            errors.extend(_path_reference_errors(root, ownership, rule, "read rule"))

        owner_path = root / ".codex" / "skills" / ownership.skill / "SKILL.md"
        owner_text = ""
        owner_meta: dict[str, object] = {}
        if owner_path.is_file():
            owner_text = owner_path.read_text(encoding="utf-8", errors="ignore")
            owner_meta = _frontmatter(owner_path)
        owner_name = str(owner_meta.get("name", "")).strip()
        if not owner_name:
            errors.append(f"owner SKILL.md missing frontmatter name for {ownership.skill}")
        elif owner_name != ownership.skill:
            errors.append(f"owner SKILL.md name mismatch for {ownership.skill}")
        owner_description = str(owner_meta.get("description", "")).strip()
        if not owner_description:
            errors.append(
                f"owner SKILL.md missing frontmatter description for {ownership.skill}"
            )
        for rule in ownership.read_rules:
            if owner_text and rule not in owner_text:
                errors.append(f"owner SKILL.md missing read rule for {ownership.skill}: {rule}")
        for command in ownership.recommended_commands:
            if owner_text and command not in owner_text:
                errors.append(
                    f"owner SKILL.md missing recommended command for {ownership.skill}: {command}"
                )
        for phrase in ownership.trigger_phrases:
            result = _discover_owner_from_ownerships(ownerships, phrase)
            matched_skills = tuple(match.skill for match in result.matches)
            if matched_skills != (ownership.skill,):
                errors.append(
                    f'trigger phrase "{phrase}" is ambiguous for {ownership.skill}: '
                    + ", ".join(matched_skills or ("no match",))
                )
            if owner_description and not _description_covers_phrase(
                owner_description, phrase
            ):
                errors.append(
                    f"trigger phrase not covered by owner description for {ownership.skill}: {phrase}"
                )

        for adapter in ownership.adapters:
            adapter_path = root / adapter
            if not adapter_path.is_file():
                errors.append(f"missing adapter for {ownership.skill}: {adapter}")
                continue
            adapter_text = adapter_path.read_text(encoding="utf-8", errors="ignore")
            for forbidden in ("owned_rules", "owned_commands", "owned_scripts"):
                if forbidden in adapter_text:
                    errors.append(f"adapter {adapter} must not declare {forbidden}")
            for rule in ownership.read_rules:
                if rule not in adapter_text:
                    errors.append(f"adapter {adapter} missing read rule: {rule}")
            for command in ownership.recommended_commands:
                if command not in adapter_text:
                    errors.append(
                        f"adapter {adapter} missing recommended command: {command}"
                    )
            adapter_meta = _frontmatter(adapter_path)
            adapter_name = str(adapter_meta.get("name", "")).strip()
            if not adapter_name:
                errors.append(f"adapter {adapter} missing frontmatter name")
            elif adapter_name != ownership.skill:
                errors.append(f"adapter {adapter} name does not match {ownership.skill}")
            adapter_description = str(adapter_meta.get("description", "")).strip()
            if not adapter_description:
                errors.append(f"adapter {adapter} missing frontmatter description")
            elif owner_description and not (
                owner_description in adapter_description
                or adapter_description in owner_description
            ):
                errors.append(
                    f"adapter {adapter} description is not equivalent to {ownership.skill}"
                )
            for phrase in ownership.trigger_phrases:
                if adapter_description and not _description_covers_phrase(
                    adapter_description, phrase
                ):
                    errors.append(
                        f"trigger phrase not covered by adapter description for {ownership.skill}: {phrase}"
                    )

    for adapter_path in sorted((root / ".claude" / "skills").glob("*/SKILL.md")):
        adapter_rel = adapter_path.relative_to(root).as_posix()
        if adapter_rel not in declared_adapters:
            errors.append(f"unowned Claude skill adapter: {adapter_rel}")

    for path in sorted((root / "docs" / "rules").glob("*.md")):
        rel_path = path.relative_to(root).as_posix()
        if rel_path not in owned_rule_paths:
            errors.append(f"rule doc missing owner: {rel_path}")

    for command in (*_discover_make_targets(root), *_registered_cli_commands()):
        if not any(_command_covers(owner_command, command) for owner_command in owned_commands):
            errors.append(f"make target missing owner: {command}" if command.startswith("make ") else f"registered CLI missing owner: {command}")

    skills_doc = root / "docs" / "rules" / "skills.md"
    if skills_doc.is_file():
        text = skills_doc.read_text(encoding="utf-8", errors="ignore")
        if "## Owner Skill 汇总" not in text:
            errors.append("skills.md missing owner skill summary")
        for skill in REQUIRED_OWNER_SKILLS:
            if f"`{skill}`" not in text:
                errors.append(f"skills.md missing owner skill summary entry: {skill}")
        for token in SKILLS_DOC_FORBIDDEN_DETAIL_TOKENS:
            if token in text:
                errors.append(f"skills.md must not duplicate ownership detail: {token}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check")
    discover_parser = subparsers.add_parser("discover")
    discover_parser.add_argument("query")
    args = parser.parse_args(argv)

    if args.command == "check":
        errors = validate_ownerships(Path.cwd())
        for error in errors:
            print(error)
        return 1 if errors else 0

    result = discover_owner(Path.cwd(), args.query)
    for match in result.matches:
        print(match.skill)
        print("read_rules=" + ",".join(match.read_rules))
        print("recommended_commands=" + ",".join(match.recommended_commands))
    return 0 if len(result.matches) == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
