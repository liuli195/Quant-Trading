from __future__ import annotations

import asyncio
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.tools.jq_automation import artifacts
from scripts.tools.jq_automation.browser import CompileFailed, wait_for_compile_completion
from scripts.tools.jq_automation.cli import _bundle_options
from scripts.tools.jq_automation.config import ConfigError, ScenarioConfig
from scripts.tools.jq_automation.dataset_registration import register_backtest_run_dataset
from scripts.tools.jq_automation.local import LocalCheckError, apply_params_overrides
from scripts.tools.jq_automation.manifest import list_pending_runs, update_manifest
from scripts.tools.jq_automation.paths import extract_backtest_id, make_run_id
from scripts.tools.jq_automation.quota import (
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
        from scripts.tools.jq_automation.config import _normalize_frequency

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
        from scripts.tools.jq_automation.config import _normalize_frequency

        self.assertEqual(_normalize_frequency("每天"), "1d")
        self.assertEqual(_normalize_frequency("每分钟"), "1m")

    def test_normalize_frequency_rejects_unknown_value(self) -> None:
        from scripts.tools.jq_automation.config import _normalize_frequency, ConfigError

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

    def test_scenario_config_parses_result_source(self) -> None:
        config = ScenarioConfig.from_mapping(
            {
                "strategy_file": "strategies/demo/demo.py",
                "strategy": "demo",
                "scenario_id": "s01",
                "start_date": "2026-04-01",
                "end_date": "2026-05-01",
                "capital": 100000,
                "result_source": "research",
            }
        )
        self.assertEqual(config.result_source, "research")
        self.assertEqual(config.for_run(config.expand_runs()[0]).result_source, "research")

        with self.assertRaisesRegex(ConfigError, "result_source"):
            ScenarioConfig.from_mapping(
                {
                    "strategy_file": "strategies/demo/demo.py",
                    "strategy": "demo",
                    "scenario_id": "s01",
                    "start_date": "2026-04-01",
                    "end_date": "2026-05-01",
                    "capital": 100000,
                    "result_source": "unknown",
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
                detail_api_json_path=None,
                allow_partial=False,
            )

    def test_register_backtest_run_dataset_imports_saved_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "backtest_runs" / "demo" / "r1"
            tabs = run_dir / "tabs_raw"
            tabs.mkdir(parents=True)
            (run_dir / "summary_metrics.json").write_text(json.dumps({"sharpe": 1.0}), encoding="utf-8")
            (run_dir / "metadata.json").write_text(json.dumps({"backtest_id": "bt1"}), encoding="utf-8")
            (run_dir / "api_export.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")
            (tabs / "daily_returns.md").write_text(
                "| date | cumulative_return |\n| --- | ---: |\n| 2026-01-01 | 0.010000 |\n",
                encoding="utf-8",
            )
            (tabs / "audit_log.jsonl").write_text(
                '{"seq": 1, "event": "run_start", "current_dt": "2026-01-01 09:30:00"}\n',
                encoding="utf-8",
            )

            snapshot = register_backtest_run_dataset(
                run_dir,
                strategy="demo",
                run_id="r1",
                datasets_root=root / "research_datasets",
            )
            duplicate = register_backtest_run_dataset(
                run_dir,
                strategy="demo",
                run_id="r1",
                datasets_root=root / "research_datasets",
            )

            self.assertIsNotNone(snapshot)
            self.assertIsNone(duplicate)
            self.assertTrue((root / "research_datasets" / "demo_backtest_runs" / "r1" / "dataset.json").is_file())


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
        self.assertEqual(opts["resultSource"], "auto")
        self.assertFalse(opts["allowPartial"])

    def test_generate_upload_file_injects_audit_token(self) -> None:
        from scripts.tools.jq_automation.local import generate_upload_file

        with tempfile.TemporaryDirectory() as tmp:
            strategy_file = Path(tmp) / "strategy.py"
            strategy_file.write_text(
                'JQ_AUTO_AUDIT_TOKEN = "manual"\n'
                "def initialize(context):\n"
                "    pass\n",
                encoding="utf-8",
            )

            upload_path = generate_upload_file(strategy_file, audit_token="audit-123")
            rewritten = upload_path.read_text(encoding="utf-8")

        self.assertIn("JQ_AUTO_AUDIT_TOKEN = 'audit-123'", rewritten)
        self.assertNotIn('"manual"', rewritten)

    def test_research_script_contains_all_get_backtest_methods(self) -> None:
        from scripts.tools.jq_automation.research import ResearchFetchOptions, build_research_export_script

        script = build_research_export_script(
            ResearchFetchOptions(backtest_id="bt123", strategy="demo", export_path="jq_auto_exports/bt123.json")
        )

        self.assertIn("get_backtest", script)
        for method in [
            "get_results",
            "get_positions",
            "get_orders",
            "get_records",
            "get_risk",
            "get_period_risks",
            "get_balances",
        ]:
            self.assertIn(method, script)
        self.assertIn("write_file", script)

    def test_research_script_handles_joinquant_cloud_runtime_quirks(self) -> None:
        from scripts.tools.jq_automation.research import (
            ResearchFetchOptions,
            _EXECUTE_RESEARCH_SCRIPT_JS,
            _READ_RESEARCH_FILE_JS,
            build_research_export_script,
        )

        script = build_research_export_script(
            ResearchFetchOptions(backtest_id="bt123", strategy="demo", export_path="jq_auto_exports/bt123.json")
        )

        self.assertIn("_metadata = json.loads(", script)
        self.assertNotIn("_metadata = {", script)
        self.assertIn('os.path.expanduser("~")', script)
        self.assertIn("os.makedirs", script)
        self.assertIn("specs && specs.kernelspecs", _EXECUTE_RESEARCH_SCRIPT_JS)
        self.assertIn('ctype.includes("text/html")', _READ_RESEARCH_FILE_JS)
        self.assertIn("continue;", _READ_RESEARCH_FILE_JS)
        self.assertIn('path.match(/^\\/hub\\/user\\/([^\\/?#]+)/)', _EXECUTE_RESEARCH_SCRIPT_JS)
        self.assertIn('path.replace(/^\\/hub\\/user\\//, "/user/")', _EXECUTE_RESEARCH_SCRIPT_JS)
        self.assertIn('path.replace(/^\\/hub\\/user\\//, "/user/")', _READ_RESEARCH_FILE_JS)
        self.assertIn('window.PageConfig.getOption("baseUrl")', _EXECUTE_RESEARCH_SCRIPT_JS)
        self.assertIn("locationHref=", _EXECUTE_RESEARCH_SCRIPT_JS)
        self.assertIn("discoveredBases=", _EXECUTE_RESEARCH_SCRIPT_JS)
        self.assertIn("apiBases=", _EXECUTE_RESEARCH_SCRIPT_JS)

    def test_research_context_url_guard_rejects_hub_bridge(self) -> None:
        from scripts.tools.jq_automation.research import _is_direct_user_workspace_url

        self.assertTrue(_is_direct_user_workspace_url("https://www.joinquant.com/user/123/tree?"))
        self.assertFalse(_is_direct_user_workspace_url("https://www.joinquant.com/hub/user/123/tree?"))
        self.assertFalse(_is_direct_user_workspace_url("https://www.joinquant.com/research"))

    def test_research_context_selects_joinquant_research_iframe(self) -> None:
        from scripts.tools.jq_automation.research import _research_context

        class FakeFrame:
            url = "https://www.joinquant.com/user/123/tree?"

            async def evaluate(self, _script: str) -> str:
                return "complete"

        class FakePage:
            url = "https://www.joinquant.com/research"

            def __init__(self) -> None:
                self.frame_obj = FakeFrame()
                self.selector_waited = False

            async def wait_for_selector(self, _selector: str, timeout: int) -> None:
                self.selector_waited = timeout == 30000

            def frame(self, name: str):
                return self.frame_obj if name == "research" else None

            async def wait_for_timeout(self, _timeout: int) -> None:
                return None

        page = FakePage()
        result = asyncio.run(_research_context(page))
        self.assertIs(result, page.frame_obj)
        self.assertTrue(page.selector_waited)

    def test_research_context_waits_past_hub_bridge_frame(self) -> None:
        from scripts.tools.jq_automation.research import _research_context

        class FakeFrame:
            def __init__(self) -> None:
                self.urls = [
                    "https://www.joinquant.com/hub/user/123/tree?",
                    "https://www.joinquant.com/user/123/tree?",
                ]
                self.index = 0

            @property
            def url(self) -> str:
                return self.urls[min(self.index, len(self.urls) - 1)]

            async def evaluate(self, _script: str) -> str:
                return "complete"

        class FakePage:
            url = "https://www.joinquant.com/research"

            def __init__(self) -> None:
                self.frame_obj = FakeFrame()
                self.wait_count = 0

            async def wait_for_selector(self, _selector: str, timeout: int) -> None:
                return None

            def frame(self, name: str):
                return self.frame_obj if name == "research" else None

            async def wait_for_timeout(self, _timeout: int) -> None:
                self.wait_count += 1
                self.frame_obj.index += 1

        page = FakePage()
        result = asyncio.run(_research_context(page))

        self.assertIs(result, page.frame_obj)
        self.assertEqual(page.wait_count, 1)

    def test_normalize_research_bundle_schema_v3(self) -> None:
        from scripts.tools.jq_automation.research import ResearchFetchOptions, normalize_research_bundle

        bundle = normalize_research_bundle(
            {
                "results": [{"time": "2026-01-01", "returns": 0.1, "benchmark_returns": 0.05}],
                "positions": [{"time": "2026-01-01", "security": "510300.XSHG", "amount": 100}],
                "orders": [{"time": "2026-01-01", "security": "510300.XSHG", "amount": 100}],
                "records": [{"time": "2026-01-01", "score": 1}],
                "risk": {"algorithm_return": 0.1},
                "period_risks": {"alpha": [{"date": "2026-01", "1month": 0.1}]},
                "balances": [{"time": "2026-01-01", "total_value": 100000}],
            },
            fetch_options=ResearchFetchOptions(
                backtest_id="bt123",
                strategy="demo",
                strategy_name="demo",
                export_path="jq_auto_exports/bt123.json",
            ),
            supplemental_detail={"runtime": {"data": {"needSeconds": 60}}, "logs_partial": True},
        )

        self.assertEqual(bundle["metadata"]["schema_version"], 3)
        self.assertEqual(bundle["metadata"]["extraction_method"], "joinquant_research_get_backtest")
        self.assertTrue(bundle["metadata"]["research_downloaded"])
        self.assertEqual(bundle["counts"]["results"], 1)
        self.assertTrue(bundle["partial"]["logs"])
        self.assertEqual(bundle["supplemental_detail"]["runtime"]["data"]["needSeconds"], 60)

    def test_save_research_bundle_data_outputs_existing_contract(self) -> None:
        save = _load_save_backtest_data()

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            tabs_dir = run_dir / "tabs_raw"
            run_dir.mkdir()
            tabs_dir.mkdir()
            api_path = run_dir / "api_export.json"
            api_data = {
                "metadata": {
                    "schema_version": 3,
                    "strategy_name": "demo",
                    "backtest_id": "bt123",
                    "extraction_method": "joinquant_research_get_backtest",
                    "primary_extraction_method": "joinquant_research_get_backtest",
                    "research_export_path": "jq_auto_exports/bt123.json",
                    "research_downloaded": True,
                    "detail_api_used": True,
                },
                "results": [{"time": "2026-01-01", "returns": 0.1, "benchmark_returns": 0.05}],
                "positions": [{"time": "2026-01-01", "security": "510300.XSHG", "amount": 100, "price": 4.0}],
                "orders": [{"time": "2026-01-01", "security": "510300.XSHG", "amount": 100, "price": 4.0}],
                "records": [{"time": "2026-01-01", "score": 1}],
                "risk": {"algorithm_return": 0.1, "annual_algo_return": 0.2, "max_drawdown": 0.03},
                "period_risks": {"alpha": [{"date": "2026-01", "1month": 0.1}]},
                "balances": [{"time": "2026-01-01", "total_value": 100000}],
                "supplemental_detail": {"logs_partial": True, "logs_count": 1000, "profile_text": ""},
                "counts": {"results": 1, "positions": 1, "orders": 1, "records": 1, "balances": 1, "period_risk_tabs": 1, "audit_log_lines": 2},
                "partial": {"logs": True, "audit_log": False},
                "audit_log_text": (
                    '{"seq": 1, "event": "run_start"}\n'
                    '{"seq": 2, "event": "run_end"}\n'
                ),
            }
            api_path.write_text(json.dumps(api_data, ensure_ascii=False), encoding="utf-8")
            detail_path = run_dir / "detail_api_export.json"
            detail_data = {
                "metadata": {"schema_version": 2, "extraction_method": "joinquant_detail_readonly_api"},
                "counts": {"result_rows": 1, "transactions": 1, "positions": 1, "risk_rows": 1, "logs": 1000},
                "partial": {"results": False, "transactions": False, "positions": False, "logs": True},
                "transactions": {"rows": [{"date": "2026-01-01"}]},
                "positions": {"rows": [{"date": "2026-01-01"}]},
                "result_rows": [{"date": "2026-01-01"}],
                "risk_tabs": {"alpha": {"rows": [{"date": "2026-01"}]}},
            }
            detail_path.write_text(json.dumps(detail_data, ensure_ascii=False), encoding="utf-8")

            save.save_api_data(
                str(api_path),
                str(run_dir),
                tabs_dir=str(tabs_dir),
                detail_api_json_path=str(detail_path),
            )

            self.assertTrue((tabs_dir / "daily_returns.md").is_file())
            self.assertTrue((tabs_dir / "transactioninfo.md").is_file())
            self.assertTrue((tabs_dir / "records.md").is_file())
            self.assertTrue((tabs_dir / "audit_log.jsonl").is_file())
            self.assertTrue((run_dir / "integrity.json").is_file())
            self.assertTrue((run_dir / "report" / "data-integrity.md").is_file())
            meta = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["primary_extraction_method"], "joinquant_research_get_backtest")
            summary = json.loads((run_dir / "summary_metrics.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["策略收益"], "10.00%")
            index = json.loads((run_dir / "all_data.json").read_text(encoding="utf-8"))
            self.assertEqual(index["extraction_method"], "research_bundle")
            self.assertTrue(index["tabs"]["logs"]["partial"])
            self.assertEqual(index["integrity_status"], "complete")

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
                "attempted_primary_extraction_method": "joinquant_research_get_backtest",
                "primary_extraction_method": "joinquant_detail_readonly_api",
                "fallback_extraction_method": "joinquant_detail_readonly_api",
                "research_downloaded": False,
                "research_fetch_failed": True,
                "research_fetch_error": "forced research failure",
                "detail_api_used": True,
            }
        }
        meta = save.metadata_from_api_bundle(bundle)
        self.assertEqual(meta["backtest_id"], "detail-abc")
        self.assertEqual(meta["internal_backtest_id"], "internal-xyz")
        self.assertTrue(meta.get("id_mismatch"))
        self.assertEqual(meta["attempted_primary_extraction_method"], "joinquant_research_get_backtest")
        self.assertEqual(meta["fallback_extraction_method"], "joinquant_detail_readonly_api")
        self.assertTrue(meta["research_fetch_failed"])
        self.assertEqual(meta["research_fetch_error"], "forced research failure")

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

    def test_integrity_gate_fails_without_audit_log(self) -> None:
        save = _load_save_backtest_data()

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            tabs_dir = run_dir / "tabs_raw"
            run_dir.mkdir()
            tabs_dir.mkdir()
            api_path = run_dir / "api_export.json"
            detail_path = run_dir / "detail_api_export.json"
            api_data = {
                "metadata": {
                    "schema_version": 3,
                    "extraction_method": "joinquant_research_get_backtest",
                    "primary_extraction_method": "joinquant_research_get_backtest",
                    "research_downloaded": True,
                },
                "results": [{"time": "2026-01-01"}],
                "positions": [],
                "orders": [],
                "risk": {"algorithm_return": 0.1},
                "period_risks": {},
                "balances": [],
                "counts": {"results": 1, "positions": 0, "orders": 0, "period_risk_tabs": 0},
                "partial": {},
                "audit_log_text": "",
            }
            detail_data = {
                "metadata": {"schema_version": 2},
                "counts": {"result_rows": 1, "transactions": 0, "positions": 1, "risk_rows": 1},
                "partial": {"results": False, "transactions": False, "positions": False, "logs": True},
                "risk_tabs": {"alpha": {"rows": [{"date": "2026-01"}]}},
            }
            api_path.write_text(json.dumps(api_data), encoding="utf-8")
            detail_path.write_text(json.dumps(detail_data), encoding="utf-8")

            with self.assertRaisesRegex(save.IntegrityError, "audit_log"):
                save.save_api_data(
                    str(api_path),
                    str(run_dir),
                    tabs_dir=str(tabs_dir),
                    detail_api_json_path=str(detail_path),
                )

            integrity = json.loads((run_dir / "integrity.json").read_text(encoding="utf-8"))
            self.assertEqual(integrity["status"], "incomplete")

    def test_allow_partial_writes_incomplete_artifacts_without_raising(self) -> None:
        save = _load_save_backtest_data()

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            tabs_dir = run_dir / "tabs_raw"
            run_dir.mkdir()
            tabs_dir.mkdir()
            api_path = run_dir / "api_export.json"
            api_data = {
                "metadata": {"schema_version": 2, "extraction_method": "joinquant_detail_readonly_api"},
                "counts": {"result_rows": 1, "transactions": 0, "positions": 1, "risk_rows": 1, "logs": 1000},
                "partial": {"results": False, "transactions": False, "positions": False, "logs": True},
                "transactions": {"rows": []},
                "positions": {"rows": [{"date": "2026-01-01"}]},
                "result_rows": [{"date": "2026-01-01"}],
                "risk_tabs": {"alpha": {"rows": [{"date": "2026-01"}]}},
                "logs": {"rows": []},
                "error_logs": {"rows": []},
            }
            api_path.write_text(json.dumps(api_data), encoding="utf-8")

            save.save_api_data(str(api_path), str(run_dir), tabs_dir=str(tabs_dir), allow_partial=True)

            index = json.loads((run_dir / "all_data.json").read_text(encoding="utf-8"))
            self.assertEqual(index["integrity_status"], "incomplete")

    def test_validate_audit_log_rejects_bad_json_and_seq_gap(self) -> None:
        save = _load_save_backtest_data()

        result = save.validate_audit_log(
            '{"seq": 1, "event": "run_start"}\n'
            '{"seq": 3, "event": "run_end"}\n'
            'not-json\n'
        )

        self.assertFalse(result["valid"])
        self.assertTrue(any("seq" in issue for issue in result["issues"]))
        self.assertTrue(any("JSON" in issue for issue in result["issues"]))

    def test_build_api_bundle_index_respects_partial_results(self) -> None:
        save = _load_save_backtest_data()

        files_written = [
            ("daily_returns.md", 804),
            ("transactioninfo.md", 10),
            ("logs.md", 50),
        ]
        api_data = {
            "metadata": {
                "attempted_primary_extraction_method": "joinquant_research_get_backtest",
                "primary_extraction_method": "joinquant_detail_readonly_api",
                "fallback_extraction_method": "joinquant_detail_readonly_api",
                "research_downloaded": False,
                "research_fetch_failed": True,
                "research_fetch_error": "forced research failure",
                "detail_api_used": True,
            },
            "counts": {"result_rows": 804, "transactions": 10, "logs": 50},
            "partial": {"results": True, "logs": False},
        }

        index = save.build_api_bundle_index("fake.json", files_written, api_data)
        tabs = index["tabs"]

        self.assertTrue(tabs["daily_returns"]["partial"], "daily_returns should be partial when partial.results is True")
        self.assertFalse(tabs["logs"]["partial"])
        self.assertEqual(index["attempted_primary_extraction_method"], "joinquant_research_get_backtest")
        self.assertEqual(index["fallback_extraction_method"], "joinquant_detail_readonly_api")
        self.assertTrue(index["research_fetch_failed"])

        # 当 partial.results 为 False 时
        api_data2 = {
            "counts": {"result_rows": 804},
            "partial": {"results": False},
        }
        index2 = save.build_api_bundle_index("fake.json", files_written, api_data2)
        self.assertFalse(index2["tabs"]["daily_returns"]["partial"])

    def test_annotate_research_fallback_marks_detail_payload(self) -> None:
        from scripts.tools.jq_automation.cli import _annotate_research_fallback

        payload = {"metadata": {"extraction_method": "joinquant_detail_readonly_api"}}
        _annotate_research_fallback(payload, "api", RuntimeError("research unavailable"))

        meta = payload["metadata"]
        self.assertEqual(meta["attempted_primary_extraction_method"], "joinquant_research_get_backtest")
        self.assertEqual(meta["primary_extraction_method"], "joinquant_detail_readonly_api")
        self.assertEqual(meta["fallback_extraction_method"], "joinquant_detail_readonly_api")
        self.assertFalse(meta["research_downloaded"])
        self.assertTrue(meta["research_fetch_failed"])
        self.assertEqual(meta["research_fetch_error"], "research unavailable")
        self.assertTrue(meta["detail_api_used"])

    def test_short_symbol_keeps_standard_joinquant_code_format(self) -> None:
        save = _load_save_backtest_data()

        self.assertEqual(
            save._short_symbol("人工智能ETF易方达(159819.XSHE)"),
            "人工智能ETF易方达(159819.XSHE)",
        )
        self.assertEqual(
            save._short_symbol("50ETF(510050.XSHG)"),
            "上证50ETF(510050.XSHG)",
        )
        self.assertEqual(
            save._short_symbol("黄金ETF(518880)"),
            "黄金ETF(518880.XSHG)",
        )

    def test_api_position_report_keeps_full_security_code(self) -> None:
        save = _load_save_backtest_data()

        md = save.api_position_to_md([
            {
                "security": "基金",
                "date": "2026-05-01",
                "stock": "人工智能ETF易方达(159819.XSHE)",
                "amount": "100",
                "price": "1.000",
                "value": "100",
                "dailyGains": "0",
                "gain": "0",
                "avgCost": "1.000",
                "positionPersent": "10%",
            }
        ])

        self.assertIn("人工智能ETF易方达(159819.XSHE)", md)

    def test_apply_backtest_params_snippet_payload_includes_frequency_py_version(self) -> None:
        """验证 browser.apply_backtest_params 构造的 payload 包含 frequency 和 py_version。"""
        from scripts.tools.jq_automation.browser import JoinQuantBrowser

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

    def test_browser_exit_skips_storage_state_on_login_page(self) -> None:
        from scripts.tools.jq_automation.browser import JoinQuantBrowser

        class FakeContext:
            async def cookies(self):
                return [{"name": "token", "value": "new"}]

            async def close(self):
                return None

        class FakePage:
            url = "https://www.joinquant.com/user/login/index"

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "storage_state.json"
            path.write_text(json.dumps({"cookies": [{"name": "token", "value": "old"}]}), encoding="utf-8")
            browser = JoinQuantBrowser.__new__(JoinQuantBrowser)
            browser.user_data_dir = Path(tmp)
            browser.context = FakeContext()
            browser.page = FakePage()
            browser._playwright = None

            asyncio.run(browser.__aexit__())

            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"cookies": [{"name": "token", "value": "old"}]},
            )

    def test_browser_exit_persists_storage_state_off_login_page(self) -> None:
        from scripts.tools.jq_automation.browser import JoinQuantBrowser

        class FakeContext:
            async def cookies(self):
                return [{"name": "token", "value": "new"}]

            async def close(self):
                return None

        class FakePage:
            url = "https://www.joinquant.com/algorithm/index/list"

        with tempfile.TemporaryDirectory() as tmp:
            browser = JoinQuantBrowser.__new__(JoinQuantBrowser)
            browser.user_data_dir = Path(tmp)
            browser.context = FakeContext()
            browser.page = FakePage()
            browser._playwright = None

            asyncio.run(browser.__aexit__())

            self.assertEqual(
                json.loads((Path(tmp) / "storage_state.json").read_text(encoding="utf-8")),
                {"cookies": [{"name": "token", "value": "new"}]},
            )

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
        from scripts.tools.jq_automation.cli import _compile_date_range

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
    root = Path(__file__).resolve().parents[4]
    candidate = root / "scripts" / "tools" / "jq_automation" / "utils" / "save_backtest_data.py"
    spec = importlib.util.spec_from_file_location("_test_save_backtest_data", candidate)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
