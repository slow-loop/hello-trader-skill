"""Append-only event log for tw-trader.

Records agent actions (trades, exit triggers, ...) as JSONL so that past
decisions can be audited or replayed even after state.yaml is overwritten.

One line per event: {"ts": ISO8601, "type": str, "payload": {...}}.
Writes are append-only with fsync; callers must tolerate best-effort
ordering on concurrent access (single-user CLI in practice).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

SKILL_ROOT = Path(__file__).resolve().parents[2]
EVENTS_SUBPATH = "data/account/events.jsonl"


def workspace_root() -> Path:
    env = os.getenv("TW_TRADER_ROOT")
    return Path(env).expanduser() if env else SKILL_ROOT


def events_path() -> Path:
    return workspace_root() / EVENTS_SUBPATH


def append_event(type: str, payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "type": type,
        "payload": payload,
    }
    path = events_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
    return record


def read_events(
    *,
    limit: int | None = None,
    types: Iterable[str] | None = None,
    since: str | None = None,
) -> list[dict[str, Any]]:
    path = events_path()
    if not path.exists():
        return []
    type_set = set(types) if types else None
    records: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if type_set and record.get("type") not in type_set:
                continue
            if since and record.get("ts", "") < since:
                continue
            records.append(record)
    if limit is not None:
        records = records[-limit:]
    return records
