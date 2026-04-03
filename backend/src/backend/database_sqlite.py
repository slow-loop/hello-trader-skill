"""
database_sqlite.py — SQLite implementation of the database layer.

Drop-in async replacement for database_supabase.py.
All functions are async (aiosqlite). All data crosses the boundary as Pydantic models.

DB file location: $SQLITE_DB_PATH or <repo>/backend/data/trader.db
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from uuid import uuid4

import aiosqlite
from pydantic import BaseModel, Field

from backend.models import (
    AgentRow,
    EquitySnapshot,
    Ledger,
    MarketOverview,
    TradeRecord,
)

# ── Config ────────────────────────────────────────────────────────────────────

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "trader.db"
)
DB_PATH = os.getenv("SQLITE_DB_PATH", os.path.abspath(_DEFAULT_DB_PATH))

_conn: Optional[aiosqlite.Connection] = None


async def _get_conn() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
        await _init_tables(_conn)
    return _conn


async def _init_tables(conn: aiosqlite.Connection) -> None:
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
            id        TEXT PRIMARY KEY,
            user_id   TEXT NOT NULL,
            name      TEXT NOT NULL,
            config    TEXT NOT NULL DEFAULT '{}',
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS accounts (
            agent_id TEXT PRIMARY KEY,
            data     TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id    TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            data        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trades_agent
            ON trades (agent_id, executed_at DESC);

        CREATE TABLE IF NOT EXISTS equity_snapshots (
            agent_id TEXT NOT NULL,
            date     TEXT NOT NULL,
            data     TEXT NOT NULL,
            PRIMARY KEY (agent_id, date)
        );

        CREATE TABLE IF NOT EXISTS journals (
            agent_id TEXT NOT NULL,
            date     TEXT NOT NULL,
            data     TEXT NOT NULL,
            PRIMARY KEY (agent_id, date)
        );

        CREATE TABLE IF NOT EXISTS market_snapshots (
            date    TEXT NOT NULL,
            session TEXT NOT NULL,
            data    TEXT NOT NULL,
            PRIMARY KEY (date, session)
        );
    """)
    await conn.commit()


# ── Agents ────────────────────────────────────────────────────────────────────

async def get_agent(agent_id: str) -> Optional[AgentRow]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM agents WHERE id = ?", (agent_id,)
    ) as cur:
        row = await cur.fetchone()
        if row is None:
            return None
        return AgentRow(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            config=json.loads(row["config"]),
            is_active=bool(row["is_active"]),
        )


async def list_agents(user_id: str) -> List[AgentRow]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT * FROM agents WHERE user_id = ? AND is_active = 1", (user_id,)
    ) as cur:
        rows = await cur.fetchall()
        return [
            AgentRow(
                id=r["id"], user_id=r["user_id"], name=r["name"],
                config=json.loads(r["config"]), is_active=bool(r["is_active"]),
            )
            for r in rows
        ]


async def list_all_active_agents() -> List[str]:
    """Return IDs of all active agents (used by scheduler)."""
    conn = await _get_conn()
    async with conn.execute(
        "SELECT id FROM agents WHERE is_active = 1"
    ) as cur:
        rows = await cur.fetchall()
        return [r["id"] for r in rows]


async def create_agent(user_id: str, name: str, config: Dict[str, Any]) -> AgentRow:
    agent = AgentRow(user_id=user_id, name=name, config=config)
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO agents (id, user_id, name, config, is_active) VALUES (?,?,?,?,?)",
        (agent.id, agent.user_id, agent.name, json.dumps(agent.config), int(agent.is_active)),
    )
    await conn.commit()
    return agent


async def update_agent_config(agent_id: str, config: Dict[str, Any]) -> None:
    conn = await _get_conn()
    await conn.execute(
        "UPDATE agents SET config = ? WHERE id = ?",
        (json.dumps(config), agent_id),
    )
    await conn.commit()


# ── Accounts (ledger state) ───────────────────────────────────────────────────

async def get_account_data(agent_id: str) -> Ledger:
    from backend.core.trading_engine import default_ledger
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM accounts WHERE agent_id = ?", (agent_id,)
    ) as cur:
        row = await cur.fetchone()
        if row is None:
            return default_ledger()
        return Ledger.model_validate(json.loads(row["data"]))


