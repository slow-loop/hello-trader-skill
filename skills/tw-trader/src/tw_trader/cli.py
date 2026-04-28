"""tw-trader CLI — local-first. No backend required.

Reads/writes YAML under data/account/ via tw_trader.state (paper trading)
and tw_trader.workspace (journal/lessons/watchlist). Briefs are plain
markdown under data/account/research/ — agents write them directly.
Market data comes from the sibling `market` CLI (market_core).
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import dotenv

# Load .env from repo root (parents[4] from cli.py).
dotenv.load_dotenv(Path(__file__).resolve().parents[4] / ".env")

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)

import typer
import yaml

from tw_trader import events as events_log, state, workspace
from tw_trader.workspace import JournalEntry

app = typer.Typer(help="TW Trader CLI (local-first)")


def _echo(obj) -> None:
    typer.echo(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


@app.command()
def account():
    """Show portfolio and trading account status."""
    _echo(state.get_account_status())


@app.command()
def buy(
    symbol: str = typer.Argument(...),
    qty: float = typer.Argument(...),
    limit: Optional[float] = typer.Option(None, "--limit", "-l", help="Limit price; omit for MARKET order"),
    stop_loss: Optional[float] = typer.Option(None, "--stop-loss"),
    take_profit: Optional[float] = typer.Option(None, "--take-profit"),
    reason: str = typer.Option("", "--reason", "-r"),
    strategy: str = typer.Option("", "--strategy"),
):
    """Place a buy order. Without --limit it's a MARKET order (fills immediately unless 漲停)."""
    order, triggered = state.buy(
        symbol,
        qty,
        limit_price=limit,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        strategy=strategy,
    )
    _echo({"order": order.model_dump(mode="json", exclude_none=True), "fills": [t.model_dump(mode="json", exclude_none=True) for t in triggered]})


@app.command()
def sell(
    symbol: str = typer.Argument(...),
    qty: float = typer.Argument(...),
    limit: Optional[float] = typer.Option(None, "--limit", "-l", help="Limit price; omit for MARKET order"),
    reason: str = typer.Option("", "--reason", "-r"),
    strategy: str = typer.Option("", "--strategy"),
):
    """Place a sell order. Without --limit it's a MARKET order (fills immediately unless 跌停)."""
    order, triggered = state.sell(
        symbol,
        qty,
        limit_price=limit,
        reason=reason,
        strategy=strategy,
    )
    _echo({"order": order.model_dump(mode="json", exclude_none=True), "fills": [t.model_dump(mode="json", exclude_none=True) for t in triggered]})


@app.command()
def cancel(
    order_id: str = typer.Argument(..., help="Order ID to cancel"),
    reason: str = typer.Option("", "--reason", "-r"),
):
    """Cancel a pending order by ID."""
    order = state.cancel_order(order_id, reason=reason)
    _echo(order.model_dump(mode="json", exclude_none=True))


@app.command()
def trades(limit: int = typer.Option(20, "--limit", "-n")):
    """Show recent trades."""
    records = state.list_trades(limit=limit)
    _echo([r.model_dump(mode="json") for r in records])


@app.command()
def journal(date_str: Optional[str] = typer.Option(None, "--date", "-d", help="YYYY-MM-DD")):
    """Show journal for a date (defaults to today)."""
    target = date_str or date.today().isoformat()
    doc = workspace.load_journal(target)
    _echo(doc.model_dump(mode="json"))


@app.command()
def journal_add(
    journal_date: Optional[str] = typer.Option(None, "--date", "-d", help="YYYY-MM-DD"),
    entry_type: str = typer.Option("note", "--type"),
    at: str = typer.Option("", "--at", help="HH:MM"),
    action: list[str] = typer.Option([], "--action"),
    note: list[str] = typer.Option([], "--note"),
    file: Optional[Path] = typer.Option(None, "--file", help="Path to YAML file containing JournalEntry data"),
):
    """Append a journal entry."""
    effective_date = journal_date or date.today().isoformat()

    if file:
        try:
            data = yaml.safe_load(file.read_text(encoding="utf-8"))
        except Exception as exc:
            typer.echo(f"Failed to parse {file}: {exc}", err=True)
            raise typer.Exit(1)
        entry = JournalEntry.model_validate(data)
    else:
        entry = JournalEntry(at=at, type=entry_type, actions=action, notes=note)

    doc = workspace.append_journal_entry(effective_date, entry)
    typer.echo(f"Appended entry to {effective_date} ({len(doc.entries)} total).")


@app.command()
def lessons():
    """Show lessons markdown."""
    typer.echo(workspace.load_lessons())


