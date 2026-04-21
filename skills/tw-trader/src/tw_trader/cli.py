"""tw-trader CLI — local-first. No backend required.

Reads/writes YAML under data/account/ via tw_trader.state (paper trading)
and tw_trader.workspace (journal/lessons/watchlist/brief).
Market data comes from the sibling `market` CLI (market_core).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

import dotenv

dotenv.load_dotenv(Path(__file__).resolve().parents[2] / ".env")

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


brief_app = typer.Typer(help="Market brief (daily overview card).")
app.add_typer(brief_app, name="brief")


@brief_app.command("init")
def brief_init():
    """Scaffold a new brief draft at the canonical path."""
    path = workspace.init_brief()
    typer.echo(str(path))


@brief_app.command("commit")
def brief_commit(
    path: Optional[Path] = typer.Argument(None, help="Brief path; defaults to the latest."),
):
    """Validate and finalize a brief (emits brief.commit event)."""
    target = path or workspace.latest_brief_draft()
    if target is None:
        typer.echo("No brief found to commit.", err=True)
        raise typer.Exit(1)
    try:
        workspace.commit_brief(target)
    except Exception as exc:
        typer.echo(f"Commit failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Committed {target}")


@brief_app.command("show")
def brief_show(
    path: Optional[Path] = typer.Argument(None, help="Brief path; defaults to the latest."),
):
    """Show a brief (defaults to latest)."""
    target = path or workspace.latest_brief_draft()
    if target is None:
        typer.echo("No brief found.", err=True)
        raise typer.Exit(1)
    _echo(workspace.load_brief(target))


@app.command()
def check_triggers():
    """Evaluate watchlist trigger/invalidation conditions (shorthand view)."""
    evaluated = workspace.load_evaluated_watchlist()
    rows = []
    for item in evaluated.items:
        if item.evaluation is None:
            continue
        rows.append(
            {
                "symbol": item.symbol,
                "status": item.status,
                **item.evaluation.model_dump(mode="json"),
            }
        )
    _echo(rows)


@app.command()
def sweep():
    """Sweep all pending orders against current quotes + bars."""
    triggered = state.sweep()
    _echo([t.model_dump(mode="json") for t in triggered])


@app.command()
def publish(
    date_arg: Optional[str] = typer.Option(
        None, "--date", "-d", help="Target date YYYY-MM-DD (default: today)"
    ),
):
    """Render daily publish artifacts (poster.png) from post.yaml + local state."""
    from tw_trader.publish import render_poster

    try:
        path = render_poster(date_arg)
    except Exception as exc:
        typer.echo(f"publish failed: {exc}", err=True)
        raise typer.Exit(1)
    typer.echo(f"wrote {path}")


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