async def save_account_data(agent_id: str, ledger: Ledger) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO accounts (agent_id, data) VALUES (?,?) "
        "ON CONFLICT(agent_id) DO UPDATE SET data = excluded.data",
        (agent_id, ledger.model_dump_json()),
    )
    await conn.commit()


# ── Trades ────────────────────────────────────────────────────────────────────

async def insert_trade(agent_id: str, trade: TradeRecord) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO trades (agent_id, executed_at, data) VALUES (?,?,?)",
        (agent_id, trade.executed_at, trade.model_dump_json()),
    )
    await conn.commit()


async def get_trades(agent_id: str, limit: int = 50) -> List[TradeRecord]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM trades WHERE agent_id = ? ORDER BY executed_at DESC LIMIT ?",
        (agent_id, limit),
    ) as cur:
        rows = await cur.fetchall()
        return [TradeRecord.model_validate_json(r["data"]) for r in rows]


async def get_trades_since(agent_id: str, since: str) -> List[TradeRecord]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM trades WHERE agent_id = ? AND executed_at >= ? ORDER BY executed_at",
        (agent_id, since),
    ) as cur:
        rows = await cur.fetchall()
        return [TradeRecord.model_validate_json(r["data"]) for r in rows]


# ── Equity Snapshots ──────────────────────────────────────────────────────────

async def upsert_equity_snapshot(agent_id: str, snapshot: EquitySnapshot) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO equity_snapshots (agent_id, date, data) VALUES (?,?,?) "
        "ON CONFLICT(agent_id, date) DO UPDATE SET data = excluded.data",
        (agent_id, snapshot.date, snapshot.model_dump_json()),
    )
    await conn.commit()


async def get_equity_snapshots(agent_id: str, days: int = 90) -> List[EquitySnapshot]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM equity_snapshots WHERE agent_id = ? "
        "ORDER BY date DESC LIMIT ?",
        (agent_id, days),
    ) as cur:
        rows = await cur.fetchall()
        return [EquitySnapshot.model_validate_json(r["data"]) for r in reversed(rows)]


# ── Journals (open-ended content — stored as raw JSON) ────────────────────────

async def get_journal(agent_id: str, date_str: str) -> Optional[Dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM journals WHERE agent_id = ? AND date = ?",
        (agent_id, date_str),
    ) as cur:
        row = await cur.fetchone()
        return json.loads(row["data"]) if row else None


async def upsert_journal(agent_id: str, date_str: str, content: Dict[str, Any]) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO journals (agent_id, date, data) VALUES (?,?,?) "
        "ON CONFLICT(agent_id, date) DO UPDATE SET data = excluded.data",
        (agent_id, date_str, json.dumps(content)),
    )
    await conn.commit()


async def list_journals(agent_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT date, data FROM journals WHERE agent_id = ? ORDER BY date DESC LIMIT ?",
        (agent_id, limit),
    ) as cur:
        rows = await cur.fetchall()
        return [{"date": r["date"], **json.loads(r["data"])} for r in rows]


# ── Market Snapshots ──────────────────────────────────────────────────────────

async def upsert_market_snapshot(date_str: str, session: str, data: MarketOverview) -> None:
    conn = await _get_conn()
    await conn.execute(
        "INSERT INTO market_snapshots (date, session, data) VALUES (?,?,?) "
        "ON CONFLICT(date, session) DO UPDATE SET data = excluded.data",
        (date_str, session, data.model_dump_json()),
    )
    await conn.commit()


async def get_market_snapshot(date_str: str, session: str) -> Optional[MarketOverview]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM market_snapshots WHERE date = ? AND session = ?",
        (date_str, session),
    ) as cur:
        row = await cur.fetchone()
        return MarketOverview.model_validate_json(row["data"]) if row else None


async def get_latest_market_snapshot() -> Optional[MarketOverview]:
    conn = await _get_conn()
    async with conn.execute(
        "SELECT data FROM market_snapshots ORDER BY date DESC, session DESC LIMIT 1"
    ) as cur:
        row = await cur.fetchone()
        return MarketOverview.model_validate_json(row["data"]) if row else None
