from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.research.governance import __main__ as governance_main
from scripts.research.governance import affected, verify, verify_cache
from scripts.research.governance.affected import plan_checks


def test_docs_files_map_to_pathref_changed_files() -> None:
    plan = plan_checks(["docs/rules/commands.md"])

    assert [check.check_id for check in plan.checked] == [
        "pathref.changed-files",
        "governance.full",
    ]
    assert plan.skipped
    assert plan.full_not_run is True


def test_root_markdown_files_map_to_pathref_changed_files() -> None:
    plan = plan_checks(["AGENTS.md", "indexes.md"])

    assert [check.check_id for check in plan.checked] == [
        "pathref.changed-files",
        "governance.full",
    ]
    assert plan.checked[0].inputs == ("AGENTS.md", "indexes.md")


def test_skill_files_map_to_skill_ownership_scoped() -> None:
    plan = plan_checks(
        [
            ".codex/skills/repo-python-env/SKILL.md",
            ".claude/skills/repo-python-env/SKILL.md",
        ]
    )

    assert [check.check_id for check in plan.checked] == [
        "pathref.changed-files",
        "skill-ownership.scoped",
        "governance.full",
    ]
    assert plan.checked[1].subjects == ("repo-python-env",)
    assert plan.full_not_run is True


def test_governance_files_map_to_static_and_test_checks() -> None:
    plan = plan_checks(["scripts/research/governance/verify.py"])

    assert [check.check_id for check in plan.checked] == [
        "ruff.governance",
        "bandit.governance",
        "mypy.governance",
        "pytest.governance",
        "governance.full",
    ]
    assert [check.scope for check in plan.checked] == [
        "scoped",
        "scoped",
        "scoped",
        "scoped",
        "full",
    ]
    assert plan.full_not_run is True


