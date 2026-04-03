"""
services.py — Business logic. Bridges trading_engine (pure) with DB.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from backend import database as db
from backend.core.trading_engine import (
    execute_order,
    build_status,
    build_equity_snapshot,
    check_pending_orders,
    update_orders,
)
from backend.core.market_data import get_quote


# ── Portfolio ─────────────────────────────────────────────────────────────────

async def get_portfolio(agent_id: str) -> Dict[str, Any]:
    ledger = await db.get_account_data(agent_id)
    trade_history = await db.get_trades(agent_id, limit=100)

    # Fetch live prices for open positions
    current_prices: Dict[str, float] = {}
    for sym in ledger.get("positions", {}):
        try:
            q = get_quote(sym)
            if q.price:
                current_prices[sym] = q.price
        except Exception:
            pass

    # Auto-check pending orders
    updated_ledger, triggered = check_pending_orders(ledger, current_prices)
    if triggered:
        await db.save_account_data(agent_id, updated_ledger)
        for trade in triggered:
            await db.insert_trade(agent_id, trade)
        ledger = updated_ledger
        trade_history = await db.get_trades(agent_id, limit=100)

    return build_status(ledger, trade_history, current_prices)


# ── Trade Execution ───────────────────────────────────────────────────────────

async def place_order(
    agent_id: str,
    symbol: str,
    side: str,
    qty: int,
    price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    reason: str = "",
    strategy: str = "",
    tags: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    market_snapshot: Optional[Dict] = None,
) -> str:
    ledger = await db.get_account_data(agent_id)
    msg, updated_ledger, trade = execute_order(
        ledger, symbol, side, qty, price,
        stop_loss, take_profit, reason,
        strategy, tags, confidence, market_snapshot,
    )
    if trade is not None:
        await db.save_account_data(agent_id, updated_ledger)
        await db.insert_trade(agent_id, trade)
    return msg


async def modify_orders(
    agent_id: str,
    symbol: str,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> str:
    ledger = await db.get_account_data(agent_id)
    msg, updated_ledger = update_orders(ledger, symbol, stop_loss, take_profit)
    if "Error" not in msg:
        await db.save_account_data(agent_id, updated_ledger)
    return msg


# ── Equity Snapshot ───────────────────────────────────────────────────────────

async def record_snapshot(agent_id: str) -> Dict[str, Any]:
    ledger = await db.get_account_data(agent_id)
    current_prices: Dict[str, float] = {}
    for sym in ledger.get("positions", {}):
        try:
            q = get_quote(sym)
            if q.price:
                current_prices[sym] = q.price
        except Exception:
            pass
    snapshot = build_equity_snapshot(ledger, current_prices)
    await db.upsert_equity_snapshot(agent_id, snapshot)
    return snapshot


# ── Market Snapshot ───────────────────────────────────────────────────────────

async def capture_market_snapshot(session: str) -> Dict[str, Any]:
    from backend.core.market_service import build_overview
    today = date.today().isoformat()
    data = build_overview()
    await db.upsert_market_snapshot(today, session, data)
    return data
