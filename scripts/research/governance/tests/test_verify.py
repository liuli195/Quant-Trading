from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.research.governance import __main__ as governance_main
from scripts.research.governance import affected, verify
from scripts.research.governance.affected import plan_checks


def test_docs_files_map_to_pathref_changed_files() -> None:
    plan = plan_checks(["docs/rules/commands.md"])

    assert [check.check_id for check in plan.checked] == ["pathref.changed-files"]
    assert plan.skipped
    assert plan.full_not_run is True


def test_skill_files_map_to_skill_ownership_scoped() -> None:
    plan = plan_checks(
        [
            ".codex/skills/repo-python-env/SKILL.md",
            ".claude/skills/repo-python-env/SKILL.md",
        ]
    )

    assert [check.check_id for check in plan.checked] == ["skill-ownership.scoped"]
    assert plan.checked[0].subjects == ("repo-python-env",)
    assert plan.full_not_run is True


def test_governance_files_map_to_static_and_test_checks() -> None:
    plan = plan_checks(["scripts/research/governance/verify.py"])

    assert [check.check_id for check in plan.checked] == [
        "ruff.governance",
        "bandit.governance",
        "mypy.governance",
        "pytest.governance",
    ]
    assert all(check.scope == "scoped" for check in plan.checked)
    assert plan.full_not_run is True


def test_strategy_file_maps_to_compile_and_pytest_checks() -> None:
    plan = plan_checks(["strategies/demo/demo.py"])

    assert [check.check_id for check in plan.checked] == [
        "py_compile.strategy",
        "pytest.strategy",
    ]
    assert plan.checked[0].inputs == ("strategies/demo/demo.py",)
    assert plan.checked[1].inputs == ("strategies/demo/tests",)


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
    assert calls == [("--cached",)]


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


def test_docs_fast_runs_changed_file_pathref_without_full_gate(
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
    assert payload["checked"][0]["check_id"] == "pathref.changed-files"
    assert any("scripts.tools.path_tools.refactor" in call for call in calls)
    assert not any("scripts.research.governance" in call for call in calls)


def test_skill_fast_runs_skill_ownership_without_full_gate(
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
    assert payload["checked"][0]["check_id"] == "skill-ownership.scoped"
    assert payload["checked"][0]["subjects"] == ["repo-python-env"]
    assert any("scripts.research.governance.skill_ownership" in call for call in calls)
    assert not any(call == ["scripts.research.governance", "gate"] for call in calls)


def test_governance_fast_runs_scoped_static_checks_without_full_gate(
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
    ]
    assert all(item["scope"] == "scoped" for item in payload["checked"])
    assert any("ruff" in call for call in calls)
    assert any("bandit" in call for call in calls)
    assert any("mypy" in call for call in calls)
    assert any("pytest" in call for call in calls)
    assert not any("scripts.research.governance" in call and "gate" in call for call in calls)


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
    assert any("pytest" in call and "strategies/demo/tests" in call for call in calls)


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
    (tmp_path / "docs/rules").mkdir(parents=True)
    changed = tmp_path / "docs/rules/commands.md"
    changed.write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.main(["fast", "--files", "docs/rules/commands.md", "--format", "json"]) == 0
    capsys.readouterr()
    assert verify.main(["fast", "--files", "docs/rules/commands.md", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(calls) == 1
    assert payload["checked"][0]["cache_hit"] is True
    assert (tmp_path / ".local/governance-cache").is_dir()


def test_fast_cache_invalidates_when_input_content_changes(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/rules").mkdir(parents=True)
    changed = tmp_path / "docs/rules/commands.md"
    changed.write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "ok\n", "")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.main(["fast", "--files", "docs/rules/commands.md", "--format", "json"]) == 0
    capsys.readouterr()
    changed.write_text("# Commands\n\nUpdated.\n", encoding="utf-8")
    assert verify.main(["fast", "--files", "docs/rules/commands.md", "--format", "json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert len(calls) == 2
    assert payload["checked"][0]["cache_hit"] is False


def test_fast_cache_does_not_store_failed_results(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    (tmp_path / "docs/rules").mkdir(parents=True)
    changed = tmp_path / "docs/rules/commands.md"
    changed.write_text("# Commands\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    calls = 0

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return subprocess.CompletedProcess(command, 1 if calls == 1 else 0, "", "boom")

    monkeypatch.setattr(verify.subprocess, "run", fake_run)

    assert verify.main(["fast", "--files", "docs/rules/commands.md", "--format", "json"]) == 1
    capsys.readouterr()
    assert verify.main(["fast", "--files", "docs/rules/commands.md", "--format", "json"]) == 0
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


def test_governance_main_forwards_verify_command(monkeypatch) -> None:
    captured: list[str] = []

    def fake_verify_main(argv: list[str]) -> int:
        captured.extend(argv)
        return 0

    monkeypatch.setattr(governance_main, "verify_main", fake_verify_main)

    code = governance_main.main(["verify", "explain", "--files", "docs/a.md"])

    assert code == 0
    assert captured == ["explain", "--files", "docs/a.md"]
