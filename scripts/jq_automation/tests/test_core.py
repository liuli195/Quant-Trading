from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from scripts.jq_automation.browser import CompileFailed, wait_for_compile_completion
from scripts.jq_automation.config import ConfigError, ScenarioConfig
from scripts.jq_automation.manifest import update_manifest
from scripts.jq_automation.paths import extract_backtest_id, make_run_id
from scripts.jq_automation.quota import (
    append_quota_entry,
    extract_actual_minutes_from_bundle,
    remaining_minutes,
    update_actual_minutes,
    used_minutes,
)


class CoreTests(unittest.TestCase):
    def test_scenario_config_infers_strategy_from_file_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            strategy_file = Path(tmp) / "strategies" / "demo_strategy" / "demo_strategy.py"
            strategy_file.parent.mkdir(parents=True)
            strategy_file.write_text("def initialize(context):\n    pass\n", encoding="utf-8")

            config = ScenarioConfig.from_mapping(
                {
                    "strategy_file": str(strategy_file),
                    "scenario_id": "s01-smoke",
                    "start_date": "2026-04-01",
                    "end_date": "2026-04-30",
                    "capital": "100,000",
                }
            )

            self.assertEqual(config.strategy, "demo_strategy")
            self.assertEqual(config.strategy_name, "demo_strategy")
            self.assertEqual(config.capital, 100000)
            self.assertEqual(config.frequency, "每天")
            self.assertEqual(config.py_version, "Python3")

    def test_scenario_config_rejects_reversed_dates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ConfigError, "start_date"):
                ScenarioConfig.from_mapping(
                    {
                        "strategy_file": str(Path(tmp) / "strategies" / "s" / "s.py"),
                        "strategy": "s",
                        "scenario_id": "s01",
                        "start_date": "2026-05-01",
                        "end_date": "2026-04-01",
                        "capital": 100000,
                    }
                )

    def test_backtest_id_and_run_id_helpers(self) -> None:
        self.assertEqual(
            extract_backtest_id("https://www.joinquant.com/algorithm/backtest/detail?backtestId=abc123&x=1"),
            "abc123",
        )
        self.assertEqual(extract_backtest_id("abc123"), "abc123")
        self.assertEqual(make_run_id("ab-c_123", now=datetime(2026, 5, 5, 9, 33)), "20260505-0933-btabc123")

    def test_update_manifest_preserves_existing_scenarios(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": "batch",
                        "strategy": "demo",
                        "scenarios": {
                            "s01": {"primary_run_id": None, "status": "pending"},
                            "s02": {"primary_run_id": "old", "status": "completed"},
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            updated = update_manifest(manifest_path, scenario_id="s01", run_id="run-1", status="completed")

            # After migration, primary_run_id should be gone, replaced by runs[]
            self.assertNotIn("primary_run_id", updated["scenarios"]["s01"])
            self.assertEqual(len(updated["scenarios"]["s01"]["runs"]), 1)
            s01_run = updated["scenarios"]["s01"]["runs"][0]
            self.assertEqual(s01_run["run_id"], "run-1")
            self.assertEqual(s01_run["status"], "completed")
            self.assertEqual(updated["scenarios"]["s01"]["status"], "completed")

            # s02 was not touched — its primary_run_id is preserved until
            # it receives its own update_manifest call.
            self.assertEqual(updated["scenarios"]["s02"]["primary_run_id"], "old")
            self.assertIn("updated", updated)

    def test_quota_counts_non_failed_runs(self) -> None:
        ledger = {"budget_minutes": 60, "runs": []}
        append_quota_entry(ledger, scenario_id="s01", run_id="r1", estimated_minutes=12, status="completed")
        append_quota_entry(ledger, scenario_id="s02", run_id="r2", estimated_minutes=20, status="failed")

        self.assertEqual(used_minutes(ledger), 12)
        self.assertEqual(remaining_minutes(ledger), 48)

    def test_used_minutes_prefers_actual_over_estimated(self) -> None:
        ledger = {"budget_minutes": 60, "runs": []}
        append_quota_entry(ledger, scenario_id="s01", run_id="r1", estimated_minutes=30, status="completed")
        update_actual_minutes(ledger, "r1", 0.16)
        # actual 0.16 min should be used instead of estimated 30 min
        self.assertAlmostEqual(used_minutes(ledger), 0.16)

    def test_update_actual_minutes_ignores_unknown_run_id(self) -> None:
        ledger = {"budget_minutes": 60, "runs": []}
        self.assertIsNone(update_actual_minutes(ledger, "nonexistent", 5.0))

    def test_extract_actual_minutes_from_bundle(self) -> None:
        bundle = {"runtime": {"data": {"needSeconds": 9.63}}}
        self.assertAlmostEqual(extract_actual_minutes_from_bundle(bundle), 9.63 / 60.0)

    def test_extract_actual_minutes_handles_missing_fields(self) -> None:
        self.assertIsNone(extract_actual_minutes_from_bundle({}))
        self.assertIsNone(extract_actual_minutes_from_bundle({"runtime": {}}))
        self.assertIsNone(extract_actual_minutes_from_bundle({"runtime": {"data": {}}}))
        self.assertIsNone(extract_actual_minutes_from_bundle({"runtime": {"data": {"needSeconds": 0}}}))

    def test_wait_for_compile_completion_requires_cancel_cycle(self) -> None:
        page = _FakeCompilePage(
            [
                {"hasCancel": True, "hasError": False, "bodyText": "building"},
                {"hasCancel": False, "hasError": False, "bodyText": "done"},
            ]
        )

        state = asyncio.run(wait_for_compile_completion(page, _compile_snippet, timeout_ms=1000, poll_ms=1))

        self.assertEqual(state["bodyText"], "done")
        self.assertEqual(page.sleep_count, 1)

    def test_wait_for_compile_completion_raises_on_error(self) -> None:
        page = _FakeCompilePage(
            [
                {"hasCancel": True, "hasError": False, "bodyText": "building"},
                {"hasCancel": False, "hasError": True, "bodyText": "Traceback"},
            ],
            error_text="Traceback: bad strategy",
        )

        with self.assertRaisesRegex(CompileFailed, "bad strategy"):
            asyncio.run(wait_for_compile_completion(page, _compile_snippet, timeout_ms=1000, poll_ms=1))


class _FakeCompilePage:
    def __init__(self, states: list[dict[str, object]], error_text: str = "") -> None:
        self.states = states
        self.error_text = error_text
        self.index = 0
        self.sleep_count = 0

    async def evaluate(self, expression: str, _arg: object) -> object:
        if "readCompileErrors" in expression:
            return self.error_text
        state = self.states[min(self.index, len(self.states) - 1)]
        self.index += 1
        return state

    async def wait_for_timeout(self, _milliseconds: int) -> None:
        self.sleep_count += 1


def _compile_snippet(_name: str) -> str:
    return "function readCompileState(){} function readCompileErrors(){}"


if __name__ == "__main__":
    unittest.main()
