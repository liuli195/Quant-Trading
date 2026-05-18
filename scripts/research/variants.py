"""CLI for strategy variant registry and guarded Git plans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .platform.strategy_variants import (
    StrategyMaterializer,
    StrategyManifestReader,
    StructuralBranchManager,
    VariantMergeManager,
    VariantRegistry,
)


def _payload_from_args(args: argparse.Namespace) -> dict:
    if args.payload_file:
        return json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    if args.payload_json:
        return json.loads(args.payload_json)
    return {}


def _strategy_dir(args: argparse.Namespace) -> str:
    strategy_dir = getattr(args, "strategy_dir", None)
    if strategy_dir:
        return str(strategy_dir)
    strategy = getattr(args, "strategy", None)
    if not strategy:
        raise ValueError("either --strategy-dir or --strategy is required")
    return str(StrategyManifestReader(getattr(args, "strategies_root", "strategies")).read(strategy).root)


def _cmd_list(args: argparse.Namespace) -> int:
    print(json.dumps(VariantRegistry(_strategy_dir(args)).list(), ensure_ascii=False, indent=2))
    return 0


def _cmd_register(args: argparse.Namespace) -> int:
    record = VariantRegistry(_strategy_dir(args)).register(
        variant_id=args.variant_id,
        variant_type=args.variant_type,
        payload=_payload_from_args(args),
        description=args.description or "",
        status=args.status,
        overwrite=args.overwrite,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def _cmd_materialize(args: argparse.Namespace) -> int:
    path = StrategyMaterializer(_strategy_dir(args), args.output_root).materialize(
        args.variant_id,
        run_id=args.run_id,
    )
    print(path)
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    record = VariantRegistry(_strategy_dir(args)).transition_status(
        args.variant_id,
        args.status,
        yes=args.yes,
    )
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def _cmd_branch_plan(args: argparse.Namespace) -> int:
    payload = StructuralBranchManager(args.repo_root).branch_plan(
        variant_id=args.variant_id,
        branch_name=args.branch_name,
        base_ref=args.base_ref,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_branch_create(args: argparse.Namespace) -> int:
    payload = StructuralBranchManager(args.repo_root).create_branch(
        variant_id=args.variant_id,
        branch_name=args.branch_name,
        base_ref=args.base_ref,
        yes=args.yes,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_merge_plan(args: argparse.Namespace) -> int:
    payload = VariantMergeManager(args.repo_root).merge_plan(
        source_ref=args.source_ref,
        target_ref=args.target_ref,
        strategy_root=_strategy_dir(args) if args.variant_id else None,
        variant_id=args.variant_id,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_merge_apply(args: argparse.Namespace) -> int:
    payload = VariantMergeManager(args.repo_root).apply_merge(
        source_ref=args.source_ref,
        target_ref=args.target_ref,
        yes=args.yes,
        strategy_root=_strategy_dir(args) if args.variant_id else None,
        variant_id=args.variant_id,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") != "conflict_or_failed" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list variants for one strategy")
    list_parser.add_argument("--strategy-dir")
    list_parser.add_argument("--strategy")
    list_parser.add_argument("--strategies-root", default="strategies")
    list_parser.set_defaults(func=_cmd_list)

    register = subparsers.add_parser("register", help="register one parameter or structural variant")
    register.add_argument("--strategy-dir")
    register.add_argument("--strategy")
    register.add_argument("--strategies-root", default="strategies")
    register.add_argument("--variant-id", required=True)
    register.add_argument("--variant-type", choices=["parameter", "structural"], required=True)
    register.add_argument("--payload-json")
    register.add_argument("--payload-file")
    register.add_argument("--description")
    register.add_argument("--status", default="candidate")
    register.add_argument("--overwrite", action="store_true")
    register.set_defaults(func=_cmd_register)

    materialize = subparsers.add_parser("materialize", help="materialize one strategy variant")
    materialize.add_argument("--strategy-dir")
    materialize.add_argument("--strategy")
    materialize.add_argument("--strategies-root", default="strategies")
    materialize.add_argument("--variant-id", required=True)
    materialize.add_argument("--run-id")
    materialize.add_argument("--output-root", default=".local/research-materialized")
    materialize.set_defaults(func=_cmd_materialize)

    status = subparsers.add_parser("status", help="transition variant status")
    status.add_argument("--strategy-dir")
    status.add_argument("--strategy")
    status.add_argument("--strategies-root", default="strategies")
    status.add_argument("--variant-id", required=True)
    status.add_argument("--status", required=True)
    status.add_argument("--yes", action="store_true")
    status.set_defaults(func=_cmd_status)

    branch_plan = subparsers.add_parser("branch-plan", help="print a structural variant branch plan")
    branch_plan.add_argument("--repo-root", default=".")
    branch_plan.add_argument("--strategy")
    branch_plan.add_argument("--strategies-root", default="strategies")
    branch_plan.add_argument("--variant-id", required=True)
    branch_plan.add_argument("--branch-name")
    branch_plan.add_argument("--base-ref", default="HEAD")
    branch_plan.set_defaults(func=_cmd_branch_plan)

    branch_create = subparsers.add_parser("branch-create", help="create a structural variant branch after authorization")
    branch_create.add_argument("--repo-root", default=".")
    branch_create.add_argument("--strategy")
    branch_create.add_argument("--strategies-root", default="strategies")
    branch_create.add_argument("--variant-id", required=True)
    branch_create.add_argument("--branch-name")
    branch_create.add_argument("--base-ref", default="HEAD")
    branch_create.add_argument("--yes", action="store_true")
    branch_create.set_defaults(func=_cmd_branch_create)

    merge_plan = subparsers.add_parser("merge-plan", help="print a structural variant merge plan")
    merge_plan.add_argument("--repo-root", default=".")
    merge_plan.add_argument("--source-ref")
    merge_plan.add_argument("--strategy-dir")
    merge_plan.add_argument("--strategy")
    merge_plan.add_argument("--strategies-root", default="strategies")
    merge_plan.add_argument("--variant-id")
    merge_plan.add_argument("--target-ref", default="HEAD")
    merge_plan.set_defaults(func=_cmd_merge_plan)

    merge_apply = subparsers.add_parser("merge-apply", help="merge a structural variant after authorization")
    merge_apply.add_argument("--repo-root", default=".")
    merge_apply.add_argument("--source-ref")
    merge_apply.add_argument("--strategy-dir")
    merge_apply.add_argument("--strategy")
    merge_apply.add_argument("--strategies-root", default="strategies")
    merge_apply.add_argument("--variant-id")
    merge_apply.add_argument("--target-ref", default="HEAD")
    merge_apply.add_argument("--yes", action="store_true")
    merge_apply.set_defaults(func=_cmd_merge_apply)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
