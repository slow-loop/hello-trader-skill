from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import aiosqlite

from backend2.models import TradeRecord, TradingState, utc_now_iso

PROJECT_ROOT = Path(__file__).resolve().parents[2]
def _get_db_path() -> Path:
    return Path(os.getenv("BACKEND2_DB_PATH", PROJECT_ROOT / "data" / "backend2.sqlite"))


_conn: aiosqlite.Connection | None = None


async def get_connection() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        db_path = _get_db_path()
        if db_path != Path(":memory:"):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(db_path)
        _conn.row_factory = aiosqlite.Row
        # await _conn.execute("PRAGMA journal_mode=WAL")
        await _conn.execute("PRAGMA foreign_keys=ON")
        await _init_tables(_conn)
    return _conn


async def close_connection() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


async def _init_tables(conn: aiosqlite.Connection) -> None:
    await conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspace_states (
            workspace_id TEXT PRIMARY KEY,
            data       TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS trades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT NOT NULL,
            executed_at TEXT NOT NULL,
            data        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_trades_workspace ON trades (workspace_id, executed_at DESC);

        CREATE TABLE IF NOT EXISTS market_snapshots (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id   TEXT NOT NULL,
            market_profile TEXT NOT NULL,
            phase          TEXT NOT NULL,
            captured_at    TEXT NOT NULL,
            data           TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_snapshots_workspace ON market_snapshots (workspace_id, captured_at DESC);

        CREATE TABLE IF NOT EXISTS account_snapshots (
            workspace_id  TEXT NOT NULL,
            date          TEXT NOT NULL,
            account_value REAL NOT NULL,
            cash          REAL NOT NULL,
            market_value  REAL NOT NULL,
            PRIMARY KEY (workspace_id, date)
        );
        """
    )
    await conn.commit()


async def get_trading_state(workspace_id: str) -> TradingState | None:
    conn = await get_connection()
    async with conn.execute(
        "SELECT data FROM workspace_states WHERE workspace_id = ?",
        (workspace_id,),
    ) as cur:
        row = await cur.fetchone()
        if row is None:
            return None
        return TradingState.model_validate_json(row["data"])


async def save_trading_state(workspace_id: str, state: TradingState) -> None:
    conn = await get_connection()
    payload = state.model_copy(update={"updated_at": utc_now_iso()})
    await conn.execute(
        """
        INSERT INTO workspace_states (workspace_id, data, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(workspace_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
        """,
        (workspace_id, payload.model_dump_json(), payload.updated_at),
    )
    await conn.commit()


async def insert_trade(workspace_id: str, trade: TradeRecord) -> None:
    conn = await get_connection()
    await conn.execute(
        "INSERT INTO trades (workspace_id, executed_at, data) VALUES (?, ?, ?)",
        (workspace_id, trade.executed_at, trade.model_dump_json()),
    )
    await conn.commit()


async def list_trades(workspace_id: str, limit: int = 50) -> list[TradeRecord]:
    conn = await get_connection()
    async with conn.execute(
        "SELECT data FROM trades WHERE workspace_id = ? ORDER BY executed_at DESC LIMIT ?",
        (workspace_id, limit),
    ) as cur:
        rows = await cur.fetchall()
        return [TradeRecord.model_validate_json(row["data"]) for row in rows]


async def insert_market_snapshot(
    workspace_id: str,
    market_profile: str,
    phase: str,
    data: dict[str, Any],
    captured_at: str | None = None,
) -> None:
    conn = await get_connection()
    ts = captured_at or utc_now_iso()
    await conn.execute(
        """
        INSERT INTO market_snapshots (workspace_id, market_profile, phase, captured_at, data)
        VALUES (?, ?, ?, ?, ?)
        """,
        (workspace_id, market_profile, phase, ts, json.dumps(data, ensure_ascii=False)),
    )
    await conn.commit()


async def upsert_account_snapshot(
    workspace_id: str,
    date: str,
    account_value: float,
    cash: float,
    market_value: float,
) -> None:
    conn = await get_connection()
    await conn.execute(
        """
        INSERT INTO account_snapshots (workspace_id, date, account_value, cash, market_value)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, date) DO UPDATE SET
            account_value = excluded.account_value,
            cash = excluded.cash,
            market_value = excluded.market_value
        """,
        (workspace_id, date, account_value, cash, market_value),
    )
    await conn.commit()


async def list_account_snapshots(workspace_id: str, days: int = 90) -> list[dict[str, Any]]:
    conn = await get_connection()
    async with conn.execute(
        """
        SELECT date, account_value, cash, market_value
        FROM account_snapshots
        WHERE workspace_id = ?
        ORDER BY date ASC
        LIMIT ?
        """,
        (workspace_id, days),
    ) as cur:
        rows = await cur.fetchall()
        return [{"date": r["date"], "account_value": r["account_value"], "cash": r["cash"], "market_value": r["market_value"]} for r in rows]


async def get_latest_market_snapshot(workspace_id: str) -> dict[str, Any] | None:
    conn = await get_connection()
    async with conn.execute(
        "SELECT data FROM market_snapshots WHERE workspace_id = ? ORDER BY captured_at DESC LIMIT 1",
        (workspace_id,),
    ) as cur:
        row = await cur.fetchone()
        if row is None:
            return None
        return json.loads(row["data"])
