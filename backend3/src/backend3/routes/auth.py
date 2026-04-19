from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend3.auth import require_agent
from backend3.db import dumps, get_connection, log_event

router = APIRouter()


class RegisterRequest(BaseModel):
    name: str
    metadata: dict = {}


class RegisterResponse(BaseModel):
    agent_id: int
    name: str
    token: str


@router.post("/auth/register", response_model=RegisterResponse)
async def register(req: RegisterRequest) -> RegisterResponse:
    conn = await get_connection()
    async with conn.execute("SELECT id FROM agents WHERE name = ?", (req.name,)) as cur:
        if await cur.fetchone():
            raise HTTPException(400, "Agent name already exists")
    token = secrets.token_urlsafe(32)
    cur = await conn.execute(
        "INSERT INTO agents (name, token, metadata) VALUES (?, ?, ?)",
        (req.name, token, dumps(req.metadata)),
    )
    agent_id = cur.lastrowid
    await log_event(conn, agent_id, "agent.created", {"name": req.name})
    await conn.commit()
    return RegisterResponse(agent_id=agent_id, name=req.name, token=token)


@router.get("/me")
async def me(agent: dict = Depends(require_agent)) -> dict:
    return {
        "agent_id": agent["id"],
        "name": agent["name"],
        "metadata": agent.get("metadata"),
        "created_at": agent["created_at"],
    }
