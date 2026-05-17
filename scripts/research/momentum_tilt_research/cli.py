"""CLI for momentum-tilt follow-up research workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research.research_core.audit import load_rebalance_events
from scripts.research.research_core.metrics import parse_cumulative_returns_md
from scripts.research.research_core.prices import load_price_bundle
from scripts.research.research_core.reporting import write_json

from .analysis import (
    analyze_project,
    calibrate_replay,
    default_raw_price_path,
    default_audit_log_path,
    default_baseline_returns_path,
    default_project_dir,
    write_cloud_robustness_report,
)
from .spec import ETF_CODES, STRATEGY


def _cmd_replay_calibrate(args: argparse.Namespace) -> int:
    events = load_rebalance_events(args.audit_log)
    frames = load_price_bundle(args.raw_data, ETF_CODES)
    baseline_returns = parse_cumulative_returns_md(args.baseline_returns)
    result = calibrate_replay(events, frames, baseline_returns)
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    result = analyze_project(
        project_dir=args.project_dir,
        run_id=args.run_id,
        stage=args.stage,
        raw_price_path=args.raw_data,
        audit_log_path=args.audit_log,
        baseline_returns_path=args.baseline_returns,
    )
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))
    return 0


def _batch_a_payload(batch_id: str) -> dict:
    return {
        "experiment_id": "momentum-strength-confirmation",
        "strategy": STRATEGY,
        "batch_id": batch_id,
        "baseline": "baseline-linear-050",
        "controls": ["baseline-linear-050"],
        "base": {
            "code_source": {
                "type": "git",
                "ref": "main",
                "path": "strategies/etf_factor_rotation/etf_factor_rotation.py",
            },
            "start_date": "2021-01-01",
            "end_date": "2026-04-30",
            "capital": 100000,
            "estimated_minutes": 6,
            "frequency": "1d",
            "py_version": "Python3",
        },
        "variants": [
            {
                "label": "baseline-linear-050",
                "role": "control",
                "params_mode": "params_diff",
                "params_diff": {},
                "note": "当前正式线性动量倾斜。",
            },
            *[
                {
                    "label": f"linear-{value:03d}",
                    "role": "variant",
                    "params_mode": "params_diff",
                    "params_diff": {"MomentumTiltStrength": value / 100},
                    "note": "线性动量倾斜强度确认。",
                }
                for value in [45, 40, 35, 25]
            ],
        ],
    }


def _cmd_ab_plan(args: argparse.Namespace) -> int:
    decision = json.loads(Path(args.local_decision).read_text(encoding="utf-8"))
    if not decision.get("ab_ready"):
        raise SystemExit("local gates are not all passed; A/B plan generation is blocked")
    output_dir = Path(args.output_dir)
    abtests_dir = output_dir / "abtests"
    abtests_dir.mkdir(parents=True, exist_ok=True)
    payload = _batch_a_payload(args.batch_id)
    write_json(
        output_dir / "manifest.json",
        {
            "batch_id": args.batch_id,
            "strategy": STRATEGY,
            "created": args.created,
            "status": "pending",
            "scenarios": {},
        },
    )
    write_json(abtests_dir / "momentum-strength-confirmation.json", payload)
    print(abtests_dir / "momentum-strength-confirmation.json")
    return 0


def _cmd_cloud_robustness(args: argparse.Namespace) -> int:
    frames = load_price_bundle(args.raw_data, ETF_CODES)
    path = write_cloud_robustness_report(
        baseline_run_id=args.baseline_run,
        variant_run_id=args.variant_run,
        label=args.label,
        frames=frames,
    )
    print(path)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    calibrate = subparsers.add_parser("replay-calibrate", help="validate local replay against known cloud runs")
    calibrate.add_argument("--raw-data", default=str(default_raw_price_path()))
    calibrate.add_argument("--audit-log", default=str(default_audit_log_path()))
    calibrate.add_argument("--baseline-returns", default=str(default_baseline_returns_path()))
    calibrate.add_argument("--output")
    calibrate.set_defaults(func=_cmd_replay_calibrate)

    analyze = subparsers.add_parser("analyze", help="run staged local momentum-tilt analysis")
    analyze.add_argument("--project-dir", default=str(default_project_dir()))
    analyze.add_argument("--run-id", required=True)
    analyze.add_argument("--stage", choices=["phase0", "phase1", "phase2", "all"], default="all")
    analyze.add_argument("--raw-data", default=str(default_raw_price_path()))
    analyze.add_argument("--audit-log", default=str(default_audit_log_path()))
    analyze.add_argument("--baseline-returns", default=str(default_baseline_returns_path()))
    analyze.set_defaults(func=_cmd_analyze)

    ab_plan = subparsers.add_parser("ab-plan", help="generate cloud batch-A config after local gates pass")
    ab_plan.add_argument("--local-decision", required=True)
    ab_plan.add_argument("--batch-id", default="20260517-momentum-strength-confirmation")
    ab_plan.add_argument("--output-dir", required=True)
    ab_plan.add_argument("--created", default="2026-05-17T00:00:00")
    ab_plan.set_defaults(func=_cmd_ab_plan)

    robustness = subparsers.add_parser("cloud-robustness", help="write robustness report for realized cloud runs")
    robustness.add_argument("--baseline-run", required=True)
    robustness.add_argument("--variant-run", required=True)
    robustness.add_argument("--label", required=True)
    robustness.add_argument("--raw-data", default=str(default_raw_price_path()))
    robustness.set_defaults(func=_cmd_cloud_robustness)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
