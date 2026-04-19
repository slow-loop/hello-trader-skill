from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend3.auth import require_agent
from backend3.db import dumps, get_connection, log_event, row_to_dict

router = APIRouter()


class OperationPropose(BaseModel):
    symbol: str
    side: str  # 'buy' or 'sell'
    qty: float
    price: float
    reason: str
    metadata: dict = {}


class OperationPatch(BaseModel):
    status: str  # 'rejected' or 'canceled'
    rejected_reason: str | None = None


class TradeRecord(BaseModel):
    operation_id: int
    fill_price: float
    qty: float | None = None
    fees: float = 0.0
    pnl: float | None = None


@router.post("/operations")
async def propose(req: OperationPropose, agent: dict = Depends(require_agent)) -> dict:
    if req.side not in ("buy", "sell"):
        raise HTTPException(400, "side must be 'buy' or 'sell'")
    conn = await get_connection()
    cur = await conn.execute(
        """INSERT INTO operations
           (agent_id, symbol, side, qty, price, reason, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (agent["id"], req.symbol, req.side, req.qty, req.price, req.reason, dumps(req.metadata)),
    )
    oid = cur.lastrowid
    await log_event(
        conn, agent["id"], "operation.proposed",
        {"id": oid, "symbol": req.symbol, "side": req.side, "qty": req.qty, "price": req.price},
    )
    await conn.commit()
    async with conn.execute("SELECT * FROM operations WHERE id = ?", (oid,)) as c:
        row = await c.fetchone()
    return row_to_dict(row)


@router.patch("/operations/{op_id}")
async def patch_op(op_id: int, req: OperationPatch, agent: dict = Depends(require_agent)) -> dict:
    if req.status not in ("rejected", "canceled"):
        raise HTTPException(400, "status must be 'rejected' or 'canceled' (executed is set via POST /trades)")
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM operations WHERE id = ? AND agent_id = ?", (op_id, agent["id"])
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(404, "Operation not found")
    if row["status"] != "proposed":
        raise HTTPException(409, f"Operation is already {row['status']}")
    await conn.execute(
        "UPDATE operations SET status = ?, rejected_reason = ? WHERE id = ?",
        (req.status, req.rejected_reason, op_id),
    )
    await log_event(
        conn, agent["id"], f"operation.{req.status}",
        {"id": op_id, "reason": req.rejected_reason},
    )
    await conn.commit()
    async with conn.execute("SELECT * FROM operations WHERE id = ?", (op_id,)) as c:
        r = await c.fetchone()
    return row_to_dict(r)


@router.get("/operations")
async def list_ops(
    status: str | None = None,
    limit: int = 100,
    agent: dict = Depends(require_agent),
) -> list[dict]:
    conn = await get_connection()
    q = "SELECT * FROM operations WHERE agent_id = ?"
    params: list = [agent["id"]]
    if status:
        q += " AND status = ?"
        params.append(status)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(q, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]


@router.post("/trades")
async def record_trade(req: TradeRecord, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM operations WHERE id = ? AND agent_id = ?",
        (req.operation_id, agent["id"]),
    ) as cur:
        op = await cur.fetchone()
    if op is None:
        raise HTTPException(404, "Operation not found")
    if op["status"] != "proposed":
        raise HTTPException(409, f"Operation is already {op['status']}")
    qty = req.qty if req.qty is not None else op["qty"]
    cur = await conn.execute(
        """INSERT INTO trades
           (operation_id, agent_id, symbol, side, qty, fill_price, fees, pnl)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (op["id"], agent["id"], op["symbol"], op["side"], qty, req.fill_price, req.fees, req.pnl),
    )
    tid = cur.lastrowid
    await conn.execute(
        "UPDATE operations SET status = 'executed', executed_at = datetime('now') WHERE id = ?",
        (op["id"],),
    )
    await log_event(
        conn, agent["id"], "trade.recorded",
        {"trade_id": tid, "operation_id": op["id"], "symbol": op["symbol"],
         "side": op["side"], "qty": qty, "fill_price": req.fill_price},
    )
    await log_event(conn, agent["id"], "operation.executed", {"id": op["id"]})
    await conn.commit()
    async with conn.execute("SELECT * FROM trades WHERE id = ?", (tid,)) as c:
        r = await c.fetchone()
    return row_to_dict(r)


@router.get("/trades")
async def list_trades(
    symbol: str | None = None,
    limit: int = 100,
    agent: dict = Depends(require_agent),
) -> list[dict]:
    conn = await get_connection()
    q = "SELECT * FROM trades WHERE agent_id = ?"
    params: list = [agent["id"]]
    if symbol:
        q += " AND symbol = ?"
        params.append(symbol)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(q, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]
