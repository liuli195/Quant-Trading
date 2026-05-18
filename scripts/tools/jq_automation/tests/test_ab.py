from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.tools.jq_automation.abtest import (
    ABConfigError,
    ABExpandError,
    ABReportError,
    ABExperimentConfig,
    ABVariantSpec,
    ABCodeSource,
    compute_config_hash,
    expand_ab_experiment,
    load_ab_config,
    resolve_ab_code_sources,
    write_ab_report,
)
from scripts.tools.jq_automation.git_versioning import (
    GitVersionError,
    assert_file_at_commit,
    resolve_git_ref,
    read_file_at_commit,
)
from scripts.tools.jq_automation.manifest import (
    get_ab_experiment,
    list_pending_runs,
    load_manifest,
    update_ab_experiment,
    update_manifest,
    sync_ab_experiment_status,
)
from scripts.tools.jq_automation.metrics import (
    DEFAULT_METRICS,
    METRIC_KEY_MAP,
    collect_all_metrics,
    extract_from_summary_metrics,
    extract_from_api_stats,
    parse_metric_value,
)
from scripts.research.platform.strategy_variants import StrategyManifestReader, VariantRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ab_config_dict(**overrides: object) -> dict:
    """Build a minimal valid AB config dict, with optional overrides."""
    cfg = {
        "experiment_id": "test-ab",
        "strategy": "demo_strategy",
        "batch_id": "test-batch",
        "baseline": "main_best",
        "controls": ["main_best"],
        "base": {
            "code_source": {
                "type": "git",
                "ref": "main",
                "path": "strategies/demo_strategy/demo_strategy.py",
            },
            "start_date": "2025-05-01",
            "end_date": "2026-04-30",
            "capital": 100000,
            "estimated_minutes": 20,
            "frequency": "1d",
            "py_version": "Python3",
        },
        "variants": [
            {
                "label": "main_best",
                "role": "control",
                "params_mode": "params_diff",
                "params_diff": {"TopK": 2, "TargetVol": 0.12},
                "scan_source": {"batch_id": "test-sweep", "run_label": "best"},
                "note": "Best params from sweep.",
            },
            {
                "label": "branch_best",
                "role": "variant",
                "params_mode": "baked_in_git",
                "note": "Branch best.",
            },
        ],
    }
    cfg.update(overrides)  # type: ignore[arg-type]
    return cfg  # type: ignore[return-value]


