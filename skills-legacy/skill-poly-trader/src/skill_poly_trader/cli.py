from __future__ import annotations

import argparse
import json

from skill_poly_trader.engine import build_scan_report, build_status, close_position, initialize_ledger, record_agent_decision, run_cycle, snapshot_equity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m skill_poly_trader.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the paper ledger")
    init_parser.add_argument("--cash", type=float, default=10_000.0)
    init_parser.add_argument("--force", action="store_true")

    run_parser = subparsers.add_parser("run", help="Run one paper-trading cycle")
    run_parser.add_argument("--limit", type=int, default=12)
    run_parser.add_argument("--candidates", type=int, default=6)
    run_parser.add_argument("--paper-size", type=float, default=25.0)
    run_parser.add_argument("--dry-run", action="store_true")

    scan_parser = subparsers.add_parser("scan", help="Fetch candidate market snapshots for manual review")
    scan_parser.add_argument("--limit", type=int, default=12)
    scan_parser.add_argument("--candidates", type=int, default=6)

    record_parser = subparsers.add_parser("record", help="Record an agent-made paper decision")
    record_parser.add_argument("--slug", required=True)
    record_parser.add_argument("--model-yes", type=float, required=True)
    record_parser.add_argument("--paper-size", type=float, default=25.0)
    record_parser.add_argument("--reason", default="Agent judged from market snapshot")
    record_parser.add_argument("--dry-run", action="store_true")

    close_parser = subparsers.add_parser("close", help="Close a position (market resolved or manual sell)")
    close_parser.add_argument("--slug", required=True)
    close_parser.add_argument("--outcome", required=True, choices=["YES", "NO", "SELL"],
                              help="YES/NO = market resolved, SELL = exit at current price")

    subparsers.add_parser("equity", help="Snapshot current equity curve point")

    subparsers.add_parser("status", help="Show ledger status")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        print(initialize_ledger(initial_cash=args.cash, force=args.force))
        return 0

    if args.command == "run":
        try:
            result = run_cycle(
                limit=args.limit,
                candidate_count=args.candidates,
                paper_size=args.paper_size,
                dry_run=args.dry_run,
            )
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")
        print(_dump_json(result))
        return 0

    if args.command == "scan":
        print(_dump_json(build_scan_report(limit=args.limit, candidate_count=args.candidates)))
        return 0

    if args.command == "record":
        try:
            result = record_agent_decision(
                slug=args.slug,
                model_yes=args.model_yes,
                paper_size=args.paper_size,
                reason=args.reason,
                dry_run=args.dry_run,
            )
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")
        print(_dump_json(result))
        return 0

    if args.command == "close":
        try:
            result = close_position(slug=args.slug, outcome=args.outcome)
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")
        print(_dump_json(result))
        return 0

    if args.command == "equity":
        result = snapshot_equity()
        print(_dump_json(result))
        return 0

    if args.command == "status":
        print(_dump_json(build_status()))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _dump_json(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(main())
