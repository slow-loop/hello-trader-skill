from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend3.auth import require_agent
from backend3.db import dumps, get_connection, log_event, row_to_dict

router = APIRouter()


class SnapshotCreate(BaseModel):
    kind: str
    source: str | None = None
    params: dict = {}
    summary: dict = {}
    payload: str | None = None  # raw string (could be JSON, CSV, or local:// pointer)


@router.post("/snapshots")
async def create_snapshot(req: SnapshotCreate, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    cur = await conn.execute(
        """INSERT INTO snapshots (agent_id, kind, source, params, summary, payload)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (agent["id"], req.kind, req.source, dumps(req.params), dumps(req.summary), req.payload),
    )
    sid = cur.lastrowid
    await log_event(
        conn, agent["id"], "snapshot.saved",
        {"id": sid, "kind": req.kind, "source": req.source},
    )
    await conn.commit()
    async with conn.execute("SELECT * FROM snapshots WHERE id = ?", (sid,)) as c:
        r = await c.fetchone()
    return row_to_dict(r)


@router.get("/snapshots")
async def list_snapshots(
    kind: str | None = None,
    from_ts: str | None = None,
    limit: int = 50,
    agent: dict = Depends(require_agent),
) -> list[dict]:
    conn = await get_connection()
    q = "SELECT id, agent_id, kind, source, ts, params, summary FROM snapshots WHERE agent_id = ?"
    params: list = [agent["id"]]
    if kind:
        q += " AND kind = ?"
        params.append(kind)
    if from_ts:
        q += " AND ts >= ?"
        params.append(from_ts)
    q += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(q, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]


@router.get("/snapshots/{snap_id}")
async def get_snapshot(snap_id: int, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM snapshots WHERE id = ? AND agent_id = ?", (snap_id, agent["id"])
    ) as cur:
        row = await cur.fetchone()
    d = row_to_dict(row)
    if d is None:
        raise HTTPException(404, "Snapshot not found")
    return d
