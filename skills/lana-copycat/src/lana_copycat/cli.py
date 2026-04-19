"""Lana-copycat CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

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


# ── cattrade ──────────────────────────────────────────────────────────────────

@app.command()
def cattrade(
    top_n: int = typer.Option(10, help="Top candidates to return"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Pure cattrade gsheet pipeline — MM-structure signals, no Square.

    Independent filtering logic from `scan`. Uses only the 11 cattrade
    rankings + Pattern B (大戶領先做多) to pick candidates.
    """
    _setup_logging()
    cfg = _load_config()
    cattrade_cfg = cfg.get("cattrade", {})
    sheet_id = cattrade_cfg.get("sheet_id")
    if not sheet_id:
        console.print("[red]cattrade.sheet_id missing in config.yaml[/]")
        raise typer.Exit(1)

    from .signals.cattrade import fetch_cattrade_sections, pick_cattrade, DEFAULT_CATTRADE_CFG

    merged = {**DEFAULT_CATTRADE_CFG, **cattrade_cfg}
    console.print("[bold cyan]Fetching cattrade sheet...[/]")
    try:
        sections = fetch_cattrade_sections(
            sheet_id, timeout_sec=cattrade_cfg.get("fetch_timeout_sec", 15)
        )
    except Exception as e:
        console.print(f"[red]cattrade fetch failed: {e}[/]")
        raise typer.Exit(1)
    cands = pick_cattrade(sections, merged)[:top_n]

    if json_out:
        print(json.dumps([{
            "symbol": c.symbol,
            "score": c.score,
            "patterns": c.patterns,
            "oi_usdt": c.oi_usdt,
            "reasons": c.reasons,
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
            str(i),
            c.symbol,
            f"{c.score:.2f}",
            ",".join(c.patterns) or "-",
            f"{c.oi_usdt/1_000_000:.1f}M",
            "; ".join(c.reasons),
        )
    console.print(table)


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
