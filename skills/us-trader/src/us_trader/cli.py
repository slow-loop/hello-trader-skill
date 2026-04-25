"""us-trader CLI.

Key commands:
    signal          top signals from ACTIVE strategy
    regime          benchmark regime snapshot (SPX/QQQ/SOX/VIX)
    account         print current ledger + equity
    watchlist       print watchlist + latest quote
    buy / sell      record trade (append to ledger)
    journal-add     append journal entry (from tmp YAML file)
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import typer
import yaml
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)

from us_trader.workspace import Workspace, resolve_active_strategy

app = typer.Typer(add_completion=False, no_args_is_help=True, help="us-trader CLI")

DEFAULT_ACCOUNT = "us-momentum"


def _ws(account: str = DEFAULT_ACCOUNT) -> Workspace:
    from us_trader.workspace import SKILL_ROOT

    ws = Workspace(account=account, skill_root=SKILL_ROOT)
    ws.ensure_dirs()
    return ws


def _echo(obj) -> None:
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _load_ledger(ws: Workspace) -> dict:
    if ws.ledger_path.exists():
        return json.loads(ws.ledger_path.read_text())
    return {"positions": {}, "trades": [], "cash": 100_000.0}


def _save_ledger(ws: Workspace, ledger: dict) -> None:
    ws.ledger_path.write_text(json.dumps(ledger, indent=2, default=str))


# ---------------------------------------------------------------------------
# Signals / regime / account
# ---------------------------------------------------------------------------


@app.command()
def signal(
    account: str = typer.Option(DEFAULT_ACCOUNT),
    universe: str = typer.Option("sp500"),
    top: int = typer.Option(20),
    start: str = typer.Option("2024-01-01"),
    end: str | None = typer.Option(None),
) -> None:
    """Run ACTIVE strategy, print top N signals on latest bar."""
    from market_core.data.ohlc_cache import load_many
    from market_core.features import compute_features
    from market_core.strategy import apply_strategy, load_strategy
    from market_core.universes import resolve_universe

    ws = _ws(account)
    strategy_path = resolve_active_strategy(ws)
    cfg = load_strategy(strategy_path)

    symbols = resolve_universe(universe) if "," not in universe else [
        s.strip().upper() for s in universe.split(",")
    ]
    typer.echo(f"loading {len(symbols)} symbols...", err=True)
    ohlc = load_many(symbols, start=start, end=end)

    rows = []
    for sym, df in ohlc.items():
        if len(df) < 250:
            continue
        feat = compute_features(df)
        sig = apply_strategy(cfg, feat)
        latest = sig.iloc[-1]
        rows.append({
            "symbol": sym,
            "date": str(feat.index[-1].date()),
            "close": round(float(feat["close"].iloc[-1]), 2),
            "composite_score": round(float(latest["composite_score"]), 3),
            "entry_ok": bool(latest["entry_ok"]),
            "firing_factors": list(latest["firing_factors"]),
            "per_factor": {
                fref.id: round(float(latest.get(fref.id, 0.0)), 3)
                for fref in cfg.factors
            },
            "risk": {
                "close": round(float(feat["close"].iloc[-1]), 2),
                "atr_14": round(float(feat["atr_14"].iloc[-1]), 2) if "atr_14" in feat else None,
                "sma_20": round(float(feat["sma_20"].iloc[-1]), 2),
                "sma_50": round(float(feat["sma_50"].iloc[-1]), 2),
            },
        })

    rows.sort(key=lambda r: r["composite_score"], reverse=True)
    _echo({
        "account": account,
        "strategy": {"name": cfg.name, "version": cfg.version, "file": strategy_path.name},
        "universe_size": len(rows),
        "top": rows[:top],
    })


@app.command()
def regime(
    benchmarks: str = typer.Option("SPX,QQQ,SOX,VIX,DJIA"),
    start: str = typer.Option("2024-01-01"),
    end: str | None = typer.Option(None),
) -> None:
    """Compute regime snapshot across benchmark indices."""
    from market_core.data.ohlc_cache import load_ohlc
    from market_core.factors.registry import evaluate_all
    from market_core.features import compute_features
    from market_core.universes import BENCHMARKS

    names = [n.strip().upper() for n in benchmarks.split(",")]
    out = {}
    for name in names:
        sym = BENCHMARKS.get(name, name)
        df = load_ohlc(sym, start=start, end=end)
        if len(df) < 50:
            out[name] = {"error": "insufficient data"}
            continue
        feat = compute_features(df)
        last = feat.iloc[-1]
        regime_scores = evaluate_all(feat, factor_ids=["regime_risk_on"])
        out[name] = {
            "symbol": sym,
            "date": str(feat.index[-1].date()),
            "close": round(float(last["close"]), 2),
            "ret_1d_pct": round(float(last.get("ret_1d", 0) * 100), 2),
            "ret_20d_pct": round(float(last.get("ret_20d", 0) * 100), 2),
            "dist_sma20_pct": round(float(last.get("dist_sma20_pct", 0)), 2),
            "dist_sma50_pct": round(float(last.get("dist_sma50_pct", 0)), 2),
            "adx_14": round(float(last.get("adx_14", 0)), 2),
            "regime_risk_on_score": round(float(regime_scores["regime_risk_on"].iloc[-1]), 3),
        }
    _echo({"date": datetime.utcnow().strftime("%Y-%m-%d"), "benchmarks": out})


@app.command()
def account(account: str = typer.Option(DEFAULT_ACCOUNT)) -> None:
    """Print current ledger state."""
    ws = _ws(account)
    ledger = _load_ledger(ws)
    _echo({
        "account": account,
        "cash": ledger.get("cash"),
        "positions": ledger.get("positions"),
        "trade_count": len(ledger.get("trades", [])),
        "last_trades": ledger.get("trades", [])[-5:],
    })


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


def _watchlist_path(ws: Workspace) -> Path:
    return ws.account_dir / "watchlist.yaml"


@app.command()
def watchlist(account: str = typer.Option(DEFAULT_ACCOUNT)) -> None:
    """Print watchlist + latest close per symbol."""
    from market_core.data.ohlc_cache import load_ohlc

    ws = _ws(account)
    path = _watchlist_path(ws)
    items = yaml.safe_load(path.read_text()) if path.exists() else []
    if not items:
        _echo({"watchlist": [], "note": "empty"})
        return
    enriched = []
    for item in items:
        sym = item["symbol"]
        try:
            df = load_ohlc(sym, start="2024-01-01")
            last_close = float(df["close"].iloc[-1]) if not df.empty else None
            item["latest_close"] = round(last_close, 2) if last_close else None
        except Exception as exc:
            item["error"] = str(exc)
        enriched.append(item)
    _echo({"account": account, "watchlist": enriched})


@app.command("watchlist-update")
def watchlist_update(
    file: Path = typer.Option(..., exists=True, help="YAML file with list of items to upsert"),
    account: str = typer.Option(DEFAULT_ACCOUNT),
) -> None:
    """Upsert watchlist items from a YAML file under tmp/."""
    ws = _ws(account)
    path = _watchlist_path(ws)
    existing = yaml.safe_load(path.read_text()) if path.exists() else []
    by_sym = {item["symbol"]: item for item in existing}

    updates = yaml.safe_load(file.read_text())
    if not isinstance(updates, list):
        updates = [updates]
    for item in updates:
        sym = item["symbol"].upper()
        item["symbol"] = sym
        item["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        by_sym[sym] = {**by_sym.get(sym, {}), **item}

    new_list = list(by_sym.values())
    path.write_text(yaml.safe_dump(new_list, sort_keys=False, allow_unicode=True))
    _echo({"updated": [u["symbol"] for u in updates], "count": len(new_list)})


# ---------------------------------------------------------------------------
# Buy / Sell / Journal
# ---------------------------------------------------------------------------


@app.command()
def buy(
    symbol: str,
    qty: int = typer.Option(...),
    price: float = typer.Option(...),
    stop_loss: float = typer.Option(..., "--stop-loss"),
    take_profit: float = typer.Option(..., "--take-profit"),
    strategy: str = typer.Option(...),
    reason: str = typer.Option(...),
    account: str = typer.Option(DEFAULT_ACCOUNT),
) -> None:
    """Record a buy in the ledger."""
    ws = _ws(account)
    ledger = _load_ledger(ws)
    sym = symbol.upper()
    trade = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "action": "buy",
        "symbol": sym,
        "qty": qty,
        "price": price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "strategy": strategy,
        "reason": reason,
    }
    pos = ledger["positions"].get(sym, {"qty": 0, "avg_price": 0.0})
    total_cost = pos["qty"] * pos["avg_price"] + qty * price
    new_qty = pos["qty"] + qty
    pos.update({
        "qty": new_qty,
        "avg_price": round(total_cost / new_qty, 4) if new_qty else 0.0,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "strategy": strategy,
        "updated_at": trade["timestamp"],
    })
    ledger["positions"][sym] = pos
    ledger["cash"] = round(ledger.get("cash", 0.0) - qty * price, 2)
    ledger["trades"].append(trade)
    _save_ledger(ws, ledger)
    _echo({"trade": trade, "position": pos, "cash": ledger["cash"]})


@app.command()
def sell(
    symbol: str,
    qty: int = typer.Option(...),
    price: float = typer.Option(...),
    reason: str = typer.Option(...),
    account: str = typer.Option(DEFAULT_ACCOUNT),
) -> None:
    """Record a sell in the ledger."""
    ws = _ws(account)
    ledger = _load_ledger(ws)
    sym = symbol.upper()
    pos = ledger["positions"].get(sym)
    if not pos or pos["qty"] < qty:
        raise typer.BadParameter(f"insufficient position: {sym} has {pos['qty'] if pos else 0}")

    realized_pnl = round((price - pos["avg_price"]) * qty, 2)
    trade = {
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "action": "sell",
        "symbol": sym,
        "qty": qty,
        "price": price,
        "realized_pnl": realized_pnl,
        "reason": reason,
    }
    pos["qty"] -= qty
    if pos["qty"] == 0:
        del ledger["positions"][sym]
    else:
        pos["updated_at"] = trade["timestamp"]
        ledger["positions"][sym] = pos
    ledger["cash"] = round(ledger.get("cash", 0.0) + qty * price, 2)
    ledger["trades"].append(trade)
    _save_ledger(ws, ledger)
    _echo({"trade": trade, "cash": ledger["cash"]})


@app.command("journal-add")
def journal_add(
    file: Path = typer.Option(..., exists=True, help="YAML journal entry (under tmp/)"),
    account: str = typer.Option(DEFAULT_ACCOUNT),
) -> None:
    """Append a journal entry to today's journal YAML."""
    ws = _ws(account)
    entry = yaml.safe_load(file.read_text())
    entry.setdefault("timestamp", datetime.utcnow().isoformat(timespec="seconds") + "Z")

    path = ws.journal_path(entry.get("date"))
    if path.exists():
        existing = yaml.safe_load(path.read_text()) or []
    else:
        existing = []
    if not isinstance(existing, list):
        existing = [existing]
    existing.append(entry)
    path.write_text(yaml.safe_dump(existing, sort_keys=False, allow_unicode=True))
    _echo({"journal": str(path), "entries": len(existing)})


@app.command("strategy-info")
def strategy_info(account: str = typer.Option(DEFAULT_ACCOUNT)) -> None:
    """Show the active strategy config."""
    ws = _ws(account)
    strategy_path = resolve_active_strategy(ws)
    cfg = yaml.safe_load(strategy_path.read_text())
    _echo({"file": str(strategy_path), "config": cfg})


def main() -> None:
    app()


if __name__ == "__main__":
    main()
