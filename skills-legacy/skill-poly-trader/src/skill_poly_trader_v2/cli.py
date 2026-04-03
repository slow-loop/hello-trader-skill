from __future__ import annotations

import argparse

from skill_poly_trader_v2.engine import (
    build_market_report,
    build_markets_report,
    build_status,
    buy_position,
    initialize_ledger,
    sell_position,
    snapshot_equity,
    sync_tags,
)
from skill_poly_trader_v2.profiles import list_profile_names
from skill_poly_trader_v2.yaml_output import dump_yaml


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m skill_poly_trader_v2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize the v2 paper ledger")
    init_parser.add_argument("--cash", type=float, default=10_000.0)
    init_parser.add_argument("--force", action="store_true")

    subparsers.add_parser("sync-tags", help="Fetch tags into local data/tags.json for slug->id resolution")

    markets_parser = subparsers.add_parser("markets", help="Fetch filtered candidate markets for agent review")
    markets_parser.add_argument("--limit", type=int, default=None)
    markets_parser.add_argument("--profile", choices=list_profile_names(), default="all")
    markets_parser.add_argument("--verbose", action="store_true")

    market_parser = subparsers.add_parser("market", help="Fetch one market with fuller details")
    market_parser.add_argument("--slug", required=True)

    buy_parser = subparsers.add_parser("buy", help="Buy one binary outcome by outcome index")
    buy_parser.add_argument("--slug", required=True)
    buy_parser.add_argument("--outcome-index", required=True, type=int)
    buy_parser.add_argument("--probability", type=float, default=None)
    buy_parser.add_argument("--size", type=float, default=25.0)
    buy_parser.add_argument("--reason", default="Agent judged from external research")
    buy_parser.add_argument("--dry-run", action="store_true")

    sell_parser = subparsers.add_parser("sell", help="Manually exit an open position at current market price")
    sell_parser.add_argument("--slug", required=True)
    sell_parser.add_argument("--reason", default="Thesis changed")

    subparsers.add_parser("equity", help="Snapshot current equity curve point")
    subparsers.add_parser("status", help="Show v2 ledger status and auto-settle resolved positions when possible")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        print(initialize_ledger(initial_cash=args.cash, force=args.force))
        return 0

    if args.command == "sync-tags":
        print(dump_yaml(sync_tags()))
        return 0

    if args.command == "markets":
        report = build_markets_report(limit=args.limit, profile_name=args.profile)
        if not args.verbose:
            report = _compact_markets_report(report)
        print(dump_yaml(report))
        return 0

    if args.command == "market":
        try:
            result = build_market_report(slug=args.slug)
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")
        print(dump_yaml(result))
        return 0

    if args.command == "buy":
        try:
            result = buy_position(
                slug=args.slug,
                outcome_index=args.outcome_index,
                probability=args.probability,
                size=args.size,
                reason=args.reason,
                dry_run=args.dry_run,
            )
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")
        print(dump_yaml(result))
        return 0

    if args.command == "sell":
        try:
            result = sell_position(slug=args.slug, reason=args.reason)
        except RuntimeError as exc:
            parser.exit(1, f"{exc}\n")
        print(dump_yaml(result))
        return 0

    if args.command == "equity":
        print(dump_yaml(snapshot_equity()))
        return 0

    if args.command == "status":
        print(dump_yaml(build_status()))
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


def _compact_markets_report(report: dict[str, object]) -> dict[str, object]:
    markets = report.get("markets", [])
    compact_markets = [_compact_market(market) for market in markets if isinstance(market, dict)]
    return {
        "profile": report.get("profile"),
        "limit": report.get("limit"),
        "count": report.get("count"),
        "markets": compact_markets,
    }


def _compact_market(market: dict[str, object]) -> dict[str, object]:
    compact: dict[str, object] = {
        "question": market.get("question"),
        "slug": market.get("slug"),
        "outcomes": market.get("outcomes"),
        "outcomePrices": market.get("outcomePrices"),
        "endDate": market.get("endDate"),
        "createdAt": market.get("createdAt"),
        "updatedAt": market.get("updatedAt"),
        "volume24hr": market.get("volume24hr"),
        "liquidity": market.get("liquidity"),
        "daysToResolution": market.get("daysToResolution"),
        "eventTitle": market.get("eventTitle"),
        "sourceQuery": market.get("sourceQuery"),
    }
    family_market = market.get("familyMarket")
    if family_market:
        compact["familyMarket"] = family_market
    price_extreme = market.get("priceExtreme")
    if price_extreme is not None:
        compact["priceExtreme"] = price_extreme
    return compact
