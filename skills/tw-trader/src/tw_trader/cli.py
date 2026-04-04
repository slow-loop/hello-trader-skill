"""
tw-trader CLI — thin client that calls the backend API.

Usage:
  tw-trader account
  tw-trader buy <symbol> <qty> --price 800 --stop-loss 750 --reason "breakout"
  tw-trader sell <symbol> <qty> --reason "TP hit"
  tw-trader watchlist
  tw-trader journal
  tw-trader journal-add --note "..." --note "..."
  tw-trader trades
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Optional

import httpx
import typer

app = typer.Typer(help="TW Trader CLI")

BACKEND_URL = os.getenv("TRADER_BACKEND_URL", "http://localhost:8000")


def _api(method: str, path: str, **kwargs) -> dict:
    url = f"{BACKEND_URL}{path}"
    try:
        r = httpx.request(method, url, timeout=30, **kwargs)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPStatusError as e:
        typer.echo(f"Error {e.response.status_code}: {e.response.text}", err=True)
        raise typer.Exit(1)
    except httpx.ConnectError:
        typer.echo(f"Cannot connect to backend at {BACKEND_URL}", err=True)
        raise typer.Exit(1)


@app.command()
def account():
    """Show portfolio and trading account status."""
    data = _api("GET", "/account")
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def buy(
    symbol: str = typer.Argument(...),
    qty: int = typer.Argument(...),
    price: Optional[float] = typer.Option(None, "--price", "-p"),
    stop_loss: Optional[float] = typer.Option(None, "--stop-loss"),
    take_profit: Optional[float] = typer.Option(None, "--take-profit"),
    reason: str = typer.Option("", "--reason", "-r"),
    strategy: str = typer.Option("", "--strategy"),
):
    """Buy shares."""
    data = _api(
        "POST",
        "/orders",
        json={
            "symbol": symbol,
            "side": "BUY",
            "quantity": qty,
            "price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "strategy": strategy,
        },
    )
    typer.echo(data.get("message", data))


@app.command()
def sell(
    symbol: str = typer.Argument(...),
    qty: int = typer.Argument(...),
    price: Optional[float] = typer.Option(None, "--price", "-p"),
    reason: str = typer.Option("", "--reason", "-r"),
):
    """Sell shares."""
    data = _api(
        "POST",
        "/orders",
        json={
            "symbol": symbol,
            "side": "SELL",
            "quantity": qty,
            "price": price,
            "reason": reason,
        },
    )
    typer.echo(data.get("message", data))


@app.command()
def trades(limit: int = typer.Option(20, "--limit", "-n")):
    """Show recent trades."""
    data = _api("GET", "/trades", params={"limit": limit})
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def journal(date: Optional[str] = typer.Option(None, "--date", "-d", help="YYYY-MM-DD")):
    """Show journal."""
    if date:
        data = _api("GET", f"/workspace/journals/{date}")
    else:
        data = _api("GET", "/workspace/journals", params={"limit": 5})
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def journal_add(
    journal_date: Optional[str] = typer.Option(None, "--date", "-d", help="YYYY-MM-DD"),
    entry_type: str = typer.Option("note", "--type"),
    at: str = typer.Option("", "--at", help="HH:MM"),
    action: list[str] = typer.Option([], "--action"),
    note: list[str] = typer.Option([], "--note"),
):
    """Append a journal entry through the backend workspace API."""
    effective_date = journal_date or date.today().isoformat()
    data = _api(
        "POST",
        f"/workspace/journals/{effective_date}/entries",
        json={
            "at": at,
            "type": entry_type,
            "actions": action,
            "notes": note,
        },
    )
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def watchlist():
    """Show the watchlist with analysis/evaluation from backend."""
    data = _api("GET", "/workspace/watchlist")
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def market(
    symbols: list[str] = typer.Argument(None, help="Ticker symbols to analyze"),
    snapshot: bool = typer.Option(False, "--snapshot", help="Show latest market snapshot"),
):
    """Show market overview or individual stock analysis."""
    if symbols:
        for sym in symbols:
            data = _api("GET", f"/analysis/{sym}")
            typer.echo(f"=== Analysis for {sym} ===")
            typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
            typer.echo("-" * 40)
    else:
        path = "/snapshots/latest" if snapshot else "/overview"
        data = _api("GET", path)
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command()
def screener(
    strategy: str = typer.Option("momentum", "--strategy"),
    no_enrich: bool = typer.Option(False, "--no-enrich"),
):
    """Run quantitative screener."""
    try:
        data = _api("GET", f"/screener", params={"strategy": strategy, "enrich": not no_enrich})
        typer.echo(json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        typer.echo("Unable to run screener from backend.")


@app.command()
def check_triggers():
    """Evaluate watchlist trigger/invalidation conditions."""
    try:
        data = _api("GET", "/workspace/watchlist")
        rows = []
        for item in data.get("items", []):
            evaluation = item.get("evaluation")
            if evaluation is None:
                continue
            rows.append(
                {
                    "symbol": item.get("symbol"),
                    "status": item.get("status"),
                    **evaluation,
                }
            )
        typer.echo(json.dumps(rows, indent=2, ensure_ascii=False))
    except Exception:
        typer.echo("Unable to evaluate watchlist triggers from backend.")


@app.command()
def heartbeat():
    """Manually trigger a heartbeat."""
    data = _api("POST", "/heartbeat")
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    app()
