"""Lana-copycat CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = typer.Typer(help="Lana-copycat: Square sentiment + OI momentum trader")
console = Console()

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text())
    return {}


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # Quiet down noisy libs — keep our own loggers at INFO
    for name in ("httpx", "httpcore", "urllib3", "websockets",
                 "binance", "lana_copycat.trader"):
        logging.getLogger(name).setLevel(logging.WARNING)


# ── scan ──────────────────────────────────────────────────────────────────────

def _load_square_from_cache(dump_dir: Path, ttl_minutes: int) -> dict[str, int] | None:
    """Read all JSONL files newer than ttl_minutes and return merged ticker counts.
    Returns None if no fresh cache exists."""
    from .scrapers.square import _parse_vos, _count_tickers
    import time

    cutoff = time.time() - ttl_minutes * 60
    files = [f for f in sorted(dump_dir.glob("*.jsonl")) if f.stat().st_mtime >= cutoff]
    if not files:
        return None

    vos, seen = [], set()
    for f in files:
        for line in f.read_text().splitlines():
            raw = json.loads(line)
            pid = str(raw.get("id", ""))
            if pid and pid not in seen:
                seen.add(pid)
                vos.append(raw)

    posts = _parse_vos(vos)
    counts = _count_tickers(posts)
    console.print(f"[dim]Cache: {len(posts)} posts from {len(files)} file(s)[/]")
    return counts


@app.command()
def scan(
    top_n: int = typer.Option(5, help="Top candidates to return"),
    dry_run: bool = typer.Option(True, help="Score only, no trades"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON"),
    square_posts: int = typer.Option(200, help="Max Square posts to scrape"),
    profile_dir: str = typer.Option("", "--profile-dir", help="Persist Chrome profile dir"),
    dump_dir: str = typer.Option("data/square", "--dump-dir", help="Square JSONL cache dir"),
    cache_ttl: int = typer.Option(60, "--cache-ttl", help="Cache TTL in minutes (0 = always scrape fresh)"),
) -> None:
    """Full scan: Square (→ cache → CoinGecko fallback) + OI → score → (optionally) trade."""
    _setup_logging()
    cfg = _load_config()

    async def _run() -> list[dict]:
        from .scrapers.square import scrape_square
        from .scrapers.coingecko import get_trending_counts
        from .signals.binance_market import get_market_signals
        from .scoring import score_candidates

        trending_counts: dict[str, int] = {}
        ddir = Path(dump_dir) if dump_dir else None

        # Try cache first
        if ddir and cache_ttl > 0:
            cached = _load_square_from_cache(ddir, cache_ttl)
            if cached is not None:
                trending_counts = cached
                console.print(f"[dim]Square: using cache ({len(trending_counts)} tickers)[/]")

        # Cache miss → scrape fresh
        if not trending_counts:
            try:
                console.print("[bold cyan]Fetching Binance Square (live)...[/]")
                pdir = Path(profile_dir) if profile_dir else None
                snapshot = await scrape_square(
                    max_posts=square_posts,
                    profile_dir=pdir,
                    dump_dir=ddir,
                )
                trending_counts = snapshot.ticker_counts
                console.print(f"  Square tickers: {len(trending_counts)} (from {len(snapshot.posts)} posts)")
            except Exception as e:
                console.print(f"[yellow]Square failed ({e}), falling back to CoinGecko...[/]")
                trending_counts = await get_trending_counts()
                console.print(f"  CoinGecko tickers: {len(trending_counts)}")

        console.print("[bold cyan]Fetching market signals...[/]")
        signals_cfg = cfg.get("signals", {})
        market = await get_market_signals(
            top_n=signals_cfg.get("top_gainers_n", 20),
            oi_window_hours=signals_cfg.get("oi_window_hours", 48),
        )

        scoring_cfg = cfg.get("scoring", {})
        candidates = score_candidates(
            square_counts=trending_counts,
            market_signals=market,
            w_square=scoring_cfg.get("weight_square", 0.4),
            w_oi=scoring_cfg.get("weight_oi", 0.35),
            w_gainers=scoring_cfg.get("weight_gainers", 0.25),
            top_n=top_n,
        )
        return [c.to_dict() for c in candidates]

    results = asyncio.run(_run())

    if json_out:
        print(json.dumps(results, indent=2))
        return

    table = Table(title="Top Candidates", show_lines=True)
    table.add_column("#", style="dim")
    table.add_column("Symbol", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Trending", justify="right")
    table.add_column("OI Ratio", justify="right")
    table.add_column("24h %", justify="right")

    for i, c in enumerate(results, 1):
        table.add_row(
            str(i),
            c["symbol"],
            f"{c['score']:.3f}",
            f"{c['square_rank']:.2f}",
            f"{c['oi_ratio']:.1f}x",
            f"{c['price_change_pct']:+.1f}%",
        )
    console.print(table)

    if dry_run:
        console.print("[yellow]Dry run — no trades placed.[/]")
        return

    # trade top candidate
    top = results[0] if results else None
    if not top:
        console.print("[red]No candidates found.[/]")
        return

    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        console.print("[red]Set BINANCE_API_KEY and BINANCE_API_SECRET env vars to trade.[/]")
        return

    from .trader import BinanceTrader

    trader_cfg = cfg.get("trader", {})
    binance_cfg = cfg.get("binance", {})
    trader = BinanceTrader(
        api_key=api_key,
        api_secret=api_secret,
        testnet=binance_cfg.get("testnet", True),
        max_loss_usdt=trader_cfg.get("max_loss_usdt", 200.0),
        leverage=trader_cfg.get("leverage", 10),
    )
    result = trader.open_long(
        symbol=top["symbol"],
        position_size_pct=trader_cfg.get("position_size_pct", 0.05),
    )
    console.print(f"[green]Trade opened:[/] {json.dumps(result.to_dict(), indent=2)}")


# ── cattrade sub-app ──────────────────────────────────────────────────────────
#
# Pure-code pipeline. `lana cattrade run` is meant to be invoked by cron every
# few minutes — no LLM in the loop. Agent involvement (tuning, incident review)
# happens out-of-band via the journal.

cattrade_app = typer.Typer(help="Cattrade gsheet pipeline (pure code, no agent)")
app.add_typer(cattrade_app, name="cattrade")


def _load_cattrade_ctx(cfg: dict) -> tuple[str, dict]:
    """Return (sheet_id, merged_cattrade_cfg) or exit."""
    from .signals.cattrade import DEFAULT_CATTRADE_CFG
    cattrade_cfg = cfg.get("cattrade", {})
    sheet_id = os.environ.get("CATTRADE_SHEET_ID") or cattrade_cfg.get("sheet_id")
    if not sheet_id:
        console.print("[red]cattrade.sheet_id missing — set CATTRADE_SHEET_ID in .env or config.yaml[/]")
        raise typer.Exit(1)
    return sheet_id, {**DEFAULT_CATTRADE_CFG, **cattrade_cfg}


def _fetch_and_pick(sheet_id: str, merged_cfg: dict, timeout: int, include_symbols: set[str] | None = None):
    from .signals.cattrade import fetch_cattrade_xlsx, pick_cattrade
    _, rankings, _ = fetch_cattrade_xlsx(sheet_id, timeout_sec=timeout)
    return pick_cattrade(rankings, merged_cfg, include_symbols=include_symbols)


def _fetch_xlsx_and_pick(
    sheet_id: str, merged_cfg: dict, timeout: int, include_symbols: set[str] | None = None,
):
    """Fetch full XLSX workbook + run the picker off 排行榜快照.

    Returns (candidates, xlsx_bytes, snapshot_ts).
    """
    from .signals.cattrade import fetch_cattrade_xlsx, pick_cattrade
    xlsx_bytes, rankings, snapshot_ts = fetch_cattrade_xlsx(sheet_id, timeout_sec=timeout)
    cands = pick_cattrade(rankings, merged_cfg, include_symbols=include_symbols)
    return cands, xlsx_bytes, snapshot_ts


@cattrade_app.command("scan")
def cattrade_scan(
    top_n: int = typer.Option(10, help="Top candidates to return"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show cattrade top candidates (read-only, no trading)."""
    _setup_logging()
    cfg = _load_config()
    sheet_id, merged = _load_cattrade_ctx(cfg)

    console.print("[bold cyan]Fetching cattrade sheet...[/]")
    try:
        cands = _fetch_and_pick(sheet_id, merged, cfg.get("cattrade", {}).get("fetch_timeout_sec", 15))[:top_n]
    except Exception as e:
        console.print(f"[red]cattrade fetch failed: {e}[/]")
        raise typer.Exit(1)

    if json_out:
        print(json.dumps([{
            "symbol": c.symbol, "score": c.score, "patterns": c.patterns,
            "oi_usdt": c.oi_usdt, "reasons": c.reasons,
        } for c in cands], ensure_ascii=False, indent=2))
        return

    table = Table(title=f"Cattrade Candidates (top {top_n})", show_lines=True)
    table.add_column("#", style="dim")
    table.add_column("Sym", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Patterns")
    table.add_column("OI", justify="right")
    table.add_column("Reasons")
    for i, c in enumerate(cands, 1):
        table.add_row(
            str(i), c.symbol, f"{c.score:.2f}",
            ",".join(c.patterns) or "-",
            f"{c.oi_usdt/1_000_000:.1f}M",
            "; ".join(c.reasons),
        )
    console.print(table)


@cattrade_app.command("journal")
def cattrade_journal(
    symbol: str = typer.Option("", help="Filter by symbol (e.g. ATUSDT)"),
    n: int = typer.Option(20, help="Show last N entries"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show cattrade trading journal entries (opens / partial closes / closes)."""
    from . import cattrade_journal as journal
    entries = journal.read_all()
    if symbol:
        entries = [e for e in entries if e.get("symbol") == symbol.upper()]
    entries = entries[-n:]

    if json_out:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return

    if not entries:
        console.print("[dim]Journal is empty.[/]")
        return

    table = Table(title=f"Cattrade Journal (last {len(entries)})", show_lines=False)
    table.add_column("Time", style="dim")
    table.add_column("Event")
    table.add_column("Sym", style="bold")
    table.add_column("Qty", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Detail")
    for e in entries:
        detail = ""
        if e.get("event") == "open":
            ct = e.get("cattrade", {})
            detail = f"score={ct.get('score')} str={ct.get('strength')} conc={ct.get('concentration')}"
        elif e.get("event") == "partial_close":
            detail = f"conv={e.get('conviction'):.2f} {e.get('reason','')}"
        elif e.get("event") == "close":
            detail = e.get("reason", "")
        table.add_row(
            e.get("ts", "")[:19],
            e.get("event", ""),
            e.get("symbol", ""),
            str(e.get("qty", "")),
            str(e.get("price", e.get("entry_price", ""))),
            detail,
        )
    console.print(table)


def _cattrade_run_once(cfg: dict, dry_run: bool) -> dict:
    """Core tick logic. Returns a structured result; never raises typer.Exit.

    On failure returns {"error": "...", "decisions": []} so a daemon can keep going.
    """
    sheet_id, merged = _load_cattrade_ctx(cfg)
    cattrade_cfg = cfg.get("cattrade", {})
    run_cfg = cattrade_cfg.get("run", {})

    min_entry_score = run_cfg.get("min_entry_score", 15.0)
    min_conviction_healthy = run_cfg.get("min_conviction_healthy", 0.95)
    max_close_pct = run_cfg.get("max_close_pct_per_run", 0.10)
    min_close_pct = run_cfg.get("min_close_pct", 0.02)
    absent_streak_threshold = int(run_cfg.get("absent_streak_threshold", 3))
    absent_trim_pct = float(run_cfg.get("absent_trim_pct", 0.05))
    time_stop_hours = float(run_cfg.get("time_stop_hours", 0))
    multi_position = bool(run_cfg.get("multi_position", False))
    max_positions = int(run_cfg.get("max_positions", 5))

    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        return {"error": "missing BINANCE_API_KEY / BINANCE_API_SECRET", "decisions": []}

    from binance.client import Client
    binance_cfg = cfg.get("binance", {})
    testnet = binance_cfg.get("testnet", True)
    client = Client(api_key, api_secret)
    if testnet:
        client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

    try:
        all_pos = client.futures_position_information()
    except Exception as e:
        return {"error": f"binance position fetch failed: {e}", "decisions": []}
    open_pos = [p for p in all_pos if float(p.get("positionAmt", 0)) != 0]

    # Include currently-held symbols so "weak signal" != "signal disappeared"
    held_bases = {p["symbol"].removesuffix("USDT") for p in open_pos}

    from . import cattrade_snapshot
    try:
        cands, xlsx_bytes, snapshot_ts = _fetch_xlsx_and_pick(
            sheet_id, merged, cattrade_cfg.get("fetch_timeout_sec", 15),
            include_symbols=held_bases,
        )
    except Exception as e:
        return {"error": f"cattrade fetch failed: {e}", "decisions": []}

    # Dedup: if the gsheet snapshot hasn't refreshed since last tick, skip.
    # All decisions (open/trim/close) are deterministic functions of the sheet,
    # so re-running on identical data only wastes Binance API calls.
    if snapshot_ts and cattrade_snapshot.exists(snapshot_ts):
        return {
            "snapshot_ts": snapshot_ts,
            "decisions": [{"action": "skip_stale", "reason": "gsheet unchanged",
                           "snapshot_ts": snapshot_ts}],
        }
    if snapshot_ts:
        cattrade_snapshot.save(snapshot_ts, xlsx_bytes)

    cand_map = {c.symbol: c for c in cands}

    # Sheet summary for logging
    strong_cands = [c for c in cands if c.score > 0]
    sheet_top = [{"symbol": c.symbol, "score": c.score, "patterns": c.patterns} for c in strong_cands[:5]]
    sheet_weak_held = [{"symbol": c.symbol, "score": c.score, "patterns": c.patterns}
                       for c in cands if c.score <= 0 and c.symbol in held_bases]
    sheet_absent = [b for b in held_bases if b not in cand_map]

    decisions: list[dict] = []

    from . import cattrade_journal as journal
    from . import cattrade_state as state_mod

    state = state_mod.load()
    # Drop state for symbols no longer held (e.g. closed outside this daemon)
    held_syms = {p["symbol"] for p in open_pos}
    for sym in list(state.keys()):
        if sym not in held_syms:
            state_mod.drop(state, sym)

    # ── Branch A — consider new entries ──────────────────────────────────────
    # Single mode: only enter when flat (original Lana rule).
    # Multi mode:  enter any qualifying candidate not already held, up to max_positions.
    trader_cfg = cfg.get("trader", {})
    base_size_pct = trader_cfg.get("position_size_pct", 0.05)

    slots_free = max_positions - len(open_pos)
    entry_eligible = [
        c for c in strong_cands
        if c.score >= min_entry_score and f"{c.symbol}USDT" not in held_syms
    ]

    if multi_position:
        to_open = entry_eligible[:max(slots_free, 0)]
        # Scale size: divide by max_positions so total exposure stays constant
        scaled_size_pct = base_size_pct / max_positions
    else:
        # Original behaviour: only open if fully flat, and only top-1
        to_open = entry_eligible[:1] if not open_pos else []
        scaled_size_pct = base_size_pct

    if not to_open and not open_pos:
        top = strong_cands[0] if strong_cands else None
        decisions.append({"action": "skip_entry", "reason": f"no candidate >= {min_entry_score}",
                          "top": top.symbol if top else None,
                          "top_score": top.score if top else None})

    for cand in to_open:
        d: dict = {"action": "open", "symbol": cand.symbol, "score": cand.score,
                   "patterns": cand.patterns, "size_pct": round(scaled_size_pct, 4)}
        decisions.append(d)
        if not dry_run:
            from .trader import BinanceTrader
            trader = BinanceTrader(
                api_key=api_key, api_secret=api_secret, testnet=testnet,
                max_loss_usdt=trader_cfg.get("max_loss_usdt", 200.0),
                leverage=trader_cfg.get("leverage", 10),
            )
            symbol_usdt = f"{cand.symbol}USDT"
            result = trader.open_long(symbol_usdt, position_size_pct=scaled_size_pct)
            d["order_id"] = result.order_id
            d["entry_price"] = result.entry_price
            d["qty"] = result.quantity
            struct = cand.raw.get("structure", {})
            journal.write_open(
                symbol=symbol_usdt,
                qty=result.quantity,
                entry_price=result.entry_price,
                cattrade_score=cand.score,
                cattrade_strength=float(struct.get("结构强度", 0) or 0),
                cattrade_concentration=float(struct.get("大户集中度", 0) or 0),
                cattrade_patterns=cand.patterns,
                cattrade_oi_usdt=cand.oi_usdt,
            )

    # ── Branch B — reconcile each open position ───────────────────────────────
    # v2 model: every held position ALWAYS has a row in 排行榜快照 (since
    # include_symbols forces inclusion). So we never hit the "absent" edge —
    # conviction and label are always defined.
    for pos in open_pos:
        symbol_usdt = pos["symbol"]
        base = symbol_usdt.removesuffix("USDT")
        qty = abs(float(pos["positionAmt"]))
        mark = float(pos.get("markPrice") or 0)
        pnl = float(pos.get("unRealizedProfit") or 0)

        entry = journal.last_open(symbol_usdt)
        if not entry:
            decisions.append({"action": "skip_unmanaged", "symbol": symbol_usdt,
                              "reason": "no journal entry — not auto-managed"})
            continue

        current = cand_map.get(base)
        entry_score = entry["cattrade"]["score"]
        pos_ctx = {"qty": qty, "mark": mark, "pnl": round(pnl, 2), "entry_score": entry_score}

        # ── L1: time stop — held too long without profit
        if time_stop_hours > 0 and pnl <= 0:
            try:
                entry_dt = datetime.fromisoformat(entry.get("ts", ""))
                age_h = (datetime.now(timezone.utc) - entry_dt).total_seconds() / 3600
            except (ValueError, TypeError):
                age_h = 0.0
            if age_h >= time_stop_hours:
                d = {"action": "close_full", "symbol": symbol_usdt,
                     "reason": f"time stop ({age_h:.1f}h, pnl<=0)",
                     "current_score": current.score if current else None,
                     **pos_ctx}
                decisions.append(d)
                if not dry_run:
                    order = _close_full(client, symbol_usdt, qty)
                    d["order_id"] = str(order.get("orderId", ""))
                    journal.write_close(symbol_usdt, qty, mark, d["reason"])
                continue

        # current should never be None now — safety fallback
        if current is None:
            decisions.append({"action": "hold", "symbol": symbol_usdt,
                              "reason": "not found in rankings (unexpected)",
                              "current_score": None, "conviction": 0.0, **pos_ctx})
            continue

        # ── L2: explicit thesis reversal — 结构标签 turned bearish
        # Pattern D (大户领先做空) or SELL_LEAD (主动卖盘领先) → full close
        if "D" in current.patterns or "SELL_LEAD" in current.patterns:
            reason = f"label={current.label}"
            d = {"action": "close_full", "symbol": symbol_usdt,
                 "reason": reason, "current_score": current.score,
                 "current_label": current.label, **pos_ctx}
            decisions.append(d)
            if not dry_run:
                order = _close_full(client, symbol_usdt, qty)
                d["order_id"] = str(order.get("orderId", ""))
                journal.write_close(symbol_usdt, qty, mark, reason)
            continue

        # ── L3: conviction-based trim. conviction = current_综合分 / entry_综合分
        conviction = current.score / entry_score if entry_score > 0 else 1.0
        conv_ctx = {**pos_ctx, "current_score": current.score,
                    "current_label": current.label,
                    "conviction": round(conviction, 3)}
        if conviction >= min_conviction_healthy:
            decisions.append({"action": "hold", "symbol": symbol_usdt, **conv_ctx})
            continue

        target_qty = entry["qty"] * conviction
        delta = qty - target_qty
        if delta <= 0:
            decisions.append({"action": "hold", "symbol": symbol_usdt,
                              "reason": "already under target", **conv_ctx})
            continue
        n_pct = min(delta / qty, max_close_pct)
        if n_pct < min_close_pct:
            decisions.append({"action": "hold", "symbol": symbol_usdt,
                              "reason": f"delta {n_pct:.1%} below min {min_close_pct:.1%}",
                              **conv_ctx})
            continue

        close_qty = _round_qty(client, symbol_usdt, qty * n_pct)
        if close_qty <= 0:
            decisions.append({"action": "hold", "symbol": symbol_usdt,
                              "reason": "close qty rounded to 0", **conv_ctx})
            continue

        d = {"action": "partial_close", "symbol": symbol_usdt,
             "close_qty": close_qty, "pct": round(n_pct, 3), **conv_ctx}
        decisions.append(d)
        if not dry_run:
            order = _close_qty(client, symbol_usdt, close_qty)
            d["order_id"] = str(order.get("orderId", ""))
            journal.write_partial_close(
                symbol=symbol_usdt, qty=close_qty, price=mark,
                conviction=conviction,
                reason=f"score {entry_score:.2f}→{current.score:.2f} (conv={conviction:.2f})",
            )

    # absent_streak state no longer used — just clear it
    state_mod.save(state)

    return {"ts": datetime.now(timezone.utc).isoformat(), "dry_run": dry_run,
            "testnet": testnet, "decisions": decisions,
            "sheet_top": sheet_top, "sheet_weak_held": sheet_weak_held,
            "sheet_absent": sheet_absent, "open_pos_count": len(open_pos)}


def _action_style(action: str) -> str:
    return {
        "open":          "[green]OPEN[/]",
        "partial_close": "[yellow]TRIM[/]",
        "close_full":    "[red]CLOSE[/]",
        "hold":          "[dim]hold[/]",
        "skip_entry":    "[dim]skip[/]",
        "skip_stale":    "[dim]stale[/]",
        "skip_unmanaged": "[dim]unmanaged[/]",
    }.get(action, action)


def _print_run_result(out: dict, json_out: bool) -> None:
    if json_out:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if out.get("error"):
        console.print(f"[red]{out['error']}[/]")
        return

    mode = "[dim]testnet[/]" if out.get("testnet") else "[bold red]LIVE[/]"
    dr = " [yellow]DRY[/]" if out.get("dry_run") else ""
    snap = out.get("snapshot_ts") or ""
    snap_str = f"  [dim]snap={snap}[/]" if snap else ""
    console.print(f"[bold]cattrade run[/]  {mode}{dr}{snap_str}")

    decisions = out.get("decisions", [])

    # Stale: single-line short-circuit
    if any(d.get("action") == "skip_stale" for d in decisions):
        console.print("  [dim]gsheet unchanged — skipped[/]")
        return

    # ── Table 1: Sheet top candidates ────────────────────────────────────────
    sheet_top = out.get("sheet_top", [])
    t1 = Table(title="Sheet — top candidates", show_lines=False,
               title_style="bold cyan", title_justify="left")
    t1.add_column("#", style="dim", width=3)
    t1.add_column("Sym", style="bold")
    t1.add_column("Score", justify="right")
    t1.add_column("Patterns")
    if sheet_top:
        for i, c in enumerate(sheet_top, 1):
            pats = ",".join(c.get("patterns") or []) or "-"
            t1.add_row(str(i), c["symbol"], f"{c['score']:.1f}", pats)
    else:
        t1.add_row("-", "[dim]none[/]", "-", "-")
    console.print(t1)

    # ── Table 2: Portfolio + decisions ───────────────────────────────────────
    pos_actions = {"hold", "partial_close", "close_full", "open", "skip_unmanaged"}
    pos_decisions = [d for d in decisions if d.get("action") in pos_actions]

    t2 = Table(title="Portfolio", show_lines=False,
               title_style="bold cyan", title_justify="left")
    t2.add_column("Sym", style="bold")
    t2.add_column("Score", justify="right")   # entry→current
    t2.add_column("Conv", justify="right")
    t2.add_column("Qty", justify="right")
    t2.add_column("Mark", justify="right")
    t2.add_column("PnL", justify="right")
    t2.add_column("Action")
    t2.add_column("Detail", style="dim")

    total_pnl = 0.0
    held_count = 0

    for d in pos_decisions:
        action = d.get("action")
        sym = d.get("symbol", "")
        qty = d.get("qty", 0)
        mark = d.get("mark", 0)
        pnl = d.get("pnl", 0)
        entry_score = d.get("entry_score")
        cur_score = d.get("current_score")
        conviction = d.get("conviction")
        reason = d.get("reason", "")

        if action == "open":
            # New entry — no pos yet
            score_str = f"→{d.get('score', 0):.1f}"
            conv_str = "-"
            qty_str = f"{d.get('qty', '?')}"
            mark_str = f"{d.get('entry_price', 0):.4f}" if d.get("entry_price") else "-"
            pnl_str = "-"
            detail = ",".join(d.get("patterns") or []) or ""
            oid = d.get("order_id")
            if oid:
                detail = (detail + f"  oid={oid}").strip()
        else:
            held_count += 1
            total_pnl += pnl
            if entry_score is not None and cur_score is not None:
                score_str = f"{entry_score:.1f}→{cur_score:.1f}"
            elif entry_score is not None:
                score_str = f"{entry_score:.1f}→?"
            else:
                score_str = "-"
            conv_str = f"{conviction:.2f}" if conviction is not None else "-"
            qty_str = f"{qty}"
            mark_str = f"{mark:.4f}" if mark else "-"
            pnl_str = (f"[green]+{pnl:.2f}[/]" if pnl >= 0 else f"[red]{pnl:.2f}[/]")
            detail_parts: list[str] = []
            if d.get("current_label"):
                detail_parts.append(d["current_label"])
            if action == "partial_close":
                pct = d.get("pct", 0)
                detail_parts.append(f"close {pct:.0%}")
            if reason:
                detail_parts.append(reason)
            oid = d.get("order_id")
            if oid:
                detail_parts.append(f"oid={oid}")
            detail = "  ".join(detail_parts)

        t2.add_row(sym, score_str, conv_str, qty_str, mark_str, pnl_str,
                   _action_style(action), detail)

    # Skip_entry (no position, no candidate)
    for d in decisions:
        if d.get("action") != "skip_entry":
            continue
        top = d.get("top")
        ts = d.get("top_score")
        top_str = f"{top}({ts:.1f})" if top and ts is not None else "none"
        t2.add_row("-", "-", "-", "-", "-", "-",
                   _action_style("skip_entry"),
                   f"top={top_str}  {d.get('reason','')}")

    if pos_decisions or any(d.get("action") == "skip_entry" for d in decisions):
        console.print(t2)
    else:
        console.print("  [dim]no action[/]")

    # Summary line
    if held_count:
        pnl_fmt = (f"[green]+{total_pnl:.2f}[/]" if total_pnl >= 0
                   else f"[red]{total_pnl:.2f}[/]")
        console.print(f"[dim]── {held_count} open  PnL {pnl_fmt} USDT[/]")


@cattrade_app.command("run")
def cattrade_run(
    dry_run: bool = typer.Option(True, help="Simulate only (default). Use --no-dry-run to place real orders."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """One autonomous loop iteration — check positions, decide, execute."""
    _setup_logging()
    cfg = _load_config()
    out = _cattrade_run_once(cfg, dry_run=dry_run)
    _print_run_result(out, json_out)
    if out.get("error"):
        raise typer.Exit(1)


@cattrade_app.command("daemon")
def cattrade_daemon(
    interval: int = typer.Option(300, help="Seconds between ticks (default 300 = 5min)"),
    dry_run: bool = typer.Option(False, help="Simulate only, no real orders. For one-shot testing use `cattrade run` instead."),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Run cattrade tick forever, sleeping `interval` between ticks.

    Errors in one tick are logged but don't stop the loop. Ctrl-C to exit.
    """
    import time
    _setup_logging()
    cfg = _load_config()
    if dry_run:
        console.print("[yellow]WARNING: dry_run=True in daemon mode — decisions will NOT be executed.[/]")
        console.print("[yellow]         Use `cattrade run` for one-shot dry testing instead.[/]")
    console.print(f"[bold green]cattrade daemon[/]  interval={interval}s dry_run={dry_run}")
    tick_n = 0
    while True:
        tick_n += 1
        started = datetime.now(timezone.utc).isoformat()
        console.print(f"[dim]── tick #{tick_n} {started} ──[/]")
        try:
            out = _cattrade_run_once(cfg, dry_run=dry_run)
            _print_run_result(out, json_out)
        except KeyboardInterrupt:
            console.print("[yellow]daemon stopped by user[/]")
            return
        except Exception as e:
            console.print(f"[red]tick #{tick_n} crashed: {e}[/]")
        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            console.print("[yellow]daemon stopped by user[/]")
            return


# ── cattrade run helpers ──────────────────────────────────────────────────────

_qty_precision_cache: dict[str, int] = {}


def _round_qty(client, symbol: str, qty: float) -> float:
    global _qty_precision_cache
    if not _qty_precision_cache:
        info = client.futures_exchange_info()
        _qty_precision_cache = {s["symbol"]: s.get("quantityPrecision", 3) for s in info.get("symbols", [])}
    precision = _qty_precision_cache.get(symbol, 3)
    return round(qty, precision)


def _close_qty(client, symbol: str, qty: float) -> dict:
    return client.futures_create_order(
        symbol=symbol, side="SELL", type="MARKET",
        quantity=qty, reduceOnly=True,
    )


def _close_full(client, symbol: str, qty: float) -> dict:
    return _close_qty(client, symbol, qty)


# ── signals ───────────────────────────────────────────────────────────────────

@app.command()
def signals(
    top_n: int = typer.Option(20, help="Number of tickers"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show raw Binance Futures OI + gainers signals (no Square)."""
    _setup_logging()

    async def _run():
        from .signals.binance_market import get_market_signals
        return await get_market_signals(top_n=top_n)

    data = asyncio.run(_run())

    if json_out:
        print(json.dumps([{
            "symbol": t.symbol,
            "price_change_pct": t.price_change_pct,
            "oi_ratio": t.oi_ratio,
            "volume_usdt": t.volume_usdt,
        } for t in data], indent=2))
        return

    table = Table(title="Market Signals", show_lines=True)
    table.add_column("Symbol", style="bold")
    table.add_column("24h %", justify="right")
    table.add_column("OI Ratio", justify="right")
    table.add_column("Volume (M USDT)", justify="right")

    for t in data:
        table.add_row(
            t.symbol,
            f"{t.price_change_pct:+.1f}%",
            f"{t.oi_ratio:.1f}x",
            f"{t.volume_usdt / 1_000_000:.1f}M",
        )
    console.print(table)


# ── square ────────────────────────────────────────────────────────────────────

@app.command()
def trending(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show CoinGecko trending coins (Lana-style social signal)."""
    _setup_logging()

    async def _run():
        from .scrapers.coingecko import get_trending_counts
        return await get_trending_counts()

    counts = asyncio.run(_run())

    if json_out:
        print(json.dumps(counts, indent=2))
        return

    table = Table(title="CoinGecko Trending (social signal)", show_lines=True)
    table.add_column("Ticker", style="bold")
    table.add_column("Score", justify="right")

    for ticker, score in list(counts.items())[:15]:
        table.add_row(ticker, str(score))
    console.print(table)


# ── square ────────────────────────────────────────────────────────────────────

@app.command()
def square(
    max_posts: int = typer.Option(200, help="Max posts to fetch"),
    scroll_wait: float = typer.Option(10.0, help="Seconds to wait between scrolls"),
    headless: bool = typer.Option(False, help="Run browser headless"),
    profile_dir: str = typer.Option("", "--profile-dir", help="Persist Chrome profile dir"),
    dump_dir: str = typer.Option("data/square", "--dump-dir", help="Dump raw JSONL here; empty to disable"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Scrape Binance Square via headed Playwright + response interception."""
    _setup_logging()

    async def _run():
        from .scrapers.square import scrape_square
        from pathlib import Path
        pdir = Path(profile_dir) if profile_dir else None
        ddir = Path(dump_dir) if dump_dir else None
        return await scrape_square(
            max_posts=max_posts,
            headless=headless,
            profile_dir=pdir,
            scroll_wait_seconds=scroll_wait,
            dump_dir=ddir,
        )

    snapshot = asyncio.run(_run())

    if json_out:
        print(json.dumps({
            "post_count": len(snapshot.posts),
            "ticker_counts": snapshot.ticker_counts,
        }, indent=2))
        return

    table = Table(title=f"Binance Square Trending ({len(snapshot.posts)} posts)", show_lines=True)
    table.add_column("Ticker", style="bold")
    table.add_column("Mentions", justify="right")

    for ticker, count in list(snapshot.ticker_counts.items())[:20]:
        table.add_row(ticker, str(count))
    console.print(table)


# ── trade / positions ─────────────────────────────────────────────────────────

def _make_trader(cfg: dict, dry_run: bool) -> "BinanceTrader":
    from .trader import BinanceTrader
    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        console.print("[red]Set BINANCE_API_KEY and BINANCE_API_SECRET env vars.[/]")
        raise typer.Exit(1)
    binance_cfg = cfg.get("binance", {})
    trader_cfg = cfg.get("trader", {})
    return BinanceTrader(
        api_key=api_key,
        api_secret=api_secret,
        testnet=binance_cfg.get("testnet", True),
        max_loss_usdt=trader_cfg.get("max_loss_usdt", 200.0),
        leverage=trader_cfg.get("leverage", 10),
        dry_run=dry_run,
    )


@app.command()
def trade(
    symbol: str = typer.Argument(help="Futures symbol e.g. HIGHUSDT"),
    dry_run: bool = typer.Option(True, help="Simulate only, no real order"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Open a LONG position on SYMBOL with fixed 200 USDT stop-loss."""
    _setup_logging()
    cfg = _load_config()
    trader = _make_trader(cfg, dry_run)
    trader_cfg = cfg.get("trader", {})

    result = trader.open_long(
        symbol=symbol.upper(),
        position_size_pct=trader_cfg.get("position_size_pct", 0.05),
    )

    if json_out:
        print(json.dumps(result.to_dict(), indent=2))
        return

    mode = "[yellow]DRY RUN[/]" if result.dry_run else ("[dim]testnet[/]" if result.testnet else "[red]LIVE[/]")
    console.print(f"{mode}  LONG {result.symbol}  entry={result.entry_price}  qty={result.quantity}")
    if not result.dry_run:
        console.print(f"  order={result.order_id}  stop={result.stop_loss_order_id}")


@app.command()
def close(
    symbol: str = typer.Argument(help="Futures symbol e.g. ATUSDT"),
    pct: float = typer.Option(..., "--pct", help="Percent of current qty to close (0-1, e.g. 0.05 = 5%)"),
    dry_run: bool = typer.Option(True, help="Simulate only"),
    journal_it: bool = typer.Option(False, "--journal", help="Write partial_close to cattrade journal"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Manually reduce a position by PCT of current qty."""
    _setup_logging()
    cfg = _load_config()
    symbol = symbol.upper()
    if not (0 < pct <= 1):
        console.print("[red]--pct must be in (0, 1][/]")
        raise typer.Exit(1)

    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        console.print("[red]Set BINANCE_API_KEY and BINANCE_API_SECRET.[/]")
        raise typer.Exit(1)

    from binance.client import Client
    binance_cfg = cfg.get("binance", {})
    testnet = binance_cfg.get("testnet", True)
    client = Client(api_key, api_secret)
    if testnet:
        client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

    positions = client.futures_position_information(symbol=symbol)
    pos = next((p for p in positions if float(p.get("positionAmt", 0)) != 0), None)
    if not pos:
        console.print(f"[red]No open position for {symbol}.[/]")
        raise typer.Exit(1)

    qty = abs(float(pos["positionAmt"]))
    mark = float(pos.get("markPrice") or 0)
    close_qty = _round_qty(client, symbol, qty * pct)
    if close_qty <= 0:
        console.print("[red]close qty rounds to 0 — increase --pct[/]")
        raise typer.Exit(1)

    plan = {"symbol": symbol, "current_qty": qty, "close_qty": close_qty,
            "pct": pct, "mark": mark, "dry_run": dry_run}

    if not dry_run:
        _close_qty(client, symbol, close_qty)
        if journal_it:
            from . import cattrade_journal as journal
            journal.write_partial_close(
                symbol=symbol, qty=close_qty, price=mark,
                conviction=0.0, reason="manual close",
            )

    if json_out:
        print(json.dumps(plan, indent=2))
    else:
        mode = "[yellow]DRY RUN[/]" if dry_run else ("[dim]testnet[/]" if testnet else "[red]LIVE[/]")
        console.print(f"{mode}  close {symbol}  {close_qty} ({pct:.1%} of {qty})")


@app.command()
def positions(
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Show all open Futures positions."""
    _setup_logging()
    cfg = _load_config()

    api_key = os.environ.get("BINANCE_API_KEY", "")
    api_secret = os.environ.get("BINANCE_API_SECRET", "")
    if not api_key or not api_secret:
        console.print("[red]Set BINANCE_API_KEY and BINANCE_API_SECRET env vars.[/]")
        raise typer.Exit(1)

    from binance.client import Client
    binance_cfg = cfg.get("binance", {})
    testnet = binance_cfg.get("testnet", True)
    client = Client(api_key, api_secret, testnet=testnet)
    if testnet:
        client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"

    all_pos = client.futures_position_information()
    open_pos = [p for p in all_pos if float(p.get("positionAmt", 0)) != 0]

    if json_out:
        print(json.dumps(open_pos, indent=2))
        return

    if not open_pos:
        console.print("[dim]No open positions.[/]")
        return

    table = Table(title="Open Positions", show_lines=True)
    table.add_column("Symbol", style="bold")
    table.add_column("Side")
    table.add_column("Qty", justify="right")
    table.add_column("Entry", justify="right")
    table.add_column("Mark", justify="right")
    table.add_column("PnL", justify="right")

    for p in open_pos:
        amt = float(p["positionAmt"])
        pnl = float(p["unRealizedProfit"])
        pnl_fmt = f"[green]+{pnl:.2f}[/]" if pnl >= 0 else f"[red]{pnl:.2f}[/]"
        table.add_row(
            p["symbol"],
            "LONG" if amt > 0 else "SHORT",
            str(abs(amt)),
            p["entryPrice"],
            p.get("markPrice", "-"),
            pnl_fmt,
        )
    console.print(table)


if __name__ == "__main__":
    app()
