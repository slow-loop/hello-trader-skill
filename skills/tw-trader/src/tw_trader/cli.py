"""tw-trader CLI — local-first. No backend required.

Reads/writes YAML under data/account/ via tw_trader.state (paper trading)
and tw_trader.workspace (journal/lessons/watchlist/research-card).
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

from tw_trader import state, workspace
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
    price: Optional[float] = typer.Option(None, "--price", "-p"),
    stop_loss: Optional[float] = typer.Option(None, "--stop-loss"),
    take_profit: Optional[float] = typer.Option(None, "--take-profit"),
    reason: str = typer.Option("", "--reason", "-r"),
    strategy: str = typer.Option("", "--strategy"),
):
    """Buy shares (paper)."""
    msg = state.place_buy(
        symbol,
        qty,
        price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        strategy=strategy,
    )
    typer.echo(msg)


@app.command()
def sell(
    symbol: str = typer.Argument(...),
    qty: float = typer.Argument(...),
    price: Optional[float] = typer.Option(None, "--price", "-p"),
    reason: str = typer.Option("", "--reason", "-r"),
):
    """Sell shares (paper)."""
    msg = state.place_sell(symbol, qty, price, reason=reason)
    typer.echo(msg)


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


@app.command()
def research_card_save(
    date_str: str = typer.Option(..., "--date", "-d", help="YYYY-MM-DD"),
    file: Path = typer.Option(..., "--file", help="Path to YAML file containing the research card"),
):
    """Save a research card from a YAML file."""
    try:
        data = yaml.safe_load(file.read_text(encoding="utf-8"))
    except Exception as exc:
        typer.echo(f"Failed to parse {file}: {exc}", err=True)
        raise typer.Exit(1)
    path = workspace.save_research_card(date_str, data)
    typer.echo(f"Saved research card → {path}")


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
    """Manually sweep exit orders against current prices."""
    triggered = state.sweep_exit_orders()
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


if __name__ == "__main__":
    app()