def _make_temp_git_repo() -> Path:
    """Create a temporary git repo with one committed file. Returns repo root."""
    tmp = Path(tempfile.mkdtemp())
    subprocess.run(["git", "init"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"],
                   cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(tmp), capture_output=True)
    (tmp / "strategy.py").write_text("def initialize(context):\n    pass\n")
    subprocess.run(["git", "add", "strategy.py"], cwd=str(tmp), capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(tmp), capture_output=True)
    return tmp


# ---------------------------------------------------------------------------
# ABConfigTests
# ---------------------------------------------------------------------------


class ABConfigTests(unittest.TestCase):
    def test_load_minimal_config(self) -> None:
        cfg = load_ab_config(_ab_config_dict())
        self.assertEqual(cfg.experiment_id, "test-ab")
        self.assertEqual(cfg.baseline, "main_best")
        self.assertEqual(len(cfg.variants), 2)
        self.assertEqual(cfg.metrics, DEFAULT_METRICS)

    def test_variant_id_loads_params_from_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            strategy_root = root / "strategies" / "demo_strategy"
            strategy_root.mkdir(parents=True)
            (strategy_root / "demo_strategy.py").write_text(
                "def set_parameter(context):\n    g.TopK = 1\n",
                encoding="utf-8",
            )
            StrategyManifestReader(root / "strategies").ensure(strategy_root)
            VariantRegistry(strategy_root).register(
                variant_id="topk-3",
                variant_type="parameter",
                payload={"param_overrides": {"TopK": 3}},
                description="registered parameter variant",
            )
            raw = _ab_config_dict()
            raw["base"]["code_source"]["path"] = "strategies/demo_strategy/demo_strategy.py"
            raw["variants"][1] = {
                "label": "registered_topk",
                "role": "variant",
                "variant_id": "topk-3",
            }
            raw["baseline"] = "main_best"

            with patch("scripts.tools.jq_automation.abtest.repo_root", return_value=root):
                cfg = load_ab_config(raw)

            self.assertEqual(cfg.variants[1].variant_id, "topk-3")
            self.assertEqual(cfg.variants[1].params_diff, {"TopK": 3})
            self.assertEqual(cfg.variants[1].scan_source, {"variant_id": "topk-3"})
            self.assertEqual(cfg.variants[1].note, "registered parameter variant")

    def test_baseline_must_match_variant(self) -> None:
        with self.assertRaises(ABConfigError):
            load_ab_config(_ab_config_dict(baseline="nonexistent"))

    def test_controls_must_match_variants(self) -> None:
        with self.assertRaises(ABConfigError):
            load_ab_config(_ab_config_dict(controls=["nonexistent"]))

    def test_duplicate_labels_rejected(self) -> None:
        raw = _ab_config_dict()
        raw["variants"][1]["label"] = "main_best"
        with self.assertRaises(ABConfigError):
            load_ab_config(raw)

    def test_note_in_params_diff_rejected(self) -> None:
        raw = _ab_config_dict()
        raw["variants"][0]["params_diff"]["note"] = "should not be here"
        with self.assertRaises(ABConfigError):
            load_ab_config(raw)

    def test_invalid_params_mode_rejected(self) -> None:
        raw = _ab_config_dict()
        raw["variants"][0]["params_mode"] = "invalid"
        with self.assertRaises(ABConfigError):
            load_ab_config(raw)

    def test_default_role_is_variant(self) -> None:
        raw = _ab_config_dict()
        raw["variants"][1].pop("role", None)
        cfg = load_ab_config(raw)
        self.assertEqual(cfg.variants[1].role, "variant")

    def test_default_params_mode_is_params_diff(self) -> None:
        raw = _ab_config_dict()
        raw["variants"][1].pop("params_mode", None)
        cfg = load_ab_config(raw)
        self.assertEqual(cfg.variants[1].params_mode, "params_diff")

    def test_variant_code_source_overrides_base(self) -> None:
        raw = _ab_config_dict()
        raw["variants"][1]["code_source"] = {
            "type": "git",
            "ref": "feature/x",
            "path": "strategies/demo/demo.py",
        }
        cfg = load_ab_config(raw)
        self.assertEqual(cfg.variants[1].code_source.ref, "feature/x")
        self.assertEqual(cfg.variants[1].code_source.path, "strategies/demo/demo.py")

    def test_missing_experiment_id_rejected(self) -> None:
        with self.assertRaises(ABConfigError):
            load_ab_config(_ab_config_dict(experiment_id=""))

    def test_missing_strategy_rejected(self) -> None:
        with self.assertRaises(ABConfigError):
            load_ab_config(_ab_config_dict(strategy=""))

    def test_compute_config_hash_is_stable(self) -> None:
        cfg1 = _ab_config_dict()
        cfg2 = _ab_config_dict()
        self.assertEqual(compute_config_hash(cfg1), compute_config_hash(cfg2))

    def test_compute_config_hash_changes(self) -> None:
        h1 = compute_config_hash(_ab_config_dict())
        h2 = compute_config_hash(_ab_config_dict(experiment_id="different"))
        self.assertNotEqual(h1, h2)


# ---------------------------------------------------------------------------
# GitVersioningTests
# ---------------------------------------------------------------------------


class GitVersioningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = _make_temp_git_repo()

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(str(self.repo), ignore_errors=True)

    def test_resolve_branch_ref(self) -> None:
        sha = resolve_git_ref("HEAD", root=self.repo)
        self.assertEqual(len(sha), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))

    def test_resolve_commit_sha(self) -> None:
        sha = resolve_git_ref("HEAD", root=self.repo)
        # Resolve again by full SHA
        sha2 = resolve_git_ref(sha, root=self.repo)
        self.assertEqual(sha, sha2)

    def test_nonexistent_ref_raises(self) -> None:
        with self.assertRaises(GitVersionError):
            resolve_git_ref("nonexistent-branch", root=self.repo)

    def test_file_not_in_commit_raises(self) -> None:
        with self.assertRaises(GitVersionError):
            assert_file_at_commit("HEAD", "nonexistent.py", root=self.repo)

    def test_read_file_at_commit(self) -> None:
        content = read_file_at_commit("HEAD", "strategy.py", root=self.repo)
        self.assertIn("def initialize", content)

    def test_assert_file_returns_canonical_sha(self) -> None:
        committed = assert_file_at_commit("HEAD", "strategy.py", root=self.repo)
        self.assertEqual(len(committed), 40)

    def test_read_does_not_change_worktree(self) -> None:
        original = (self.repo / "strategy.py").read_text()
        read_file_at_commit("HEAD", "strategy.py", root=self.repo)
        after = (self.repo / "strategy.py").read_text()
        self.assertEqual(original, after)


