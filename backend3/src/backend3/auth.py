from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from backend3.db import get_connection, row_to_dict


async def require_agent(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    conn = await get_connection()
    async with conn.execute("SELECT * FROM agents WHERE token = ?", (token,)) as cur:
        row = await cur.fetchone()
    agent = row_to_dict(row)
    if agent is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    return agent


AgentDep = Depends(require_agent)