@app.command()
def lessons_set(
    content: Optional[str] = typer.Option(None, "--content", help="Replacement markdown content"),
    file: Optional[Path] = typer.Option(None, "--file", help="Read replacement markdown from file"),
):
    """Replace lessons markdown."""
    if (content is None) == (file is None):
        typer.echo("Provide exactly one of --content or --file.", err=True)
        raise typer.Exit(1)
    if file is not None:
        try:
            content = file.read_text(encoding="utf-8")
        except OSError as exc:
            typer.echo(f"Unable to read {file}: {exc}", err=True)
            raise typer.Exit(1) from exc
    workspace.save_lessons(content or "")
    typer.echo(f"Updated lessons ({len(content or '')} chars).")


@app.command()
def watchlist():
    """Show watchlist (raw + analysis + evaluation)."""
    evaluated = workspace.load_evaluated_watchlist()
    _echo(evaluated.model_dump(mode="json"))


@app.command()
def watchlist_update(
    file: Path = typer.Option(..., "--file", help="Path to YAML file containing WatchlistItem data"),
):
    """Upsert a watchlist item from a YAML file."""
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.echo(f"Failed to parse {file}: {exc}", err=True)
        raise typer.Exit(1)
    from market_core.models import WatchlistItem

    item = WatchlistItem.model_validate(data)
    if item.status in {"watch", "hold"}:
        missing = [f for f in ("thesis", "trigger", "invalidation") if not getattr(item, f).strip()]
        if missing:
            typer.echo(
                f"{item.symbol}: status={item.status} requires non-empty {', '.join(missing)}.",
                err=True,
            )
            raise typer.Exit(1)
    workspace.upsert_watchlist_item(item)
    typer.echo(f"Updated watchlist for {item.symbol}.")


@app.command()
def watchlist_delete(
    symbol: str = typer.Option(..., "--symbol", help="Symbol to remove from watchlist"),
):
    """Remove a watchlist entry by symbol."""
    try:
        workspace.delete_watchlist_item(symbol)
        typer.echo(f"Deleted watchlist entry for {symbol}.")
    except KeyError:
        typer.echo(f"Symbol {symbol!r} not found in watchlist.", err=True)
        raise typer.Exit(1)


@app.command()
def screener_snapshot(
    strategy: str = typer.Option("momentum", "--strategy", "-s"),
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
    limit: int = typer.Option(30, "--limit", "-n"),
    enrich: bool = typer.Option(True, "--enrich/--no-enrich"),
    snapshot_date: Optional[str] = typer.Option(
        None, "--date", "-d", help="YYYY-MM-DD (defaults to today)"
    ),
    suffix: Optional[str] = typer.Option(
        None, "--suffix", help="e.g. 'postclose' → {date}-postclose.json"
    ),
):
    """Run screener and snapshot to data_root/account/screener/{date}[-suffix].json."""
    from market_core import MarketConfig, MarketRuntimeConfig, get_market_profile
    from market_core.screener import run_screener

    target_date = snapshot_date or date.today().isoformat()
    config = MarketRuntimeConfig(market=MarketConfig(profile=profile))
    result = run_screener(
        config,
        get_market_profile(profile),
        strategy=strategy,
        limit=limit,
        enrich=enrich,
    )
    payload = result.model_dump()

    out_path = workspace.screener_snapshot_path(target_date, suffix)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    out_path.write_text(serialized, encoding="utf-8")

    events_log.append_event(
        "screener.snapshot",
        {
            "path": str(out_path.relative_to(workspace.data_root())),
            "date": target_date,
            "strategy": strategy,
        },
    )

    _echo({"path": str(out_path), "result": payload})


@app.command()
def doc_add(
    path: Path = typer.Argument(..., help="Research markdown under data/account/research/"),
):
    """Stamp created_at into frontmatter and publish to the timeline."""
    try:
        payload = workspace.add_doc(path)
    except (FileNotFoundError, ValueError, FileExistsError) as exc:
        typer.echo(f"doc-add failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    _echo(payload)


@app.command()
def sweep():
    """Sweep all pending orders against current quotes + bars."""
    triggered = state.sweep()
    _echo([t.model_dump(mode="json") for t in triggered])


@app.command()
def events(
    limit: int = typer.Option(20, "--limit", "-n", help="Show last N events"),
    type_filter: Optional[str] = typer.Option(
        None, "--type", "-t", help="Comma-separated types, e.g. trade.buy,trade.sell"
    ),
    since: Optional[str] = typer.Option(None, "--since", help="ISO timestamp lower bound"),
):
    """Show recent agent events from the append-only event log."""
    types = [t.strip() for t in type_filter.split(",")] if type_filter else None
    _echo(events_log.read_events(limit=limit, types=types, since=since))


if __name__ == "__main__":
    app()
