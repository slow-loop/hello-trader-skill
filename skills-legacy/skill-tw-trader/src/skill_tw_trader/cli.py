from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import yaml

from skill_tw_trader.core.market_data.symbols import normalize_symbol
from skill_tw_trader.core.market_service import build_market_report, save_briefing
from skill_tw_trader.core.trading_engine import (
    DEFAULT_INITIAL_CASH,
    build_status,
    execute_order,
    get_trade_history,
    initialize_ledger,
    record_daily_snapshot,
    update_orders,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m skill_tw_trader.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    market_parser = subparsers.add_parser("market", help="Show market overview or stock analysis")
    market_parser.add_argument("symbols", nargs="*", help="Ticker symbols, e.g. 2330 or AAPL")

    account_parser = subparsers.add_parser("account", aliases=["status"], help="Show account status")
    account_parser.set_defaults(command_name="account")

    buy_parser = subparsers.add_parser("buy", help="Execute a buy order")
    _add_trade_args(buy_parser, require_price=False)

    sell_parser = subparsers.add_parser("sell", help="Execute a sell order")
    _add_trade_args(sell_parser, require_price=True)

    exit_parser = subparsers.add_parser("set-exit", aliases=["update"], help="Update stop-loss / take-profit")
    exit_parser.add_argument("symbol")
    exit_parser.add_argument("--stop-loss", dest="stop_loss", type=float)
    exit_parser.add_argument("--take-profit", dest="take_profit", type=float)
    exit_parser.set_defaults(command_name="set-exit")

    history_parser = subparsers.add_parser("history", help="Show recent trade history")
    history_parser.add_argument("--days", type=int, default=7)

    snapshot_parser = subparsers.add_parser("snapshot", help="Record daily equity snapshot")
    snapshot_parser.add_argument("--date", dest="snapshot_date")

    screener_parser = subparsers.add_parser("screener", help="Run quantitative screener")
    screener_parser.add_argument("--strategy", default="momentum", help="Screening strategy (e.g., momentum)")
    screener_parser.add_argument("--limit", type=int, default=30, help="Number of results to show")
    screener_parser.add_argument("--no-enrich", dest="no_enrich", action="store_true", help="Skip technical/chips enrichment (faster)")

    init_parser = subparsers.add_parser("init", help="Initialize paper-trading ledger")
    init_parser.add_argument("--cash", type=float, default=DEFAULT_INITIAL_CASH)
    init_parser.add_argument("--force", action="store_true")

    research_parser = subparsers.add_parser("research", help="Manage research documents")
    research_subparsers = research_parser.add_subparsers(dest="research_command", required=True)
    research_init_parser = research_subparsers.add_parser("init", help="Initialize a new research file")
    research_init_parser.add_argument("symbol", help="Ticker symbol, e.g. 3715.TW")

    subparsers.add_parser("check-triggers", help="Evaluate watchlist trigger/invalidation conditions")

    perf_parser = subparsers.add_parser("performance", help="Show trade performance by strategy or tags")
    perf_parser.add_argument("--by", choices=["strategy", "tags"], default="strategy", help="Group by strategy or tags")

    recall_parser = subparsers.add_parser("recall", help="Find similar past trades for a symbol")
    recall_parser.add_argument("symbol", help="Ticker symbol to compare")
    recall_parser.add_argument("--top", type=int, default=5, help="Number of results")

    notify_parser = subparsers.add_parser("notify", help="Push an inbox message to Telegram")
    notify_parser.add_argument("file", nargs="?", help="Path to inbox yaml file")
    notify_parser.add_argument("--agent", default="trading")
    notify_parser.add_argument("--action", default="update")
    notify_parser.add_argument("--summary", help="Inline summary text (used if no file given)")

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

    if command == "account":
        print(_dump_yaml(build_status()))
        return 0

    if command == "buy":
        snapshot = _auto_snapshot(args.symbol)
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
                market_snapshot=snapshot,
            )
        )
        return 0

    if command == "sell":
        snapshot = _auto_snapshot(args.symbol)
        tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
        print(
            execute_order(
                symbol=args.symbol,
                side="SELL",
                qty=args.qty,
                price=args.price,
                stop_loss=args.stop_loss,
                take_profit=args.take_profit,
                reason=args.reason or "",
                strategy=args.strategy,
                tags=tags,
                confidence=args.confidence,
                market_snapshot=snapshot,
            )
        )
        return 0

    if command == "set-exit":
        print(update_orders(args.symbol, stop_loss=args.stop_loss, take_profit=args.take_profit))
        return 0

    if command == "history":
        print(get_trade_history(days=args.days))
        return 0

    if command == "snapshot":
        print(record_daily_snapshot(snapshot_date=args.snapshot_date))
        return 0

    if command == "screener":
        from skill_tw_trader.core.screener import run_momentum_screener
        from skill_tw_trader.core.account_paths import WATCHLIST_FILE

        watchlist_symbols = set()
        if WATCHLIST_FILE.exists():
            with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
                wl = yaml.safe_load(f) or []
                watchlist_symbols = {normalize_symbol(item["symbol"]) for item in wl if "symbol" in item}

        if getattr(args, "strategy", "momentum") == "momentum":
            limit = getattr(args, "limit", 30)
            no_enrich = getattr(args, "no_enrich", False)
            results = run_momentum_screener(limit=limit, enrich=not no_enrich)
            print(f"=== TWSE Momentum Screener (Top {len(results)} by Value) ===")
            header = (
                f"{'#':<3} {'Symbol':<8} {'Name':<8} {'Close':<8} {'Chg%':<7} "
                f"{'Value(M)':<10} {'RSI':<6} {'ADX':<6} {'Vol.R':<6} "
                f"{'Foreign':<9} {'Trust':<8} {'Margin':<8} {'W'}"
            )
            print(header)
            print("-" * len(header))
            for idx, r in enumerate(results, 1):
                normalized = normalize_symbol(r.symbol)
                in_wl = "Y" if normalized in watchlist_symbols else "-"
                rsi = f"{r.rsi_14:.0f}" if r.rsi_14 is not None else "-"
                adx = f"{r.adx_14:.0f}" if r.adx_14 is not None else "-"
                vol_r = f"{r.volume_ratio_20:.1f}" if r.volume_ratio_20 is not None else "-"
                fn = f"{r.foreign_net_days:+d}d" if r.foreign_net_days else "-"
                tn = f"{r.trust_net_days:+d}d" if r.trust_net_days else "-"
                mg = r.margin_trend[:4] if r.margin_trend else "-"
                print(
                    f"{idx:<3} {r.symbol:<8} {r.name:<8} {r.close:<8.2f} "
                    f"{'+' if r.change_pct > 0 else ''}{r.change_pct:<6.2f} "
                    f"{r.trade_value:>9,.0f} {rsi:>5} {adx:>5} {vol_r:>5} "
                    f"{fn:>8} {tn:>7} {mg:>7} {in_wl}"
                )
            # Print triggered expressions summary for enriched results
            triggered = [(r.symbol, r.triggers) for r in results if r.triggers]
            if triggered:
                print(f"\n--- Triggered Expressions ---")
                for sym, trigs in triggered:
                    print(f"  {sym}: {', '.join(trigs[:8])}")
        else:
            print(f"Strategy {args.strategy} not implemented.")
        return 0

    if command == "research":
        if args.research_command == "init":
            from skill_tw_trader.core.research_engine import init_research_file
            path = init_research_file(args.symbol)
            print(f"Initialized research file: {path}")
            return 0
        return 0

    if command == "init":
        print(initialize_ledger(initial_cash=args.cash, force=args.force))
        return 0

    if command == "performance":
        from skill_tw_trader.core.trade_memory import compute_performance
        import json as _json

        ledger_path = __import__("skill_tw_trader.core.account_paths", fromlist=["LEDGER_FILE"]).LEDGER_FILE
        if not ledger_path.exists():
            print("No ledger found. Run 'init' first.")
            return 1
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger_data = _json.load(f)
        history = ledger_data.get("trade_history", [])
        perf = compute_performance(history, group_by=args.by)
        if not perf:
            print(f"No completed sell trades found to analyze.")
            return 0
        print(f"=== Performance by {args.by} ===\n")
        for key, stats in sorted(perf.items(), key=lambda x: x[1]["total_pnl"], reverse=True):
            pnl_r_str = f", avg R={stats['avg_pnl_r']}" if stats.get("avg_pnl_r") is not None else ""
            print(
                f"  {key}: {stats['trades']} trades, "
                f"win {stats['win_rate']:.0%} ({stats['wins']}W/{stats['losses']}L), "
                f"PnL={stats['total_pnl']:+,.0f}{pnl_r_str}"
            )
            print(f"    avg={stats['avg_pnl']:+,.0f}, best={stats['best_trade']:+,.0f}, worst={stats['worst_trade']:+,.0f}")
        return 0

    if command == "recall":
        from skill_tw_trader.core.trade_memory import build_trade_snapshot, recall_similar_trades
        import json as _json

        ledger_path = __import__("skill_tw_trader.core.account_paths", fromlist=["LEDGER_FILE"]).LEDGER_FILE
        if not ledger_path.exists():
            print("No ledger found.")
            return 1
        with open(ledger_path, "r", encoding="utf-8") as f:
            ledger_data = _json.load(f)
        history = ledger_data.get("trade_history", [])
        snapshot = build_trade_snapshot(args.symbol)
        similar = recall_similar_trades(snapshot, history, top_k=args.top)
        if not similar:
            print(f"No past trades with market_snapshot found for comparison.")
            return 0
        print(f"=== Similar Past Trades for {args.symbol} ===\n")
        for i, t in enumerate(similar, 1):
            pnl_str = f"PnL={t.get('pnl', '?'):+,.0f}" if "pnl" in t else ""
            r_str = f" ({t['pnl_r']:+.1f}R)" if "pnl_r" in t else ""
            tags_str = f" [{','.join(t.get('tags', []))}]" if t.get("tags") else ""
            print(
                f"  {i}. {t['symbol']} {t['action']} @ {t['price']:.0f} "
                f"{pnl_str}{r_str}{tags_str} "
                f"(dist={t['similarity_distance']:.3f})"
            )
            if t.get("reason"):
                print(f"     reason: {t['reason'][:80]}")
        return 0

    if command == "check-triggers":
        from skill_tw_trader.core.watchlist_checker import check_watchlist_triggers

        results = check_watchlist_triggers()
        if not results:
            print("No watchlist items with trigger_conditions or invalidation_conditions.")
            return 0
        print("=== Watchlist Trigger Check ===\n")
        for r in results:
            sym = r["symbol"]
            status = r["status"]
            trig = "TRIGGERED" if r["trigger_met"] else "not met"
            inv = "INVALIDATED" if r["invalidation_met"] else "ok"
            print(f"  {sym} ({status})  trigger: {trig}  invalidation: {inv}")
            snap = r.get("context_snapshot", {})
            if snap:
                parts = [f"{k}={v}" for k, v in snap.items()]
                print(f"    snapshot: {', '.join(parts)}")
            for tr in r.get("trigger_results", []):
                mark = "✓" if tr["result"] else "✗"
                err = f" ({tr['error']})" if tr.get("error") else ""
                print(f"    trigger  {mark} {tr['expr']}{err}")
            for ir in r.get("invalidation_results", []):
                mark = "!" if ir["result"] else "ok"
                err = f" ({ir['error']})" if ir.get("error") else ""
                print(f"    invalid  {mark} {ir['expr']}{err}")
            if r.get("error"):
                print(f"    ERROR: {r['error']}")
            print()
        return 0

    if command == "notify":
        return _cmd_notify(args)

    parser.error(f"Unknown command: {command}")
    return 2