# ---------------------------------------------------------------------------
# MetricsTests
# ---------------------------------------------------------------------------


class MetricsTests(unittest.TestCase):
    def test_parse_percentage(self) -> None:
        self.assertAlmostEqual(parse_metric_value("18.06%"), 0.1806)

    def test_parse_negative_float(self) -> None:
        self.assertAlmostEqual(parse_metric_value("-1.841"), -1.841)

    def test_parse_int(self) -> None:
        self.assertEqual(parse_metric_value(0), 0.0)

    def test_parse_empty_string(self) -> None:
        self.assertIsNone(parse_metric_value(""))

    def test_parse_none(self) -> None:
        self.assertIsNone(parse_metric_value(None))

    def test_parse_whitespace(self) -> None:
        self.assertIsNone(parse_metric_value("   "))

    def test_extract_from_summary_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            summary = {
                "策略收益": "15.30%",
                "策略年化收益": "12.50%",
                "最大回撤": "-8.20%",
                "夏普比率": "1.350",
                "胜率": "0.550",
                "盈利次数": 42,
            }
            (run_dir / "summary_metrics.json").write_text(
                json.dumps(summary, ensure_ascii=False), encoding="utf-8"
            )
            result = extract_from_summary_metrics(run_dir)
            self.assertAlmostEqual(result["total_return"], 0.153)
            self.assertAlmostEqual(result["annual_return"], 0.125)
            self.assertAlmostEqual(result["max_drawdown"], -0.082)
            self.assertAlmostEqual(result["sharpe"], 1.35)
            self.assertAlmostEqual(result["win_ratio"], 0.55)
            self.assertEqual(result["win_count"], 42.0)

    def test_extract_from_summary_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = extract_from_summary_metrics(Path(tmp))
            self.assertEqual(result, {})

    def test_extract_from_api_stats(self) -> None:
        bundle = {
            "stats": {
                "data": {
                    "annual_algo_return": 0.125,
                    "sharpe": 1.35,
                    "max_drawdown": -0.082,
                    "algorithm_volatility": 0.22,
                    "win_ratio": 0.55,
                }
            }
        }
        result = extract_from_api_stats(bundle)
        self.assertAlmostEqual(result["annual_return"], 0.125)
        self.assertAlmostEqual(result["sharpe"], 1.35)
        self.assertAlmostEqual(result["volatility"], 0.22)

    def test_chinese_key_mapping_completeness(self) -> None:
        # All keys in METRIC_KEY_MAP should have a corresponding METRIC_LABEL_CN
        from scripts.tools.jq_automation.metrics import METRIC_LABEL_CN
        for eng_key in METRIC_KEY_MAP.values():
            self.assertIn(eng_key, METRIC_LABEL_CN)

    def test_default_metrics_structure(self) -> None:
        for m in DEFAULT_METRICS:
            self.assertIn("key", m)
            self.assertIn("direction", m)
            self.assertIn(m["direction"], ("maximize", "minimize"))


# ---------------------------------------------------------------------------
# Manifest AB tests
# ---------------------------------------------------------------------------


class ManifestABTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.manifest_path = Path(self.tmp.name) / "manifest.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _empty_manifest(self) -> dict:
        return {
            "batch_id": "test-batch",
            "strategy": "demo",
            "scenarios": {},
        }

    def test_get_ab_experiment_returns_none_for_missing(self) -> None:
        manifest = self._empty_manifest()
        self.assertIsNone(get_ab_experiment(manifest, "nonexistent"))

    def test_update_ab_experiment_creates_entry(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self._empty_manifest()), encoding="utf-8"
        )
        exp = update_ab_experiment(
            self.manifest_path, "test-ab", "main_best",
            status="in_progress",
        )
        self.assertIn("variants", exp)
        variant = next(v for v in exp["variants"] if v["label"] == "main_best")
        self.assertEqual(variant["status"], "in_progress")

    def test_update_ab_experiment_updates_existing(self) -> None:
        self.manifest_path.write_text(
            json.dumps(self._empty_manifest()), encoding="utf-8"
        )
        update_ab_experiment(self.manifest_path, "test-ab", "main_best", status="in_progress")
        update_ab_experiment(self.manifest_path, "test-ab", "main_best",
                            run_id="run-1", status="completed")
        manifest = load_manifest(self.manifest_path)
        exp = get_ab_experiment(manifest, "test-ab")
        variant = next(v for v in exp["variants"] if v["label"] == "main_best")
        self.assertEqual(variant["run_id"], "run-1")
        self.assertEqual(variant["status"], "completed")

    def test_sync_experiment_status_all_completed(self) -> None:
        manifest = self._empty_manifest()
        manifest["ab_experiments"] = {
            "test-ab": {
                "variants": [
                    {"label": "a", "status": "completed"},
                    {"label": "b", "status": "completed"},
                ]
            }
        }
        sync_ab_experiment_status(manifest, "test-ab")
        self.assertEqual(manifest["ab_experiments"]["test-ab"]["status"], "completed")

    def test_sync_experiment_status_one_failed(self) -> None:
        manifest = self._empty_manifest()
        manifest["ab_experiments"] = {
            "test-ab": {
                "variants": [
                    {"label": "a", "status": "completed"},
                    {"label": "b", "status": "failed"},
                ]
            }
        }
        sync_ab_experiment_status(manifest, "test-ab")
        self.assertEqual(manifest["ab_experiments"]["test-ab"]["status"], "failed")

    def test_sync_experiment_status_one_in_progress(self) -> None:
        manifest = self._empty_manifest()
        manifest["ab_experiments"] = {
            "test-ab": {
                "variants": [
                    {"label": "a", "status": "completed"},
                    {"label": "b", "status": "in_progress"},
                ]
            }
        }
        sync_ab_experiment_status(manifest, "test-ab")
        self.assertEqual(manifest["ab_experiments"]["test-ab"]["status"], "in_progress")


# ---------------------------------------------------------------------------
# ABExpandTests
# ---------------------------------------------------------------------------


class ABExpandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_dirs_and_manifest(self) -> tuple[Path, Path]:
        batch_dir = self.tmp_path / "strategies" / "demo_strategy" / "test_batches" / "test-batch"
        scenarios_dir = batch_dir / "scenarios"
        scenarios_dir.mkdir(parents=True)
        manifest_path = batch_dir / "manifest.json"
        manifest_path.write_text(json.dumps({
            "batch_id": "test-batch",
            "strategy": "demo_strategy",
            "scenarios": {},
        }), encoding="utf-8")
        return manifest_path, batch_dir

    @patch("scripts.tools.jq_automation.abtest.resolve_git_ref")
    @patch("scripts.tools.jq_automation.abtest.assert_file_at_commit")
    @patch("scripts.tools.jq_automation.abtest.materialize_strategy_source")
    def test_expand_generates_scenario_files(
        self, mock_mat: Mock, mock_assert: Mock, mock_resolve: Mock
    ) -> None:
        mock_resolve.return_value = "a" * 40
        mock_assert.return_value = "a" * 40
        mock_mat.return_value = self.tmp_path / "dummy.py"

        manifest_path, batch_dir = self._make_dirs_and_manifest()

        cfg = load_ab_config(_ab_config_dict())
        expand_ab_experiment(cfg, manifest_path)

        # Verify manifest was populated with correct scenario_ids
        manifest = load_manifest(manifest_path)
        exp = get_ab_experiment(manifest, "test-ab")
        self.assertIsNotNone(exp)
        self.assertEqual(len(exp["variants"]), 2)
        self.assertEqual(exp["variants"][0]["scenario_id"], "ab-test-ab-main_best")
        self.assertEqual(exp["variants"][1]["scenario_id"], "ab-test-ab-branch_best")
        self.assertTrue((batch_dir / "scenarios" / "ab-test-ab-main_best" / "scenario.json").is_file())

    @patch("scripts.tools.jq_automation.abtest.resolve_git_ref")
    @patch("scripts.tools.jq_automation.abtest.assert_file_at_commit")
    @patch("scripts.tools.jq_automation.abtest.materialize_strategy_source")
    def test_expand_writes_manifest_entry(
        self, mock_mat: Mock, mock_assert: Mock, mock_resolve: Mock
    ) -> None:
        mock_resolve.return_value = "a" * 40
        mock_assert.return_value = "a" * 40
        mock_mat.return_value = self.tmp_path / "dummy.py"

        manifest_path, _ = self._make_dirs_and_manifest()
        cfg = load_ab_config(_ab_config_dict())
        expand_ab_experiment(cfg, manifest_path)

        manifest = load_manifest(manifest_path)
        exp = get_ab_experiment(manifest, "test-ab")
        self.assertIsNotNone(exp)
        self.assertEqual(exp["baseline"], "main_best")
        self.assertEqual(len(exp["variants"]), 2)
        self.assertEqual(exp["variants"][0]["upload_index"], 1)
        self.assertEqual(exp["variants"][1]["upload_index"], 2)
        self.assertIn("config_hash", exp)

    @patch("scripts.tools.jq_automation.abtest.resolve_git_ref")
    @patch("scripts.tools.jq_automation.abtest.assert_file_at_commit")
    @patch("scripts.tools.jq_automation.abtest.materialize_strategy_source")
    def test_expand_is_idempotent(
        self, mock_mat: Mock, mock_assert: Mock, mock_resolve: Mock
    ) -> None:
        mock_resolve.return_value = "a" * 40
        mock_assert.return_value = "a" * 40
        mock_mat.return_value = self.tmp_path / "dummy.py"

        manifest_path, _ = self._make_dirs_and_manifest()
        cfg = load_ab_config(_ab_config_dict())
        e1 = expand_ab_experiment(cfg, manifest_path)
        e2 = expand_ab_experiment(cfg, manifest_path)
        self.assertEqual(e1["config_hash"], e2["config_hash"])

    @patch("scripts.tools.jq_automation.abtest.resolve_git_ref")
    @patch("scripts.tools.jq_automation.abtest.assert_file_at_commit")
    @patch("scripts.tools.jq_automation.abtest.materialize_strategy_source")
    def test_expand_rejects_config_hash_change_on_completed(
        self, mock_mat: Mock, mock_assert: Mock, mock_resolve: Mock
    ) -> None:
        mock_resolve.return_value = "a" * 40
        mock_assert.return_value = "a" * 40
        mock_mat.return_value = self.tmp_path / "dummy.py"

        manifest_path, _ = self._make_dirs_and_manifest()
        cfg = load_ab_config(_ab_config_dict())
        expand_ab_experiment(cfg, manifest_path)

        # Manually mark all variants as completed
        manifest = load_manifest(manifest_path)
        for v in manifest["ab_experiments"]["test-ab"]["variants"]:
            v["status"] = "completed"
            v["run_id"] = "some-run"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

        # Change config and try to expand again
        cfg2 = load_ab_config(_ab_config_dict(experiment_id="test-ab", baseline="main_best"))
        # The config hash is the same as before since data is unchanged
        # Need to change actual data
        raw2 = _ab_config_dict(baseline="main_best")
        raw2["experiment_id"] = "test-ab"
        raw2["base"]["estimated_minutes"] = 999
        cfg3 = load_ab_config(raw2)

        with self.assertRaises(ABExpandError):
            expand_ab_experiment(cfg3, manifest_path)


# ---------------------------------------------------------------------------
# Regression tests
# ---------------------------------------------------------------------------


class RegressionTests(unittest.TestCase):
    def test_existing_update_manifest_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mp = Path(tmp) / "manifest.json"
            mp.write_text(json.dumps({
                "batch_id": "test",
                "strategy": "demo",
            }), encoding="utf-8")
            result = update_manifest(mp, scenario_id="s01", label="baseline",
                                     status="in_progress")
            self.assertEqual(result["scenarios"]["s01"]["status"], "in_progress")

    def test_existing_list_pending_still_works(self) -> None:
        manifest = {
            "scenarios": {
                "s01": {"status": "pending", "runs": []},
                "s02": {"status": "completed", "runs": [{"label": "ok", "status": "completed"}]},
            }
        }
        pending = list_pending_runs(manifest)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0][0], "s01")


if __name__ == "__main__":
    unittest.main()
