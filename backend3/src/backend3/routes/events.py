from __future__ import annotations

from fastapi import APIRouter, Depends

from backend3.auth import require_agent
from backend3.db import get_connection, row_to_dict

router = APIRouter()


@router.get("/events")
async def list_events(
    from_ts: str | None = None,
    types: str | None = None,
    limit: int = 100,
    agent: dict = Depends(require_agent),
) -> list[dict]:
    conn = await get_connection()
    q = "SELECT * FROM events WHERE agent_id = ?"
    params: list = [agent["id"]]
    if from_ts:
        q += " AND ts >= ?"
        params.append(from_ts)
    if types:
        type_list = [t.strip() for t in types.split(",") if t.strip()]
        if type_list:
            q += " AND type IN (" + ",".join("?" * len(type_list)) + ")"
            params.extend(type_list)
    q += " ORDER BY seq DESC LIMIT ?"
    params.append(limit)
    async with conn.execute(q, params) as cur:
        rows = await cur.fetchall()
    return [row_to_dict(r) for r in rows]
