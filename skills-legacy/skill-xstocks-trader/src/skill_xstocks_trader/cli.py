from __future__ import annotations

import argparse
from datetime import datetime

import yaml

from skill_xstocks_trader.core.market_service import build_market_report, build_overview, save_briefing
from skill_xstocks_trader.core.trading_engine import (
    DEFAULT_INITIAL_CASH,
    build_status,
    execute_order,
    get_trade_history,
    initialize_ledger,
    record_daily_snapshot,
    update_orders,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m skill_xstocks_trader.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Market overview or per-symbol analysis
    market_parser = subparsers.add_parser("market", help="Show market overview or stock analysis")
    market_parser.add_argument("symbols", nargs="*", help="Trading pairs, e.g. AAPL/USDC TSLA/USDC")

    # SPY/QQQ regime
    subparsers.add_parser("regime", help="Show SPY/QQQ macro regime status")

    # Account status
    account_parser = subparsers.add_parser("account", aliases=["status"], help="Show account status")
    account_parser.set_defaults(command_name="account")

    # Buy
    buy_parser = subparsers.add_parser("buy", help="Execute a buy order")
    _add_trade_args(buy_parser)

    # Sell
    sell_parser = subparsers.add_parser("sell", help="Execute a sell order")
    _add_trade_args(sell_parser)

    # Update stop-loss / take-profit
    exit_parser = subparsers.add_parser("set-exit", aliases=["update"], help="Update stop-loss / take-profit")
    exit_parser.add_argument("symbol")
    exit_parser.add_argument("--stop-loss", dest="stop_loss", type=float)
    exit_parser.add_argument("--take-profit", dest="take_profit", type=float)
    exit_parser.set_defaults(command_name="set-exit")

    # Trade history
    history_parser = subparsers.add_parser("history", help="Show recent trade history")
    history_parser.add_argument("--days", type=int, default=7)

    # Daily snapshot
    snapshot_parser = subparsers.add_parser("snapshot", help="Record daily equity snapshot")
    snapshot_parser.add_argument("--date", dest="snapshot_date")

    # Initialize
    init_parser = subparsers.add_parser("init", help="Initialize paper-trading ledger")
    init_parser.add_argument("--cash", type=float, default=DEFAULT_INITIAL_CASH)
    init_parser.add_argument("--force", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command_name", args.command)

    if command == "market":
        report = build_market_report(args.symbols)
        print(_dump_yaml(report))
        save_briefing(report, symbols=args.symbols)
        return 0

    if command == "regime":
        overview = build_overview()
        print(_dump_yaml(overview))
        return 0

    if command == "account":
        print(_dump_yaml(build_status()))
        return 0

    if command == "buy":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        print(
            execute_order(
                symbol=args.symbol,
                side="BUY",
                qty=args.qty,
                price=args.price,
                stop_loss=args.stop_loss,
                take_profit=args.take_profit,
                reason=args.reason or "",
                strategy=args.strategy,
                tags=tags,
                confidence=args.confidence,
            )
        )
        return 0

    if command == "sell":
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        print(
            execute_order(
                symbol=args.symbol,
                side="SELL",
                qty=args.qty,
                price=args.price,
                reason=args.reason or "",
                strategy=args.strategy,
                tags=tags,
                confidence=args.confidence,
            )
        )
        return 0

    if command == "set-exit":
        print(update_orders(args.symbol, stop_loss=args.stop_loss, take_profit=args.take_profit))
        return 0

    if command == "history":
        history = get_trade_history(days=args.days)
        print(_dump_yaml(history))
        return 0

    if command == "snapshot":
        print(record_daily_snapshot(snapshot_date=args.snapshot_date))
        return 0

    if command == "init":
        print(initialize_ledger(initial_cash=args.cash, force=args.force))
        return 0

    parser.error(f"Unknown command: {command}")
    return 2


def _add_trade_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("symbol")
    parser.add_argument("--qty", type=float, required=True)
    parser.add_argument("--price", type=float, help="Fill price (auto-fetch if omitted)")
    parser.add_argument("--stop-loss", dest="stop_loss", type=float)
    parser.add_argument("--take-profit", dest="take_profit", type=float)
    parser.add_argument("--reason")
    parser.add_argument("--strategy", default="", help="Strategy tag (e.g. mean_reversion)")
    parser.add_argument("--tags", default="", help="Comma-separated theme tags (e.g. tech,oversold)")
    parser.add_argument("--confidence", type=float, help="Entry confidence 0.0-1.0")


def _dump_yaml(data) -> str:
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    raise SystemExit(main())
