from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend3.auth import require_agent
from backend3.db import dumps, get_connection, log_event, row_to_dict

router = APIRouter()


class DocCreate(BaseModel):
    path: str
    body: str
    metadata: dict = {}


@router.post("/docs")
async def create_doc(req: DocCreate, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    async with conn.execute(
        "SELECT MAX(version) AS v FROM docs WHERE agent_id = ? AND path = ?",
        (agent["id"], req.path),
    ) as cur:
        row = await cur.fetchone()
    version = (row["v"] or 0) + 1
    cur = await conn.execute(
        "INSERT INTO docs (agent_id, path, body, metadata, version) VALUES (?, ?, ?, ?, ?)",
        (agent["id"], req.path, req.body, dumps(req.metadata), version),
    )
    did = cur.lastrowid
    await log_event(
        conn, agent["id"], "doc.saved",
        {"id": did, "path": req.path, "version": version},
    )
    await conn.commit()
    async with conn.execute("SELECT * FROM docs WHERE id = ?", (did,)) as c:
        row = await c.fetchone()
    return row_to_dict(row)


@router.get("/docs/latest")
async def get_latest(path: str, agent: dict = Depends(require_agent)) -> dict:
    conn = await get_connection()
    async with conn.execute(
        "SELECT * FROM docs WHERE agent_id = ? AND path = ? ORDER BY version DESC LIMIT 1",
        (agent["id"], path),
    ) as cur:
        row = await cur.fetchone()
    d = row_to_dict(row)
    if d is None:
        raise HTTPException(404, "Doc not found")
    return d


@router.get("/docs")
async def list_docs(
    prefix: str | None = None,
    limit: int = 100,
    agent: dict = Depends(require_agent),
) -> list[dict]:
    """List latest version of each distinct path (optionally filtered by prefix)."""
    conn = await get_connection()
    q = """
        SELECT d.* FROM docs d
        JOIN (
            SELECT path, MAX(version) AS mv
            FROM docs WHERE agent_id = ?
            GROUP BY path
        ) x ON d.path = x.path AND d.version = x.mv
        WHERE d.agent_id = ?
    """
    params: list = [agent["id"], agent["id"]]
    if prefix:
        q += " AND d.path LIKE ?"
        params.append(f"{prefix}%")
    q += " ORDER BY d.path LIMIT ?"
    params.append(limit)
    async with conn.execute(q, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]
