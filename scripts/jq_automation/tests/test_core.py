from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.jq_automation import artifacts
from scripts.jq_automation.browser import CompileFailed, wait_for_compile_completion
from scripts.jq_automation.cli import _bundle_options
from scripts.jq_automation.config import ConfigError, ScenarioConfig
from scripts.jq_automation.local import LocalCheckError, apply_params_overrides
from scripts.jq_automation.manifest import list_pending_runs, update_manifest
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
            self.assertEqual(config.frequency, "1d")
            self.assertEqual(config.py_version, "Python3")

    def test_normalize_frequency_accepts_english_aliases(self) -> None:
        from scripts.jq_automation.config import _normalize_frequency

        self.assertEqual(_normalize_frequency("1d"), "1d")
        self.assertEqual(_normalize_frequency("day"), "1d")
        self.assertEqual(_normalize_frequency("daily"), "1d")
        self.assertEqual(_normalize_frequency("d"), "1d")
        self.assertEqual(_normalize_frequency("1m"), "1m")
        self.assertEqual(_normalize_frequency("minute"), "1m")
        self.assertEqual(_normalize_frequency("m"), "1m")
        self.assertEqual(_normalize_frequency("tick"), "tick")
        self.assertEqual(_normalize_frequency("5m"), "5m")
        self.assertEqual(_normalize_frequency("60m"), "60m")

    def test_normalize_frequency_accepts_chinese_display_text(self) -> None:
        from scripts.jq_automation.config import _normalize_frequency

        self.assertEqual(_normalize_frequency("每天"), "1d")
        self.assertEqual(_normalize_frequency("每分钟"), "1m")

    def test_normalize_frequency_rejects_unknown_value(self) -> None:
        from scripts.jq_automation.config import _normalize_frequency, ConfigError

        with self.assertRaises(ConfigError):
            _normalize_frequency("每周")
        with self.assertRaises(ConfigError):
            _normalize_frequency("monthly")
        with self.assertRaises(ConfigError):
            _normalize_frequency("")

    def test_scenario_config_rejects_unknown_frequency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ConfigError):
                ScenarioConfig.from_mapping(
                    {
                        "strategy_file": str(Path(tmp) / "strategies" / "s" / "s.py"),
                        "strategy": "s",
                        "scenario_id": "s01",
                        "start_date": "2026-04-01",
                        "end_date": "2026-05-01",
                        "capital": 100000,
                        "frequency": "每周",
                    }
                )

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

    def test_scenario_config_rejects_invalid_estimated_minutes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ConfigError, "estimated_minutes must be numeric"):
                ScenarioConfig.from_mapping(
                    {
                        "strategy_file": str(Path(tmp) / "strategies" / "s" / "s.py"),
                        "strategy": "s",
                        "scenario_id": "s01",
                        "start_date": "2026-04-01",
                        "end_date": "2026-05-01",
                        "capital": 100000,
                        "estimated_minutes": "unknown",
                    }
                )

    def test_scenario_config_expands_grid_sweep(self) -> None:
        config = ScenarioConfig.from_mapping(
            {
                "strategy_file": "strategies/demo/demo.py",
                "strategy": "demo",
                "scenario_id": "s01",
                "start_date": "2026-04-01",
                "end_date": "2026-05-01",
                "capital": 100000,
                "sweep": {
                    "strategy": "grid",
                    "dimensions": {"TopK": [1, 2], "fq_mode": [None]},
                },
            }
        )

        runs = config.expand_runs()

        self.assertEqual([run.label for run in runs], ["TopK=1_fq_mode=None", "TopK=2_fq_mode=None"])
        self.assertEqual(runs[1].params_diff, {"TopK": 2, "fq_mode": None})

    def test_scenario_config_expands_list_sweep(self) -> None:
        config = ScenarioConfig.from_mapping(
            {
                "strategy_file": "strategies/demo/demo.py",
                "strategy": "demo",
                "scenario_id": "s01",
                "start_date": "2026-04-01",
                "end_date": "2026-05-01",
                "capital": 100000,
                "sweep": {
                    "strategy": "list",
                    "combinations": [
                        {"label": "conservative", "params": {"TopK": 1}},
                        {"label": "baseline", "params": {"TopK": 2}},
                    ],
                },
            }
        )

        runs = config.expand_runs()

        self.assertEqual([run.label for run in runs], ["conservative", "baseline"])
        self.assertEqual(runs[0].params_diff, {"TopK": 1})

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

    def test_list_pending_runs_filters_completed_and_failed_scenarios(self) -> None:
        manifest = {
            "scenarios": {
                "s01": {"status": "pending"},
                "s02": {
                    "runs": [
                        {"label": "done", "status": "completed"},
                        {"label": "retry", "status": "failed"},
                    ]
                },
                "s03": {"status": "failed"},
                "s04": {"runs": [{"label": "next", "status": "pending"}]},
            }
        }

        pending = list_pending_runs(manifest)

        self.assertEqual(
            [(sid, entry["label"] if entry else None) for sid, entry in pending],
            [("s01", None), ("s02", "retry"), ("s04", "next")],
        )
        self.assertEqual(list_pending_runs(manifest, {"s04"}), [("s04", {"label": "next", "status": "pending"})])

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

    def test_used_minutes_counts_cancelled_actual_minutes(self) -> None:
        ledger = {"budget_minutes": 60, "runs": []}
        append_quota_entry(ledger, scenario_id="s01", run_id="r1", estimated_minutes=30, status="cancelled")
        update_actual_minutes(ledger, "r1", 2.5)

        self.assertAlmostEqual(used_minutes(ledger), 2.5)

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

    def test_apply_params_overrides_only_updates_set_parameter_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            strategy_file = Path(tmp) / "demo.py"
            strategy_file.write_text(
                "\n".join(
                    [
                        "def set_parameter(context):",
                        "    g.TopK = 2",
                        "    g.names = ['old']",
                        "",
                        "def update_runtime_state():",
                        "    g.TopK = g.TopK + 1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            tmp_file = apply_params_overrides(strategy_file, {"TopK": 3, "names": ["new", 2]})

            rewritten = tmp_file.read_text(encoding="utf-8")
            self.assertIn("    g.TopK = 3\n", rewritten)
            self.assertIn("    g.names = ['new', 2]\n", rewritten)
            self.assertIn("    g.TopK = g.TopK + 1\n", rewritten)

    def test_apply_params_overrides_rejects_multiline_parameter_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            strategy_file = Path(tmp) / "demo.py"
            strategy_file.write_text(
                "\n".join(
                    [
                        "def set_parameter(context):",
                        "    g.TopK = (",
                        "        2",
                        "    )",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(LocalCheckError, "multi-line assignment"):
                apply_params_overrides(strategy_file, {"TopK": 3})

    def test_apply_params_overrides_refuses_non_parameter_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            strategy_file = Path(tmp) / "demo.py"
            strategy_file.write_text(
                "\n".join(
                    [
                        "def set_parameter(context):",
                        "    pass",
                        "",
                        "def update_runtime_state():",
                        "    g.TopK = g.TopK + 1",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(LocalCheckError, "outside set_parameter"):
                apply_params_overrides(strategy_file, {"TopK": 3})

    def test_save_api_bundle_uses_resolved_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            tabs_dir = run_dir / "tabs_raw"
            run_dir.mkdir()
            tabs_dir.mkdir()
            save_module = Mock()
            bundle = {"metadata": {"schema_version": 2}, "counts": {"result_rows": 1}}

            with (
                patch.object(artifacts, "resolve_run_dir", return_value=run_dir),
                patch.object(artifacts, "resolve_tabs_dir", return_value=tabs_dir),
                patch.object(artifacts, "_load_save_backtest_data", return_value=save_module),
            ):
                result = artifacts.save_api_bundle(bundle, strategy="demo", run_id="r1")

            self.assertEqual(result, run_dir)
            self.assertEqual(json.loads((run_dir / "api_export.json").read_text(encoding="utf-8")), bundle)
            save_module.save_api_data.assert_called_once_with(
                str(run_dir / "api_export.json"),
                str(run_dir),
                tabs_dir=str(tabs_dir),
            )


    def test_bundle_options_includes_frequency_and_py_version(self) -> None:
        config = ScenarioConfig.from_mapping(
            {
                "strategy_file": "strategies/demo/demo.py",
                "strategy": "demo",
                "scenario_id": "s01",
                "start_date": "2026-04-01",
                "end_date": "2026-05-01",
                "capital": 100000,
                "frequency": "1m",
                "py_version": "Python2",
            }
        )
        opts = _bundle_options(config)
        self.assertEqual(opts["frequency"], "1m")
        self.assertEqual(opts["pyVersion"], "Python2")
        self.assertEqual(opts["startDate"], "2026-04-01")
        self.assertEqual(opts["capital"], 100000)

    def test_metadata_from_api_bundle_preserves_internal_id_and_mismatch(self) -> None:
        save = _load_save_backtest_data()

        bundle = {
            "metadata": {
                "backtest_id": "detail-abc",
                "internal_backtest_id": "internal-xyz",
                "id_mismatch": True,
                "backtest_url": "https://example.com/?backtestId=detail-abc",
                "strategy_name": "test",
                "start_date_effective": "2026-01-01",
                "end_date_effective": "2026-01-31",
                "capital": 100000,
                "frequency": "1d",
                "py_version": "Python3",
            }
        }
        meta = save.metadata_from_api_bundle(bundle)
        self.assertEqual(meta["backtest_id"], "detail-abc")
        self.assertEqual(meta["internal_backtest_id"], "internal-xyz")
        self.assertTrue(meta.get("id_mismatch"))

        # 无 mismatch 时不应设置 id_mismatch
        bundle_no_mismatch = {
            "metadata": {
                "backtest_id": "same-id",
                "internal_backtest_id": "same-id",
                "backtest_url": "https://example.com/?backtestId=same-id",
            }
        }
        meta2 = save.metadata_from_api_bundle(bundle_no_mismatch)
        self.assertEqual(meta2["backtest_id"], "same-id")
        self.assertNotIn("id_mismatch", meta2)

    def test_build_api_bundle_index_respects_partial_results(self) -> None:
        save = _load_save_backtest_data()

        files_written = [
            ("daily_returns.md", 804),
            ("transactioninfo.md", 10),
            ("logs.md", 50),
        ]
        api_data = {
            "counts": {"result_rows": 804, "transactions": 10, "logs": 50},
            "partial": {"results": True, "logs": False},
        }

        index = save.build_api_bundle_index("fake.json", files_written, api_data)
        tabs = index["tabs"]

        self.assertTrue(tabs["daily_returns"]["partial"], "daily_returns should be partial when partial.results is True")
        self.assertFalse(tabs["logs"]["partial"])

        # 当 partial.results 为 False 时
        api_data2 = {
            "counts": {"result_rows": 804},
            "partial": {"results": False},
        }
        index2 = save.build_api_bundle_index("fake.json", files_written, api_data2)
        self.assertFalse(index2["tabs"]["daily_returns"]["partial"])

    def test_apply_backtest_params_snippet_payload_includes_frequency_py_version(self) -> None:
        """验证 browser.apply_backtest_params 构造的 payload 包含 frequency 和 py_version。"""
        from scripts.jq_automation.browser import JoinQuantBrowser

        # 通过检查 snippet payload 结构来验证合约
        captured_payload = {}

        class FakePage:
            async def evaluate(self, expression, arg):
                captured_payload.update(arg.get("payload", {}))
                return {"start_date": "2026-01-01", "end_date": "2026-01-31",
                        "capital": "100000", "frequency": "1d", "py_version": "Python3"}

        browser = JoinQuantBrowser.__new__(JoinQuantBrowser)
        browser._require_page = lambda: FakePage()
        browser.snippet_reader = lambda name: "function applyBacktestParams(){}"

        import asyncio
        asyncio.run(browser.apply_backtest_params(
            "2026-01-01", "2026-01-31", 100000,
            frequency="1d", py_version="Python3",
        ))

        self.assertEqual(captured_payload.get("frequency"), "1d")
        self.assertEqual(captured_payload.get("py_version"), "Python3")
        self.assertEqual(captured_payload.get("capital"), 100000)

    def test_expand_runs_preserves_non_sweep_params_diff(self) -> None:
        """非 sweep 场景的 params_diff 应被保留在 RunSpec 中。"""
        config = ScenarioConfig.from_mapping(
            {
                "strategy_file": "strategies/demo/demo.py",
                "strategy": "demo",
                "scenario_id": "s01",
                "start_date": "2026-04-01",
                "end_date": "2026-05-01",
                "capital": 100000,
                "params_diff": {"TopK": 3, "MaxWeight": 0.5},
            }
        )

        runs = config.expand_runs()
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].label, "default")
        self.assertEqual(runs[0].params_diff, {"TopK": 3, "MaxWeight": 0.5})

    def test_for_run_sets_run_params_diff_in_raw(self) -> None:
        """for_run() 应将 RunSpec.params_diff 写入派生 config 的 raw._run_params_diff。"""
        config = ScenarioConfig.from_mapping(
            {
                "strategy_file": "strategies/demo/demo.py",
                "strategy": "demo",
                "scenario_id": "s01",
                "start_date": "2026-04-01",
                "end_date": "2026-05-01",
                "capital": 100000,
                "params_diff": {"RSRS_M": 800, "CrowdWindow": 700},
            }
        )

        runs = config.expand_runs()
        derived = config.for_run(runs[0])
        self.assertEqual(derived.raw.get("_run_params_diff"), {"RSRS_M": 800, "CrowdWindow": 700})

    def test_compile_date_range_uses_last_30_days(self) -> None:
        """短周期编译参数应取最近 30 天，不超过给定的 end_date_cap。"""
        from scripts.jq_automation.cli import _compile_date_range

        # 无 cap：最近 30 天到今日
        start, end = _compile_date_range()
        today = datetime.now()
        self.assertEqual(end, today.strftime("%Y-%m-%d"))
        self.assertGreaterEqual(today - datetime.strptime(start, "%Y-%m-%d"), timedelta(days=29))

        # 有历史 cap：不应超过 cap 日期
        start_capped, end_capped = _compile_date_range(end_date_cap="2025-12-31")
        self.assertEqual(end_capped, "2025-12-31")
        self.assertEqual(start_capped, "2025-12-01")


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


def _load_save_backtest_data():
    """Load save_backtest_data.py via importlib for direct function testing."""
    root = Path(__file__).resolve().parents[3]
    candidate = root / "scripts" / "jq_automation" / "scripts" / "save_backtest_data.py"
    spec = importlib.util.spec_from_file_location("_test_save_backtest_data", candidate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
