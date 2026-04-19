from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import aiosqlite

DB_PATH = Path(os.environ.get("BACKEND3_DB", Path(__file__).resolve().parents[2] / "data" / "backend3.db"))

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  token TEXT UNIQUE NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  type TEXT NOT NULL,
  payload TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_agent_ts ON events(agent_id, ts);

CREATE TABLE IF NOT EXISTS journals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  entry_type TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  metadata TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_journals_agent_date ON journals(agent_id, date);

CREATE TABLE IF NOT EXISTS docs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  path TEXT NOT NULL,
  body TEXT NOT NULL,
  metadata TEXT NOT NULL DEFAULT '{}',
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_docs_path ON docs(agent_id, path, version);

CREATE TABLE IF NOT EXISTS watchlist_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  thesis TEXT,
  status TEXT NOT NULL DEFAULT 'active',
  metadata TEXT NOT NULL DEFAULT '{}',
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(agent_id, symbol)
);

CREATE TABLE IF NOT EXISTS operations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  price REAL NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed',
  reason TEXT NOT NULL,
  rejected_reason TEXT,
  metadata TEXT NOT NULL DEFAULT '{}',
  proposed_at TEXT NOT NULL DEFAULT (datetime('now')),
  executed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_operations_agent_status ON operations(agent_id, status);

CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  operation_id INTEGER NOT NULL,
  agent_id INTEGER NOT NULL,
  symbol TEXT NOT NULL,
  side TEXT NOT NULL,
  qty REAL NOT NULL,
  fill_price REAL NOT NULL,
  fees REAL NOT NULL DEFAULT 0,
  pnl REAL,
  executed_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_trades_agent ON trades(agent_id, executed_at);

CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  source TEXT,
  ts TEXT NOT NULL DEFAULT (datetime('now')),
  params TEXT NOT NULL DEFAULT '{}',
  summary TEXT NOT NULL DEFAULT '{}',
  payload TEXT
);
CREATE INDEX IF NOT EXISTS idx_snapshots_kind ON snapshots(agent_id, kind, ts);
"""

_conn: aiosqlite.Connection | None = None


async def get_connection() -> aiosqlite.Connection:
    global _conn
    if _conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.executescript(SCHEMA_SQL)
        await _conn.commit()
    return _conn


async def close_connection() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None


def row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    d = dict(row)
    for k in ("metadata", "payload", "params", "summary"):
        if k in d and isinstance(d[k], str) and d[k]:
            try:
                d[k] = json.loads(d[k])
            except json.JSONDecodeError:
                pass
    return d


def dumps(x: Any) -> str:
    return json.dumps(x or {}, ensure_ascii=False)


async def log_event(conn: aiosqlite.Connection, agent_id: int, type_: str, payload: dict) -> None:
    await conn.execute(
        "INSERT INTO events (agent_id, type, payload) VALUES (?, ?, ?)",
        (agent_id, type_, dumps(payload)),
    )
