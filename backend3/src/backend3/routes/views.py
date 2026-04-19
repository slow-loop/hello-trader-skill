from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends

from backend3.auth import require_agent
from backend3.db import get_connection

router = APIRouter()


@router.get("/positions")
async def positions(agent: dict = Depends(require_agent)) -> list[dict]:
    """Compute current positions from trade history (FIFO, net qty)."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT symbol, side, qty, fill_price FROM trades WHERE agent_id = ? ORDER BY id",
        (agent["id"],),
    ) as cur:
        rows = await cur.fetchall()
    pos: dict[str, dict] = defaultdict(lambda: {"qty": 0.0, "cost": 0.0})
    for r in rows:
        sign = 1 if r["side"] == "buy" else -1
        p = pos[r["symbol"]]
        if sign > 0:
            p["cost"] += r["qty"] * r["fill_price"]
            p["qty"] += r["qty"]
        else:
            if p["qty"] > 0:
                avg = p["cost"] / p["qty"]
                p["cost"] -= min(r["qty"], p["qty"]) * avg
            p["qty"] -= r["qty"]
    out = []
    for sym, p in pos.items():
        if abs(p["qty"]) < 1e-9:
            continue
        avg = (p["cost"] / p["qty"]) if p["qty"] else 0.0
        out.append({"symbol": sym, "qty": p["qty"], "avg_cost": avg})
    return out


@router.get("/account")
async def account(agent: dict = Depends(require_agent)) -> dict:
    """Aggregate realized PnL + open positions summary."""
    conn = await get_connection()
    async with conn.execute(
        "SELECT COALESCE(SUM(pnl), 0) AS realized, COALESCE(SUM(fees), 0) AS fees FROM trades WHERE agent_id = ?",
        (agent["id"],),
    ) as cur:
        r = await cur.fetchone()
    async with conn.execute(
        "SELECT COUNT(*) AS n FROM trades WHERE agent_id = ?", (agent["id"],)
    ) as cur:
        tc = await cur.fetchone()
    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "realized_pnl": r["realized"],
        "total_fees": r["fees"],
        "trade_count": tc["n"],
    }
