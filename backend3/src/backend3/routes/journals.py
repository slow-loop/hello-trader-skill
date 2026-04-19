from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend3.auth import require_agent
from backend3.db import dumps, get_connection, log_event, row_to_dict

router = APIRouter()


class JournalCreate(BaseModel):
    date: str
    entry_type: str
    body: str = ""
    metadata: dict = {}


@router.post("/journals")
async def create_journal(req: JournalCreate, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    cur = await conn.execute(
        "INSERT INTO journals (agent_id, date, entry_type, body, metadata) VALUES (?, ?, ?, ?, ?)",
        (agent["id"], req.date, req.entry_type, req.body, dumps(req.metadata)),
    )
    jid = cur.lastrowid
    await log_event(conn, agent["id"], "journal.appended", {"id": jid, "date": req.date, "entry_type": req.entry_type})
    await conn.commit()
    async with conn.execute("SELECT * FROM journals WHERE id = ?", (jid,)) as c:
        row = await c.fetchone()
    return row_to_dict(row)


@router.get("/journals")
async def list_journals(
    from_date: str | None = None,
    to_date: str | None = None,
    entry_type: str | None = None,
    limit: int = 100,
    agent: dict = Depends(require_agent),
) -> list[dict]:
    conn = await get_connection()
    q = "SELECT * FROM journals WHERE agent_id = ?"
    params: list = [agent["id"]]
    if from_date:
        q += " AND date >= ?"
        params.append(from_date)
    if to_date:
        q += " AND date <= ?"
        params.append(to_date)
    if entry_type:
        q += " AND entry_type = ?"
        params.append(entry_type)
    q += " ORDER BY date DESC, id DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(q, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]