def test_strategy_file_maps_to_compile_and_pytest_checks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "strategies/demo/tests").mkdir(parents=True)
    (tmp_path / "strategies/demo/demo.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    plan = plan_checks(["strategies/demo/demo.py"])

    assert [check.check_id for check in plan.checked] == [
        "py_compile.strategy",
        "pytest.strategy",
    ]
    assert plan.checked[0].inputs == ("strategies/demo/demo.py",)
    assert plan.checked[1].inputs == ("strategies/demo/tests", "strategies/demo/demo.py")


def test_multiple_strategy_files_keep_each_strategy_check(
    monkeypatch,
    tmp_path: Path,
) -> None:
    for strategy in ("alpha", "beta"):
        (tmp_path / f"strategies/{strategy}/tests").mkdir(parents=True)
        (tmp_path / f"strategies/{strategy}/{strategy}.py").write_text(
            "pass\n",
            encoding="utf-8",
        )
    monkeypatch.chdir(tmp_path)

    plan = plan_checks(["strategies/alpha/alpha.py", "strategies/beta/beta.py"])

    assert [check.check_id for check in plan.checked] == [
        "py_compile.strategy",
        "pytest.strategy",
        "py_compile.strategy",
        "pytest.strategy",
    ]
    assert [check.subjects for check in plan.checked] == [
        ("alpha",),
        ("alpha",),
        ("beta",),
        ("beta",),
    ]


def test_strategy_pytest_cache_inputs_include_changed_source(
    monkeypatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "strategies/demo/tests").mkdir(parents=True)
    (tmp_path / "strategies/demo/demo.py").write_text("VALUE = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    plan = plan_checks(["strategies/demo/demo.py"])
    pytest_check = next(check for check in plan.checked if check.check_id == "pytest.strategy")

    assert pytest_check.inputs == ("strategies/demo/tests", "strategies/demo/demo.py")


def test_strategy_compile_uses_actual_changed_python_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "strategies/value_stock_rsrs/Value_Stock_RSRS.py"
    source.parent.mkdir(parents=True)
    source.write_text("pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    plan = plan_checks(["strategies/value_stock_rsrs/Value_Stock_RSRS.py"])

    assert plan.checked[0].command == (
        "python",
        "-m",
        "py_compile",
        "strategies/value_stock_rsrs/Value_Stock_RSRS.py",
    )
    assert plan.checked[0].inputs == ("strategies/value_stock_rsrs/Value_Stock_RSRS.py",)


def test_deleted_markdown_skips_changed_file_pathref_and_runs_full_pathref(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    plan = plan_checks(["docs/deleted.md"])

    assert [check.check_id for check in plan.checked] == ["pathref.full"]


def test_deleted_strategy_source_skips_scoped_strategy_checks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    plan = plan_checks(["strategies/demo/demo.py"])

    assert plan.checked == ()


def test_dependency_files_map_to_pip_audit() -> None:
    plan = plan_checks(["requirements.txt", "requirements-dev.txt"])

    assert [check.check_id for check in plan.checked] == ["pip-audit.dependencies"]
    assert plan.checked[0].command == ("python", "-m", "pip_audit")


def test_collect_changed_files_staged_does_not_include_worktree(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git_changed_files(_root: Path, args: list[str]) -> list[str]:
        calls.append(tuple(args))
        return ["docs/staged.md"] if args == ["--cached"] else ["docs/worktree.md"]

    monkeypatch.setattr(affected, "_git_changed_files", fake_git_changed_files)

    source = affected.collect_changed_files(tmp_path, staged=True)

    assert source.files == ("docs/staged.md",)
    assert calls == [("--cached",), ()]


def test_collect_changed_files_fails_when_git_diff_fails(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 128, "", "bad revision")

    monkeypatch.setattr(affected.subprocess, "run", fake_run)

    try:
        affected.collect_changed_files(tmp_path, base="missing-ref")
    except affected.ChangedFileCollectionError as exc:
        assert "bad revision" in str(exc)
    else:
        raise AssertionError("collect_changed_files should fail closed on git errors")


def test_verify_fast_fails_when_staged_file_has_unstaged_changes(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    def fake_git_changed_files(_root: Path, args: list[str]) -> list[str]:
        if args == ["--cached"]:
            return ["docs/rules/commands.md"]
        return ["docs/rules/commands.md"]

    monkeypatch.setattr(affected, "_git_changed_files", fake_git_changed_files)

    code = verify.main(["fast", "--staged", "--format", "json", "--repo-root", str(tmp_path)])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert "unstaged changes" in payload["error"]


def test_governance_related_paths_trigger_full_governance_checks() -> None:
    plan = plan_checks(
        [
            ".githooks/pre-commit",
            ".github/workflows/research-governance.yml",
            "Makefile",
            "scripts/tools/path_tools/refactor.py",
            "scripts/research/registry/tool_registry.py",
        ]
    )

    checked = [check.check_id for check in plan.checked]
    assert "pathref.full" in checked
    assert "governance.full" in checked
    assert "pathref.changed-files" not in checked


def test_governance_cache_key_includes_actual_scan_root(tmp_path: Path) -> None:
    governance_dir = tmp_path / "scripts/research/governance"
    governance_dir.mkdir(parents=True)
    (governance_dir / "verify.py").write_text("print('verify')\n", encoding="utf-8")
    helper = governance_dir / "helper.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    check = plan_checks(["scripts/research/governance/verify.py"]).checked[0]

    first_key, _ = verify_cache.cache_key(
        tmp_path,
        check,
        ("python", "-m", "ruff", "check", "scripts/research/governance"),
    )
    helper.write_text("VALUE = 2\n", encoding="utf-8")
    second_key, _ = verify_cache.cache_key(
        tmp_path,
        check,
        ("python", "-m", "ruff", "check", "scripts/research/governance"),
    )

    assert first_key != second_key


def test_verify_explain_outputs_json_without_running_checks(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/rules").mkdir(parents=True)
    (tmp_path / "docs/rules/commands.md").write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = verify.main(
        [
            "explain",
            "--files",
            "docs/rules/commands.md",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["full_not_run"] is True
    assert payload["checked"][0]["check_id"] == "pathref.changed-files"
    assert "skill-ownership.scoped" in [
        item["check_id"] for item in payload["skipped"]
    ]


def test_verify_explain_default_text_names_checked_skipped_and_full_not_run(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/rules").mkdir(parents=True)
    (tmp_path / "docs/rules/commands.md").write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    code = verify.main(["explain", "--files", "docs/rules/commands.md"])

    assert code == 0
    output = capsys.readouterr().out
    assert "checked:" in output
    assert "skipped:" in output
    assert "full-not-run: true" in output


def test_docs_rules_fast_runs_changed_file_pathref_and_full_gate(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/rules").mkdir(parents=True)
    (tmp_path / "docs/rules/commands.md").write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(
        [
            "fast",
            "--files",
            "docs/rules/commands.md",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["full_not_run"] is True
    assert [item["check_id"] for item in payload["checked"]] == [
        "pathref.changed-files",
        "governance.full",
    ]
    assert any("scripts.tools.path_tools.refactor" in call for call in calls)
    assert any("scripts.research.governance" in call and "gate" in call for call in calls)


def test_skill_fast_runs_skill_ownership_and_full_gate(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / ".codex/skills/repo-python-env").mkdir(parents=True)
    skill_file = tmp_path / ".codex/skills/repo-python-env/SKILL.md"
    skill_file.write_text("# Skill\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(
        [
            "fast",
            "--files",
            ".codex/skills/repo-python-env/SKILL.md",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["check_id"] for item in payload["checked"]] == [
        "pathref.changed-files",
        "skill-ownership.scoped",
        "governance.full",
    ]
    assert payload["checked"][1]["subjects"] == ["repo-python-env"]
    assert any("scripts.research.governance.skill_ownership" in call for call in calls)
    assert any("scripts.research.governance" in call and "gate" in call for call in calls)


def test_governance_fast_runs_scoped_static_checks_and_full_gate(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "scripts/research/governance").mkdir(parents=True)
    changed = tmp_path / "scripts/research/governance/verify.py"
    changed.write_text("# verify\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(
        [
            "fast",
            "--files",
            "scripts/research/governance/verify.py",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["check_id"] for item in payload["checked"]] == [
        "ruff.governance",
        "bandit.governance",
        "mypy.governance",
        "pytest.governance",
        "governance.full",
    ]
    assert [item["scope"] for item in payload["checked"]] == [
        "scoped",
        "scoped",
        "scoped",
        "scoped",
        "full",
    ]
    assert any("ruff" in call for call in calls)
    assert any("bandit" in call for call in calls)
    assert any("mypy" in call for call in calls)
    pytest_call = next(call for call in calls if "pytest" in call)
    assert "scripts/research/governance/tests" in pytest_call
    assert ".local/pytest-tmp/governance-fast" in pytest_call
    assert "-p" in pytest_call
    assert "no:cacheprovider" in pytest_call
    assert any("scripts.research.governance" in call and "gate" in call for call in calls)


def test_strategy_fast_skips_pytest_when_tests_dir_is_missing(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "strategies/demo").mkdir(parents=True)
    (tmp_path / "strategies/demo/demo.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(
        [
            "fast",
            "--files",
            "strategies/demo/demo.py",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checked"][0]["check_id"] == "py_compile.strategy"
    assert payload["checked"][1]["check_id"] == "pytest.strategy"
    assert payload["checked"][1]["skipped"] is True
    assert any("py_compile" in call for call in calls)
    assert not any("pytest" in call for call in calls)


def test_strategy_fast_runs_pytest_when_tests_dir_exists(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "strategies/demo/tests").mkdir(parents=True)
    (tmp_path / "strategies/demo/demo.py").write_text("pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(
        [
            "fast",
            "--files",
            "strategies/demo/demo.py",
            "--format",
            "json",
        ]
    )

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checked"][1]["skipped"] is False
    pytest_call = next(call for call in calls if "pytest" in call and "strategies/demo/tests" in call)
    assert ".local/pytest-tmp/strategy-demo-fast" in pytest_call


def test_dependency_fast_runs_pip_audit(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "requirements.txt").write_text("pytest\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(["fast", "--files", "requirements.txt", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checked"][0]["check_id"] == "pip-audit.dependencies"
    assert any("pip_audit" in call for call in calls)


def test_fast_cache_hits_for_same_passed_input(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/guides").mkdir(parents=True)
    changed = tmp_path / "docs/guides/commands.md"
    changed.write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.main(["fast", "--files", "docs/guides/commands.md", "--format", "json"]) == 0
    capsys.readouterr()
    assert verify.main(["fast", "--files", "docs/guides/commands.md", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(calls) == 1
    assert payload["checked"][0]["cache_hit"] is True
    assert (tmp_path / ".local/governance-cache").is_dir()


def test_fast_cache_invalidates_when_input_content_changes(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/guides").mkdir(parents=True)
    changed = tmp_path / "docs/guides/commands.md"
    changed.write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.main(["fast", "--files", "docs/guides/commands.md", "--format", "json"]) == 0
    capsys.readouterr()
    changed.write_text("# Commands\n\nUpdated.\n", encoding="utf-8")
    assert verify.main(["fast", "--files", "docs/guides/commands.md", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(calls) == 2
    assert payload["checked"][0]["cache_hit"] is False


def test_fast_cache_does_not_store_failed_results(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/guides").mkdir(parents=True)
    changed = tmp_path / "docs/guides/commands.md"
    changed.write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls = 0

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, 1 if calls == 1 else 0, "", "boom")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.main(["fast", "--files", "docs/guides/commands.md", "--format", "json"]) == 1
    capsys.readouterr()
    assert verify.main(["fast", "--files", "docs/guides/commands.md", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert calls == 2
    assert payload["checked"][0]["cache_hit"] is False


def test_verify_full_runs_complete_command_chain(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    code = verify.main(["full", "--format", "json"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    modules = [call[call.index("-m") + 1] for call in calls if "-m" in call]
    assert modules == [
        "ruff",
        "bandit",
        "mypy",
        "pip_audit",
        "pytest",
        "scripts.tools.path_tools.refactor",
        "scripts.research.governance",
    ]
    assert calls[-1][-1] == "gate"
    pytest_call = next(call for call in calls if "pytest" in call)
    assert ".local/pytest-tmp/verify-full" in pytest_call
    assert "-p" in pytest_call
    assert "no:cacheprovider" in pytest_call


def test_governance_main_forwards_verify_command(monkeypatch) -> None:
    captured: list[str] = []

    def fake_verify_main(argv: list[str]) -> int:
        captured.extend(argv)
        return 0

    monkeypatch.setattr(governance_main, "verify_main", fake_verify_main)

    code = governance_main.main(["verify", "explain", "--files", "docs/a.md"])

    assert code == 0
    assert captured == ["explain", "--files", "docs/a.md"]
