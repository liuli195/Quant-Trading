"""Built-in research plugins for the local-first platform."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.research.etf_window_research import analysis as window_analysis
from scripts.research.etf_window_research.spec import (
    BOOTSTRAP_REPS,
    FACTOR_SPECS,
    PRIMARY_HORIZON,
    SCORE_END,
    SCORE_START,
    SEGMENTS,
)
from scripts.research.research_core.metrics import (
    paired_block_bootstrap,
    parse_cumulative_returns_md,
    performance_metrics,
    rolling_sharpe,
    yearly_metrics,
)
from scripts.research.research_core.audit import load_rebalance_events
from scripts.research.research_core.prices import load_price_bundle
from scripts.research.momentum_tilt_research.analysis import calibrate_replay
from scripts.research.momentum_tilt_research.replay import (
    VariantSpec,
    replay_variant,
    summarize_variant_vs_baseline,
)
from scripts.research.momentum_tilt_research.spec import ETF_CODES as MOMENTUM_TILT_ETF_CODES
from scripts.research.momentum_tilt_research.spec import LINEAR_STRENGTHS
from scripts.research.portfolio_volatility_research.domain_builder import (
    build_domains as build_portfolio_vol_domains,
    representative_smoke_points,
)
from scripts.research.portfolio_volatility_research.evaluator import (
    evaluate_variant as evaluate_portfolio_vol_variant,
    load_context as load_portfolio_vol_context,
)
from scripts.research.portfolio_volatility_research.report_spec import (
    render_full_report as render_portfolio_vol_full_report,
    render_smoke_report as render_portfolio_vol_smoke_report,
)

from .batch_executor import execute_batch
from .benchmark_runner import run_smoke_benchmark
from .coverage_audit import ScanCoverageSlice, audit_scan_coverage, coverage_is_complete
from .contracts import FidelityLevel, PluginCapabilities, ResearchRunContext
from .datasets import load_price_frames, load_snapshot
from .funnel import CandidateFunnel, build_fast_funnel, promote_full_funnel


def _candidate_id(factor: str, etf: str, window: int) -> str:
    return f"{factor}:{etf}:{window}"


class FactorScanPlugin:
    """Fast window/factor screening backed by the existing ETF research logic."""

    name = "factor_scan"
    template = "factor_scan"
    code_version = "factor_scan:v1"
    capabilities = PluginCapabilities(
        local_capabilities=("factor_windows", "thresholds", "holdout", "segment_stability", "bootstrap"),
        replayable_params=(),
        required_exports=(),
        unsupported_changes=("order_execution", "minute_level_logic", "unexported_external_data"),
        fidelity_level=FidelityLevel.LOCAL_EXACT,
    )

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            "plugin": self.name,
            "factor_specs": [asdict(spec) for spec in FACTOR_SPECS],
            "score_start": SCORE_START.isoformat(),
            "score_end": SCORE_END.isoformat(),
            "primary_horizon": PRIMARY_HORIZON,
        }

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        dataset = (project.get("datasets") or [None])[0]
        if dataset:
            snapshot = load_snapshot(
                dataset["dataset_id"],
                dataset["snapshot_id"],
                datasets_root=project.get("datasets_root", "research_datasets"),
            )
            return snapshot.fingerprint
        raw_data = project.get("inputs", {}).get("raw_data")
        if not raw_data:
            raise ValueError("factor_scan requires datasets[0] or inputs.raw_data")
        return f"sha256:{_sha256_file(Path(raw_data))}"

    def _load_frames(self, project: dict[str, Any]):
        dataset = (project.get("datasets") or [None])[0]
        if dataset:
            snapshot = load_snapshot(
                dataset["dataset_id"],
                dataset["snapshot_id"],
                datasets_root=project.get("datasets_root", "research_datasets"),
            )
            return load_price_frames(snapshot), snapshot.fingerprint
        raw_data = project.get("inputs", {}).get("raw_data")
        if not raw_data:
            raise ValueError("factor_scan requires datasets[0] or inputs.raw_data")
        raw_path = Path(raw_data)
        return load_price_bundle(raw_path), f"sha256:{_sha256_file(raw_path)}"

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        frames, dataset_fingerprint = self._load_frames(project)
        return {
            "frames": frames,
            "research_cache": window_analysis.build_research_cache(frames),
            "dataset_fingerprint": dataset_fingerprint,
        }

    def run_fast(self, context: ResearchRunContext, features: dict[str, Any]) -> dict[str, Any]:
        grid = window_analysis.build_factor_window_grid(
            features["frames"],
            horizons=(PRIMARY_HORIZON,),
            bootstrap_horizons=(),
            bootstrap_reps=0,
            cache=features["research_cache"],
        )
        ranked = grid.copy()
        ranked["candidate_id"] = ranked.apply(
            lambda row: _candidate_id(str(row["factor"]), str(row["etf"]), int(row["window"])),
            axis=1,
        )
        funnel = build_fast_funnel(ranked, score_column="benefit", top_k=context.top_k)
        return {
            "grid": grid,
            "funnel": funnel,
            "decision": {
                "mode": "fast",
                "candidate_count": int(len(ranked)),
                "shortlist_count": int(len(funnel.shortlist)),
                "best_candidate_id": None if funnel.ranked.empty else str(funnel.ranked.iloc[0]["candidate_id"]),
            },
        }

    def run_full(
        self,
        context: ResearchRunContext,
        features: dict[str, Any],
        shortlist: pd.DataFrame,
    ) -> dict[str, Any]:
        cache = features["research_cache"]
        frames = features["frames"]
        reviewed = _review_shortlist(frames, cache, shortlist)
        funnel = promote_full_funnel(reviewed, cloud_top_k=context.cloud_top_k)
        return {
            "reviewed": reviewed,
            "funnel": funnel,
            "decision": {
                "mode": "full",
                "reviewed_count": int(len(reviewed)),
                "eligible_count": int(reviewed["eligible_for_cloud"].sum()) if not reviewed.empty else 0,
                "cloud_candidate_count": int(len(funnel.cloud_candidates)),
            },
        }

    def build_cloud_handoff(
        self,
        context: ResearchRunContext,
        cloud_candidates: pd.DataFrame,
    ) -> dict[str, Any] | None:
        if cloud_candidates.empty:
            return {
                "status": "blocked",
                "reason": "no_local_candidate_passed",
                "commands": [],
            }
        return {
            "status": "ready_for_design",
            "reason": "local_candidates_passed",
            "candidate_ids": cloud_candidates["candidate_id"].tolist(),
            "commands": [
                "根据 cloud_candidates.csv 生成模块级 A/B 配置",
                "通过 jq-ab-test 设计并校验云端确认实验",
            ],
        }


class ParameterFollowupPlugin:
    """Replayable parameter studies routed through strategy-specific adapters."""

    name = "parameter_followup"
    template = "parameter_followup"
    code_version = "parameter_followup:v2"
    capabilities = PluginCapabilities(
        local_capabilities=("parameter_strength", "weight_shape", "counterfactual_replay"),
        replayable_params=("weight_shape", "tilt_strength", "local_threshold"),
        required_exports=(
            "daily_returns",
            "signals",
            "gates",
            "scores",
            "penalties",
            "target_weights",
            "actual_weights",
            "params",
            "audit_events",
        ),
        unsupported_changes=("signal_definition", "execution_logic", "external_data_dependency"),
        fidelity_level=FidelityLevel.LOCAL_REPLAYABLE,
    )

    def _adapter(self, project: dict[str, Any]) -> "ParameterReplayAdapter":
        adapter_name = project.get("inputs", {}).get("adapter", "momentum_tilt")
        try:
            return PARAMETER_REPLAY_ADAPTERS[adapter_name]
        except KeyError as exc:
            raise KeyError(f"unknown parameter replay adapter: {adapter_name}") from exc

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            "plugin": self.name,
            "adapter": self._adapter(project).name,
            "adapter_spec": self._adapter(project).build_feature_spec(project),
        }

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        return self._adapter(project).dataset_fingerprint(project)

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        return self._adapter(project).build_features(project)

    def run_fast(self, context: ResearchRunContext, features: dict[str, Any]) -> dict[str, Any]:
        adapter = self._adapter(context.project)
        ranked = pd.DataFrame([adapter.score_fast(features, variant) for variant in adapter.variants(context.project)])
        funnel = build_fast_funnel(ranked, score_column="fast_score", top_k=context.top_k)
        return {
            "grid": ranked,
            "funnel": funnel,
            "decision": {
                "mode": "fast",
                "candidate_count": int(len(ranked)),
                "shortlist_count": int(len(funnel.shortlist)),
                "best_candidate_id": None if funnel.ranked.empty else str(funnel.ranked.iloc[0]["candidate_id"]),
                "adapter": adapter.name,
            },
        }

    def run_full(
        self,
        context: ResearchRunContext,
        features: dict[str, Any],
        shortlist: pd.DataFrame,
    ) -> dict[str, Any]:
        adapter = self._adapter(context.project)
        reviewed = pd.DataFrame(
            [adapter.review_full(features, row) for row in shortlist.to_dict(orient="records")]
        )
        funnel = promote_full_funnel(reviewed, cloud_top_k=context.cloud_top_k)
        return {
            "reviewed": reviewed,
            "funnel": funnel,
            "decision": {
                "mode": "full",
                "reviewed_count": int(len(reviewed)),
                "eligible_count": int(reviewed["eligible_for_cloud"].sum()) if not reviewed.empty else 0,
                "cloud_candidate_count": int(len(funnel.cloud_candidates)),
                "adapter": adapter.name,
            },
        }

    def build_cloud_handoff(
        self,
        context: ResearchRunContext,
        cloud_candidates: pd.DataFrame,
    ) -> dict[str, Any] | None:
        return {
            "status": "ready" if not cloud_candidates.empty else "blocked",
            "reason": "replay_candidates_passed" if not cloud_candidates.empty else "no_candidate_passed",
            "candidate_ids": [] if cloud_candidates.empty else cloud_candidates["candidate_id"].tolist(),
        }


class RobustnessCheckPlugin:
    """Post-run robustness checks for realized return paths."""

    name = "robustness_check"
    template = "robustness_check"
    code_version = "robustness_check:v1"
    capabilities = PluginCapabilities(
        local_capabilities=("paired_bootstrap", "rolling_windows", "yearly_decomposition"),
        replayable_params=(),
        required_exports=("daily_returns",),
        unsupported_changes=("new_strategy_discovery",),
        fidelity_level=FidelityLevel.LOCAL_EXACT,
    )

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        return {
            "plugin": self.name,
            "variants": project.get("inputs", {}).get("variants", []),
        }

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        inputs = project.get("inputs", {})
        baseline_returns = inputs.get("baseline_returns")
        variants = inputs.get("variants", [])
        if not baseline_returns or not variants:
            raise ValueError("robustness_check requires inputs.baseline_returns and inputs.variants")
        payload = {
            "baseline_returns": _sha256_file(Path(baseline_returns)),
            "variants": [
                {
                    "label": item["label"],
                    "returns": _sha256_file(Path(item["returns"])),
                }
                for item in variants
            ],
        }
        return f"sha256:{_stable_json_hash(payload)}"

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        inputs = project.get("inputs", {})
        baseline_returns = parse_cumulative_returns_md(inputs["baseline_returns"])
        variants = {
            item["label"]: parse_cumulative_returns_md(item["returns"])
            for item in inputs["variants"]
        }
        return {
            "baseline_returns": baseline_returns,
            "variants": variants,
        }

    def run_fast(self, context: ResearchRunContext, features: dict[str, Any]) -> dict[str, Any]:
        baseline = features["baseline_returns"]
        baseline_metrics = performance_metrics(baseline)
        rows = []
        for label, variant in features["variants"].items():
            aligned = _align_returns(baseline, variant)
            metrics = performance_metrics(aligned["variant"])
            rows.append(
                {
                    "candidate_id": label,
                    "variant": label,
                    "days": int(len(aligned)),
                    "annual_return": metrics["annual_return"],
                    "sharpe": metrics["sharpe"],
                    "max_drawdown": metrics["max_drawdown"],
                    "annual_return_delta": metrics["annual_return"] - baseline_metrics["annual_return"],
                    "sharpe_delta": metrics["sharpe"] - baseline_metrics["sharpe"],
                }
            )
        ranked = pd.DataFrame(rows)
        funnel = build_fast_funnel(ranked, score_column="sharpe_delta", top_k=context.top_k)
        return {
            "grid": ranked,
            "funnel": funnel,
            "decision": {
                "mode": "fast",
                "candidate_count": int(len(ranked)),
                "shortlist_count": int(len(funnel.shortlist)),
                "best_candidate_id": None if funnel.ranked.empty else str(funnel.ranked.iloc[0]["candidate_id"]),
            },
        }

    def run_full(
        self,
        context: ResearchRunContext,
        features: dict[str, Any],
        shortlist: pd.DataFrame,
    ) -> dict[str, Any]:
        baseline = features["baseline_returns"]
        reviewed_rows = []
        for candidate in shortlist.itertuples():
            aligned = _align_returns(baseline, features["variants"][candidate.variant])
            base = aligned["baseline"]
            variant = aligned["variant"]
            baseline_metrics = performance_metrics(base)
            variant_metrics = performance_metrics(variant)
            bootstrap = paired_block_bootstrap(base, variant)
            rolling = pd.concat(
                [
                    rolling_sharpe(base).rename("baseline"),
                    rolling_sharpe(variant).rename("variant"),
                ],
                axis=1,
            ).dropna()
            yearly = yearly_metrics(variant).merge(
                yearly_metrics(base),
                on="year",
                suffixes=("_variant", "_baseline"),
            )
            years_better = int((yearly["sharpe_variant"] > yearly["sharpe_baseline"]).sum())
            rolling_win_rate = (
                float((rolling["variant"] > rolling["baseline"]).mean()) if not rolling.empty else 0.0
            )
            eligible = bool(
                variant_metrics["sharpe"] > baseline_metrics["sharpe"]
                and variant_metrics["annual_return"] >= baseline_metrics["annual_return"] - 0.003
                and bootstrap["ci_low"] >= 0
                and rolling_win_rate > 0.55
                and years_better >= max(1, len(yearly) // 2)
            )
            reasons = []
            if variant_metrics["sharpe"] <= baseline_metrics["sharpe"]:
                reasons.append("sharpe_not_higher")
            if variant_metrics["annual_return"] < baseline_metrics["annual_return"] - 0.003:
                reasons.append("annual_return_too_low")
            if bootstrap["ci_low"] < 0:
                reasons.append("bootstrap_crosses_zero")
            if rolling_win_rate <= 0.55:
                reasons.append("rolling_win_rate_low")
            if years_better < max(1, len(yearly) // 2):
                reasons.append("yearly_stability_low")
            reviewed_rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "variant": candidate.variant,
                    "fast_sharpe_delta": float(candidate.sharpe_delta),
                    "annual_return_delta": variant_metrics["annual_return"] - baseline_metrics["annual_return"],
                    "sharpe_delta": variant_metrics["sharpe"] - baseline_metrics["sharpe"],
                    "max_drawdown_delta": variant_metrics["max_drawdown"] - baseline_metrics["max_drawdown"],
                    "rolling_sharpe_win_rate": rolling_win_rate,
                    "years_better": years_better,
                    "years_total": int(len(yearly)),
                    "bootstrap_observed": bootstrap["observed"],
                    "bootstrap_ci_low": bootstrap["ci_low"],
                    "bootstrap_ci_high": bootstrap["ci_high"],
                    "bootstrap_p_value": bootstrap["p_value"],
                    "eligible_for_cloud": eligible,
                    "promotion_reasons": "passed_local_gates" if eligible else ";".join(reasons),
                    "refinement_score": float(candidate.sharpe_delta),
                }
            )
        reviewed = pd.DataFrame(reviewed_rows)
        funnel = promote_full_funnel(reviewed, cloud_top_k=context.cloud_top_k)
        return {
            "reviewed": reviewed,
            "funnel": funnel,
            "decision": {
                "mode": "full",
                "reviewed_count": int(len(reviewed)),
                "eligible_count": int(reviewed["eligible_for_cloud"].sum()) if not reviewed.empty else 0,
                "cloud_candidate_count": int(len(funnel.cloud_candidates)),
            },
        }

    def build_cloud_handoff(
        self,
        context: ResearchRunContext,
        cloud_candidates: pd.DataFrame,
    ) -> dict[str, Any] | None:
        return {
            "status": "ready" if not cloud_candidates.empty else "blocked",
            "reason": "robustness_passed" if not cloud_candidates.empty else "no_candidate_passed",
            "candidate_ids": [] if cloud_candidates.empty else cloud_candidates["candidate_id"].tolist(),
        }


class GenericPlugin:
    """Minimal scaffolding plugin for diagnostic / exploratory research.

    Provides the standard project skeleton and data-contract infrastructure
    without imposing any candidate-funnel workflow.  Actual analysis logic
    lives in standalone modules and writes results into ``runs/<run_id>/``.
    """

    name = "generic"
    template = "generic"
    code_version = "generic:v1"
    capabilities = PluginCapabilities(
        local_capabilities=("diagnostic", "data_exploration", "project_scaffolding"),
        replayable_params=(),
        required_exports=(),
        unsupported_changes=(),
        fidelity_level=FidelityLevel.LOCAL_EXACT,
    )

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        return {"plugin": self.name, "datasets": project.get("datasets", [])}

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        datasets = project.get("datasets") or []
        if datasets:
            parts = [f"{d['dataset_id']}/{d['snapshot_id']}" for d in datasets]
            return f"generic:{'+'.join(parts)}"
        return "generic:no-datasets"

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        return {"project": project, "datasets": project.get("datasets", [])}

    def run_fast(self, context: ResearchRunContext, features: dict[str, Any]) -> dict[str, Any]:
        return {
            "grid": pd.DataFrame({"status": ["ok"]}),
            "funnel": CandidateFunnel(
                ranked=pd.DataFrame(),
                discarded=pd.DataFrame(),
                shortlist=pd.DataFrame(),
                cloud_candidates=pd.DataFrame(),
            ),
            "decision": {
                "mode": "fast",
                "template": "generic",
                "message": "Generic project scaffolded. Run custom analysis scripts for diagnostics.",
            },
        }

    def run_full(
        self,
        context: ResearchRunContext,
        features: dict[str, Any],
        shortlist: pd.DataFrame,
    ) -> dict[str, Any]:
        return {
            "reviewed": pd.DataFrame(),
            "funnel": CandidateFunnel(
                ranked=pd.DataFrame(),
                discarded=pd.DataFrame(),
                shortlist=pd.DataFrame(),
                cloud_candidates=pd.DataFrame(),
            ),
            "decision": {
                "mode": "full",
                "template": "generic",
                "message": "Generic full mode — no built-in analysis. Use standalone modules.",
            },
        }

    def build_cloud_handoff(
        self,
        context: ResearchRunContext,
        cloud_candidates: pd.DataFrame,
    ) -> dict[str, Any] | None:
        return {
            "status": "not_applicable",
            "reason": "generic_template_no_handoff",
            "commands": [],
        }


class PortfolioVolatilityPlugin:
    """Exact portfolio-volatility domain scan with performance smoke gating."""

    name = "portfolio_volatility"
    template = "portfolio_volatility"
    code_version = "portfolio_volatility:v2"
    capabilities = PluginCapabilities(
        local_capabilities=("performance_smoke", "exact_domain_scan", "coverage_audit"),
        replayable_params=("portfolio_vol_window", "target_vol"),
        required_exports=("daily_returns", "audit_events", "params"),
        unsupported_changes=("signal_definition", "execution_logic", "external_data_dependency"),
        fidelity_level=FidelityLevel.LOCAL_REPLAYABLE,
    )

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        inputs = project.get("inputs", {})
        return {
            "plugin": self.name,
            "baseline_run_dir": inputs.get("baseline_run_dir"),
            "raw_data": inputs.get("raw_data"),
            "algorithm": "exact-breakpoints-plus-interval-points",
        }

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        inputs = project.get("inputs", {})
        baseline_run_dir = Path(inputs["baseline_run_dir"])
        raw_data = Path(inputs["raw_data"])
        payload = {
            "raw_data": _sha256_file(raw_data),
            "audit_log": _sha256_file(baseline_run_dir / "tabs_raw" / "audit_log.jsonl"),
            "baseline_returns": _sha256_file(baseline_run_dir / "tabs_raw" / "daily_returns.md"),
            "summary_metrics": _sha256_file(baseline_run_dir / "summary_metrics.json"),
        }
        return f"sha256:{_stable_json_hash(payload)}"

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        inputs = project["inputs"]
        context = load_portfolio_vol_context(
            baseline_run_dir=Path(inputs["baseline_run_dir"]),
            raw_price_path=Path(inputs["raw_data"]),
        )
        domains = build_portfolio_vol_domains(context)
        coverage = audit_scan_coverage(
            [
                ScanCoverageSlice(
                    slice_id=str(domain.window),
                    lower_bound=0.0,
                    upper_bound=domain.upper_bound,
                    breakpoints=domain.breakpoints,
                    interval_points=domain.interval_points,
                    breakpoint_sources=domain.breakpoint_sources,
                )
                for domain in domains.values()
            ]
        )
        return {
            "context": context,
            "domains": domains,
            "coverage": coverage,
        }

    def run_fast(self, context: ResearchRunContext, features: dict[str, Any]) -> dict[str, Any]:
        domains = features["domains"]
        coverage = features["coverage"]
        smoke_points = representative_smoke_points(
            domains,
            per_window=int(context.project.get("inputs", {}).get("smoke_points_per_window", 16)),
        )
        full_item_count = sum(len(domain.evaluation_points) for domain in domains.values())
        target_seconds = float(context.project.get("runtime", {}).get("full_mode_slo_seconds", 60.0))
        summary = run_smoke_benchmark(
            smoke_points,
            lambda item: evaluate_portfolio_vol_variant(
                features["context"],
                window=int(item["window"]),
                target=float(item["target"]),
                label=f"smoke-w{int(item['window'])}-t{float(item['target']):.12f}",
            ),
            full_item_count=full_item_count,
            target_seconds=target_seconds,
        )
        complete = coverage_is_complete(coverage)
        feature_cache_hit = bool(context.feature_cache_hit)
        smoke_passed = bool(summary.passed and complete and feature_cache_hit)
        coverage.to_csv(context.run.tables_dir / "coverage_audit.csv", index=False)
        pd.DataFrame(smoke_points).to_csv(context.run.tables_dir / "smoke_points.csv", index=False)
        pd.DataFrame(summary.warm.rows).to_csv(context.run.tables_dir / "smoke_results.csv", index=False)
        payload = {
            "coverage_complete": complete,
            "feature_cache_hit": feature_cache_hit,
            "sample_size": summary.sample_size,
            "full_item_count": summary.full_item_count,
            "cold_seconds": summary.cold.runtime_seconds,
            "warm_seconds": summary.warm.runtime_seconds,
            "cold_per_item_seconds": summary.cold.per_item_seconds,
            "warm_per_item_seconds": summary.warm.per_item_seconds,
            "predicted_full_seconds": summary.predicted_full_seconds,
            "target_seconds": summary.target_seconds,
            "smoke_passed": smoke_passed,
        }
        (context.run.tables_dir / "smoke_summary.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (context.run.reports_dir / "portfolio-volatility-performance-smoke.md").write_text(
            render_portfolio_vol_smoke_report(
                coverage=coverage,
                summary=summary,
                feature_cache_hit=feature_cache_hit,
            ),
            encoding="utf-8",
        )
        ranked = pd.DataFrame(
            [
                {
                    "candidate_id": "portfolio-volatility-full-scan",
                    "fast_score": 1.0 if smoke_passed else 0.0,
                    "coverage_complete": complete,
                    "feature_cache_hit": feature_cache_hit,
                    "predicted_full_seconds": summary.predicted_full_seconds,
                    "target_seconds": summary.target_seconds,
                    "smoke_passed": smoke_passed,
                }
            ]
        )
        funnel = build_fast_funnel(ranked, score_column="fast_score", top_k=1)
        return {
            "grid": ranked,
            "funnel": funnel,
            "decision": {
                "mode": "fast",
                "candidate_count": 1,
                "shortlist_count": int(len(funnel.shortlist)),
                "smoke_passed": smoke_passed,
                "coverage_complete": complete,
                "feature_cache_hit": feature_cache_hit,
                "predicted_full_seconds": summary.predicted_full_seconds,
                "target_seconds": summary.target_seconds,
            },
        }

    def run_full(
        self,
        context: ResearchRunContext,
        features: dict[str, Any],
        shortlist: pd.DataFrame,
    ) -> dict[str, Any]:
        coverage = features["coverage"]
        items = [
            {"window": window, "target": target}
            for window, domain in features["domains"].items()
            for target in domain.evaluation_points
        ]
        batch = execute_batch(
            items,
            lambda item: evaluate_portfolio_vol_variant(
                features["context"],
                window=int(item["window"]),
                target=float(item["target"]),
                label=f"global-w{int(item['window'])}-t{float(item['target']):.12f}",
            ),
        )
        if batch.errors:
            raise RuntimeError(f"portfolio-volatility full scan failed for {len(batch.errors)} items")
        scan = pd.DataFrame(batch.rows)
        coverage.to_csv(context.run.tables_dir / "coverage_audit.csv", index=False)
        scan.to_csv(context.run.tables_dir / "portfolio_vol_full_scan.csv", index=False)
        (context.run.reports_dir / "portfolio-volatility-full-scan.md").write_text(
            render_portfolio_vol_full_report(
                global_scan=scan,
                coverage=coverage,
                baseline_position=float(features["context"].baseline_schedule.sum(axis=1).mean()),
            ),
            encoding="utf-8",
        )
        best = scan.sort_values(
            ["sharpe_delta", "annual_delta", "target"],
            ascending=[False, False, True],
        ).head(1)
        reviewed = best.assign(
            eligible_for_cloud=False,
            promotion_reasons="formal_local_scan_completed",
            refinement_score=best["sharpe_delta"],
        )
        funnel = promote_full_funnel(reviewed, cloud_top_k=context.cloud_top_k)
        return {
            "reviewed": reviewed,
            "funnel": funnel,
            "decision": {
                "mode": "full",
                "reviewed_count": int(len(reviewed)),
                "eligible_count": 0,
                "cloud_candidate_count": 0,
                "scan_point_count": int(len(scan)),
                "coverage_complete": coverage_is_complete(coverage),
                "runtime_seconds": batch.runtime_seconds,
            },
        }

    def validate_promotion(
        self,
        *,
        project_dir: Path,
        fast_run_id: str,
        shortlist: pd.DataFrame,
    ) -> None:
        """Allow full scan only after a warm, complete, passing smoke run."""

        summary_path = project_dir / "runs" / fast_run_id / "tables" / "smoke_summary.json"
        if not summary_path.is_file():
            raise ValueError("portfolio-volatility promotion requires smoke_summary.json")
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        reasons = []
        if not bool(payload.get("coverage_complete")):
            reasons.append("coverage_incomplete")
        if not bool(payload.get("feature_cache_hit")):
            reasons.append("feature_cache_not_warm")
        if not bool(payload.get("smoke_passed")):
            reasons.append("smoke_failed")
        if reasons:
            raise ValueError("portfolio-volatility promotion blocked: " + ";".join(reasons))

    def build_cloud_handoff(
        self,
        context: ResearchRunContext,
        cloud_candidates: pd.DataFrame,
    ) -> dict[str, Any] | None:
        return {
            "status": "not_applicable",
            "reason": "portfolio_volatility_local_scan_only",
            "candidate_ids": [],
        }


BUILTIN_PLUGINS = {
    FactorScanPlugin.name: FactorScanPlugin(),
    ParameterFollowupPlugin.name: ParameterFollowupPlugin(),
    RobustnessCheckPlugin.name: RobustnessCheckPlugin(),
    GenericPlugin.name: GenericPlugin(),
    PortfolioVolatilityPlugin.name: PortfolioVolatilityPlugin(),
}


class ParameterReplayAdapter:
    """Minimal strategy hook for replayable parameter studies."""

    name = "base"

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        raise NotImplementedError

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def variants(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def score_fast(self, features: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def review_full(self, features: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class MomentumTiltReplayAdapter(ParameterReplayAdapter):
    """Reference adapter backed by the existing momentum-tilt replay module."""

    name = "momentum_tilt"

    def build_feature_spec(self, project: dict[str, Any]) -> dict[str, Any]:
        return {"variants": self.variants(project)}

    def dataset_fingerprint(self, project: dict[str, Any]) -> str:
        inputs = project.get("inputs", {})
        raw_data = inputs.get("raw_data")
        audit_log = inputs.get("audit_log")
        baseline_returns = inputs.get("baseline_returns")
        if not raw_data or not audit_log or not baseline_returns:
            raise ValueError(
                "momentum_tilt adapter requires inputs.raw_data, inputs.audit_log and inputs.baseline_returns"
            )
        payload = {
            "raw_data": _sha256_file(Path(raw_data)),
            "audit_log": _sha256_file(Path(audit_log)),
            "baseline_returns": _sha256_file(Path(baseline_returns)),
            "variants": self.variants(project),
        }
        return f"sha256:{_stable_json_hash(payload)}"

    def build_features(self, project: dict[str, Any]) -> dict[str, Any]:
        inputs = project["inputs"]
        frames = load_price_bundle(inputs["raw_data"], MOMENTUM_TILT_ETF_CODES)
        events = load_rebalance_events(inputs["audit_log"])
        baseline_returns = parse_cumulative_returns_md(inputs["baseline_returns"])
        try:
            calibration = calibrate_replay(events, frames, baseline_returns)
        except FileNotFoundError as exc:
            calibration = {
                "passed": False,
                "reason": "calibration_inputs_missing",
                "error": str(exc),
            }
        return {
            "frames": frames,
            "events": events,
            "baseline_returns": baseline_returns,
            "baseline_metrics": performance_metrics(baseline_returns),
            "calibration": calibration,
        }

    def variants(self, project: dict[str, Any]) -> list[dict[str, Any]]:
        configured = project.get("inputs", {}).get("variants")
        if configured:
            return [dict(item) for item in configured]
        return [
            {"label": f"linear-{int(strength * 100):03d}", "strength": float(strength)}
            for strength in LINEAR_STRENGTHS
        ]

    def score_fast(self, features: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
        result = replay_variant(
            features["events"],
            features["frames"].close.reindex(columns=list(MOMENTUM_TILT_ETF_CODES)),
            features["baseline_returns"],
            _variant_spec(variant),
        )
        baseline = features["baseline_metrics"]
        return {
            "candidate_id": str(variant["label"]),
            "variant": str(variant["label"]),
            "strength": float(variant["strength"]),
            "shape": str(variant.get("shape", "linear")),
            "annual_return_delta": result.metrics["annual_return"] - baseline["annual_return"],
            "sharpe_delta": result.metrics["sharpe"] - baseline["sharpe"],
            "max_drawdown_delta": result.metrics["max_drawdown"] - baseline["max_drawdown"],
            "fast_score": result.metrics["sharpe"] - baseline["sharpe"],
        }

    def review_full(self, features: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
        result = replay_variant(
            features["events"],
            features["frames"].close.reindex(columns=list(MOMENTUM_TILT_ETF_CODES)),
            features["baseline_returns"],
            _variant_spec(candidate),
        )
        summary = summarize_variant_vs_baseline(features["baseline_returns"], result)
        calibration_passed = bool(features["calibration"].get("passed"))
        eligible = bool(
            calibration_passed
            and summary["sharpe_delta"] > 0
            and summary["annual_return_delta"] > 0
            and summary["bootstrap_ci_low"] >= 0
        )
        reasons = []
        if not calibration_passed:
            reasons.append("replay_not_calibrated")
        if summary["sharpe_delta"] <= 0:
            reasons.append("sharpe_not_higher")
        if summary["annual_return_delta"] <= 0:
            reasons.append("annual_return_not_higher")
        if summary["bootstrap_ci_low"] < 0:
            reasons.append("bootstrap_crosses_zero")
        return {
            "candidate_id": candidate["candidate_id"],
            "variant": candidate["variant"],
            "strength": float(candidate["strength"]),
            "shape": candidate["shape"],
            "fast_score": float(candidate["fast_score"]),
            **summary,
            "eligible_for_cloud": eligible,
            "promotion_reasons": "passed_local_gates" if eligible else ";".join(reasons),
            "refinement_score": float(candidate["fast_score"]),
        }


PARAMETER_REPLAY_ADAPTERS: dict[str, ParameterReplayAdapter] = {
    MomentumTiltReplayAdapter.name: MomentumTiltReplayAdapter(),
}


def get_plugin(name: str):
    try:
        return BUILTIN_PLUGINS[name]
    except KeyError as exc:
        raise KeyError(f"unknown research plugin: {name}") from exc


def _sha256_file(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_json_hash(payload: object) -> str:
    import hashlib

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _variant_spec(payload: dict[str, Any]) -> VariantSpec:
    label = payload.get("label") or payload.get("variant") or payload.get("candidate_id")
    if label is None:
        raise KeyError("variant payload requires label, variant or candidate_id")
    return VariantSpec(
        label=str(label),
        strength=float(payload["strength"]),
        shape=str(payload.get("shape", "linear")),
        extreme_start=None if payload.get("extreme_start") is None else float(payload["extreme_start"]),
        extreme_cap=float(payload.get("extreme_cap", 1.0)),
    )


def _align_returns(baseline: pd.Series, variant: pd.Series) -> pd.DataFrame:
    frame = pd.concat(
        [baseline.rename("baseline"), variant.rename("variant")],
        axis=1,
    ).dropna()
    if frame.empty:
        raise ValueError("baseline and variant returns do not overlap")
    return frame


def _grid_for_period(
    frames,
    cache,
    *,
    start: date,
    end: date,
) -> pd.DataFrame:
    return window_analysis.build_factor_window_grid(
        frames,
        start,
        end,
        horizons=(PRIMARY_HORIZON,),
        bootstrap_horizons=(),
        bootstrap_reps=0,
        cache=cache,
    )


def _review_shortlist(frames, cache, shortlist: pd.DataFrame) -> pd.DataFrame:
    if shortlist.empty:
        return shortlist.copy()

    discovery = _grid_for_period(frames, cache, start=SCORE_START, end=date(2024, 12, 31))
    holdout = _grid_for_period(frames, cache, start=date(2025, 1, 1), end=SCORE_END)
    segment_frames = []
    for name, (start, end) in SEGMENTS.items():
        if name in {"discovery", "holdout"}:
            continue
        frame = _grid_for_period(frames, cache, start=start, end=end)
        frame["segment"] = name
        segment_frames.append(frame)
    segments = pd.concat(segment_frames, ignore_index=True)

    rows: list[dict[str, Any]] = []
    for candidate in shortlist.itertuples():
        mask = (
            (discovery["factor"] == candidate.factor)
            & (discovery["etf"] == candidate.etf)
            & (discovery["window"] == candidate.window)
        )
        discovery_row = discovery[mask].iloc[0]
        holdout_mask = (
            (holdout["factor"] == candidate.factor)
            & (holdout["etf"] == candidate.etf)
            & (holdout["window"] == candidate.window)
        )
        holdout_row = holdout[holdout_mask].iloc[0]
        segment_mask = (
            (segments["factor"] == candidate.factor)
            & (segments["etf"] == candidate.etf)
            & (segments["window"] == candidate.window)
        )
        segment_rows = segments[segment_mask]
        segment_positive_ratio = float((segment_rows["benefit"] >= 0).mean()) if not segment_rows.empty else 0.0
        bootstrap = _bootstrap_candidate(frames, cache, str(candidate.factor), str(candidate.etf), int(candidate.window))
        eligible = bool(
            holdout_row["benefit"] >= 0
            and segment_positive_ratio >= 0.5
            and (pd.isna(bootstrap["ci_low"]) or bootstrap["ci_low"] >= 0)
        )
        reasons = []
        if holdout_row["benefit"] < 0:
            reasons.append("holdout_negative")
        if segment_positive_ratio < 0.5:
            reasons.append("segment_unstable")
        if pd.notna(bootstrap["ci_low"]) and bootstrap["ci_low"] < 0:
            reasons.append("bootstrap_crosses_zero")
        rows.append(
            {
                "candidate_id": candidate.candidate_id,
                "family": candidate.family,
                "factor": candidate.factor,
                "etf": candidate.etf,
                "etf_label": candidate.etf_label,
                "window": int(candidate.window),
                "fast_benefit": float(candidate.benefit),
                "discovery_benefit": float(discovery_row["benefit"]),
                "holdout_benefit": float(holdout_row["benefit"]),
                "segment_positive_ratio": segment_positive_ratio,
                **bootstrap,
                "eligible_for_cloud": eligible,
                "promotion_reasons": "passed_local_gates" if eligible else ";".join(reasons),
                "refinement_score": float(candidate.benefit) + float(holdout_row["benefit"]),
            }
        )
    return pd.DataFrame(rows)


def _bootstrap_candidate(frames, cache, factor: str, etf: str, window: int) -> dict[str, float]:
    anchors = cache.anchors
    forward = cache.forward
    signal_dates = set(anchors["signal_date"])
    etf_forward = forward[
        (forward["signal_date"].isin(signal_dates)) & (forward["etf"] == etf)
    ][["signal_date", "asof_date", f"forward_{PRIMARY_HORIZON}d"]].copy()
    etf_forward = etf_forward.rename(columns={f"forward_{PRIMARY_HORIZON}d": "forward_return"})
    factor_values = cache.factor_values[(factor, etf, window)]
    signal = etf_forward.copy()
    signal["factor_value"] = signal["asof_date"].map(factor_values)
    clean = signal.dropna(subset=["factor_value", "forward_return"])
    metric_fn = window_analysis._metric_fn_for_factor(factor)
    ci_low, ci_high, std_error = window_analysis._bootstrap_metric(
        clean,
        lambda sample, fn=metric_fn: fn(sample)["benefit"],
        reps=BOOTSTRAP_REPS,
    )
    return {
        "ci_low": ci_low,
        "ci_high": ci_high,
        "std_error": std_error,
    }
