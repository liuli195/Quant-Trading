"""CLI entrypoint for the local-first research platform."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .platform.engine import create_project, handoff_cloud, promote_run, resume_run, run_project


def _cmd_init(args: argparse.Namespace) -> int:
    datasets = []
    if args.dataset_id and args.snapshot_id:
        datasets.append({"dataset_id": args.dataset_id, "snapshot_id": args.snapshot_id})
    variants = []
    for value in args.variant_return or []:
        label, sep, path = value.partition("=")
        if not sep or not label or not path:
            raise SystemExit("--variant-return must use label=path")
        variants.append({"label": label, "returns": path})
    extra_inputs = {}
    if args.audit_log:
        extra_inputs["audit_log"] = args.audit_log
    if args.baseline_returns:
        extra_inputs["baseline_returns"] = args.baseline_returns
    if variants:
        extra_inputs["variants"] = variants
    path = create_project(
        project_dir=args.project_dir,
        strategy=args.strategy,
        project=args.project,
        template=args.template,
        plugin=args.plugin,
        datasets=datasets,
        raw_data=args.raw_data,
        extra_inputs=extra_inputs,
    )
    print(path)
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    result = run_project(
        project_dir=args.project_dir,
        run_id=args.run_id,
        mode=args.mode,
        top_k=args.top_k,
        cloud_top_k=args.cloud_top_k,
    )
    print(json.dumps(result["manifest"], ensure_ascii=False, indent=2))
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    result = promote_run(
        project_dir=args.project_dir,
        fast_run_id=args.fast_run_id,
        full_run_id=args.full_run_id,
        top_k=args.top_k,
        cloud_top_k=args.cloud_top_k,
    )
    print(json.dumps(result["manifest"], ensure_ascii=False, indent=2))
    return 0


def _cmd_handoff_cloud(args: argparse.Namespace) -> int:
    payload = handoff_cloud(project_dir=args.project_dir, run_id=args.run_id)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    project_dir = Path(args.project_dir)
    rows = []
    runs_dir = project_dir / "runs"
    if runs_dir.exists():
        for status_path in sorted(runs_dir.glob("*/status.json")):
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            rows.append({"run_id": status_path.parent.name, **payload})
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    result = resume_run(project_dir=args.project_dir, run_id=args.run_id)
    print(json.dumps(result["manifest"], ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="create one research project skeleton")
    init.add_argument("--project-dir", required=True)
    init.add_argument("--strategy", required=True)
    init.add_argument("--project", required=True)
    init.add_argument(
        "--template",
        choices=["factor_scan", "parameter_followup", "robustness_check", "generic", "portfolio_volatility"],
        required=True,
    )
    init.add_argument("--plugin")
    init.add_argument("--dataset-id")
    init.add_argument("--snapshot-id")
    init.add_argument("--raw-data")
    init.add_argument("--audit-log")
    init.add_argument("--baseline-returns")
    init.add_argument("--variant-return", action="append", help="repeatable label=path pair for robustness_check")
    init.set_defaults(func=_cmd_init)

    run = subparsers.add_parser("run", help="run one fast or full local research pass")
    run.add_argument("--project-dir", required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--mode", choices=["fast", "full"], required=True)
    run.add_argument("--top-k", type=int)
    run.add_argument("--cloud-top-k", type=int)
    run.set_defaults(func=_cmd_run)

    promote = subparsers.add_parser("promote", help="promote a fast run shortlist into a full run")
    promote.add_argument("--project-dir", required=True)
    promote.add_argument("--fast-run-id", required=True)
    promote.add_argument("--full-run-id", required=True)
    promote.add_argument("--top-k", type=int)
    promote.add_argument("--cloud-top-k", type=int)
    promote.set_defaults(func=_cmd_promote)

    handoff = subparsers.add_parser("handoff-cloud", help="write cloud handoff materials for one full run")
    handoff.add_argument("--project-dir", required=True)
    handoff.add_argument("--run-id", required=True)
    handoff.set_defaults(func=_cmd_handoff_cloud)

    status = subparsers.add_parser("status", help="show run status rows")
    status.add_argument("--project-dir", required=True)
    status.set_defaults(func=_cmd_status)

    resume = subparsers.add_parser("resume", help="resume one persisted run request")
    resume.add_argument("--project-dir", required=True)
    resume.add_argument("--run-id", required=True)
    resume.set_defaults(func=_cmd_resume)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
