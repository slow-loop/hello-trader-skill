from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend3.auth import require_agent
from backend3.db import dumps, get_connection, log_event, row_to_dict

router = APIRouter()


class WatchlistUpsert(BaseModel):
    thesis: str | None = None
    status: str = "active"
    metadata: dict = {}


@router.get("/watchlist")
async def list_watchlist(agent: dict = Depends(require_agent)) -> list[dict]:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM watchlist_items WHERE agent_id = ? ORDER BY symbol",
        (agent["id"],),
    ) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]


@router.get("/watchlist/{symbol}")
async def get_item(symbol: str, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM watchlist_items WHERE agent_id = ? AND symbol = ?",
        (agent["id"], symbol),
    ) as cur:
        row = await cur.fetchone()
    d = row_to_dict(row)
    if d is None:
        raise HTTPException(404, "Not found")
    return d


@router.put("/watchlist/{symbol}")
async def upsert_item(
    symbol: str, req: WatchlistUpsert, agent: dict = Depends(require_agent)
) -> dict:
    conn = await get_connection()
    await conn.execute(
        """
        INSERT INTO watchlist_items (agent_id, symbol, thesis, status, metadata, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(agent_id, symbol) DO UPDATE SET
          thesis=excluded.thesis,
          status=excluded.status,
          metadata=excluded.metadata,
          updated_at=datetime('now')
        """,
        (agent["id"], symbol, req.thesis, req.status, dumps(req.metadata)),
    )
    await log_event(conn, agent["id"], "watchlist.upserted", {"symbol": symbol, "status": req.status})
    await conn.commit()
    async with conn.execute(
        "SELECT * FROM watchlist_items WHERE agent_id = ? AND symbol = ?",
        (agent["id"], symbol),
    ) as cur:
        row = await cur.fetchone()
    return row_to_dict(row)


@router.delete("/watchlist/{symbol}")
async def delete_item(symbol: str, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    cur = await conn.execute(
        "DELETE FROM watchlist_items WHERE agent_id = ? AND symbol = ?",
        (agent["id"], symbol),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Not found")
    await log_event(conn, agent["id"], "watchlist.removed", {"symbol": symbol})
    await conn.commit()
    return {"ok": True, "symbol": symbol}