def _add_trade_args(parser: argparse.ArgumentParser, *, require_price: bool) -> None:
    parser.add_argument("symbol")
    parser.add_argument("--qty", type=int, required=True)
    parser.add_argument("--price", type=float, required=require_price)
    parser.add_argument("--stop-loss", dest="stop_loss", type=float)
    parser.add_argument("--take-profit", dest="take_profit", type=float)
    parser.add_argument("--reason")
    parser.add_argument("--strategy", default="", help="Strategy tag (e.g. momentum)")
    parser.add_argument("--tags", default="", help="Comma-separated theme tags (e.g. satellite,leo)")
    parser.add_argument("--confidence", type=float, help="Entry confidence 0.0-1.0")


def _auto_snapshot(symbol: str) -> dict | None:
    """Try to build a trade snapshot; return None on failure."""
    try:
        from skill_tw_trader.core.trade_memory import build_trade_snapshot
        return build_trade_snapshot(symbol)
    except Exception:
        return None


def _cmd_notify(args) -> int:
    from skill_tw_trader.messaging.telegram import push

    if args.file:
        inbox_path = Path(args.file)
        data = yaml.safe_load(inbox_path.read_text(encoding="utf-8")) or {}
    else:
        # Build inbox entry inline and save it
        now = datetime.now()
        data = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "agent": args.agent,
            "action": args.action,
            "summary": args.summary or "",
        }
        inbox_dir = Path(__file__).resolve().parents[2] / "data" / "inbox"
        inbox_dir.mkdir(parents=True, exist_ok=True)
        fname = inbox_dir / f"{now.strftime('%Y-%m-%d-%H%M')}.yaml"
        fname.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")
        print(f"Saved: {fname}")

    text = _format_inbox_message(data)
    result = push(text)
    print(result)
    return 0 if result.get("ok") else 1


def _format_inbox_message(data: dict) -> str:
    ts = data.get("timestamp", "")
    agent = data.get("agent", "")
    action = data.get("action", "")
    summary = data.get("summary", "").strip()
    return f"*[{agent}/{action}]* `{ts}`\n\n{summary}"


def _dump_yaml(data: dict) -> str:
    return yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    raise SystemExit(main())
