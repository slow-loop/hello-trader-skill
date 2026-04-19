"""Cattrade trading journal — JSONL log of opens/partials/closes.

Schema (one JSON object per line):
    {"event": "open",  "ts": ISO8601, "symbol": "ATUSDT",
     "qty": 15021.0, "entry_price": 0.1663,
     "cattrade": {"score": 65.01, "strength": 15.01, "concentration": 5.054,
                  "patterns": ["B"], "oi_usdt": 8800000}}
    {"event": "partial_close", "ts": ..., "symbol": "ATUSDT", "qty": 1500.0,
     "price": 0.18, "conviction": 0.80, "reason": "..."}
    {"event": "close", "ts": ..., "symbol": "ATUSDT", "qty": 13521.0,
     "price": 0.15, "reason": "pattern D"}
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("data/cattrade/journal.jsonl")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def append(entry: dict[str, Any], path: Path = DEFAULT_PATH) -> None:
    _ensure(path)
    with path.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def write_open(
    symbol: str,
    qty: float,
    entry_price: float,
    cattrade_score: float,
    cattrade_strength: float,
    cattrade_concentration: float,
    cattrade_patterns: list[str],
    cattrade_oi_usdt: float,
    path: Path = DEFAULT_PATH,
) -> None:
    append({
        "event": "open",
        "ts": _now(),
        "symbol": symbol,
        "qty": qty,
        "entry_price": entry_price,
        "cattrade": {
            "score": cattrade_score,
            "strength": cattrade_strength,
            "concentration": cattrade_concentration,
            "patterns": cattrade_patterns,
            "oi_usdt": cattrade_oi_usdt,
        },
    }, path)


def write_partial_close(
    symbol: str,
    qty: float,
    price: float,
    conviction: float,
    reason: str,
    path: Path = DEFAULT_PATH,
) -> None:
    append({
        "event": "partial_close",
        "ts": _now(),
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "conviction": conviction,
        "reason": reason,
    }, path)


def write_close(
    symbol: str,
    qty: float,
    price: float,
    reason: str,
    path: Path = DEFAULT_PATH,
) -> None:
    append({
        "event": "close",
        "ts": _now(),
        "symbol": symbol,
        "qty": qty,
        "price": price,
        "reason": reason,
    }, path)


def read_all(path: Path = DEFAULT_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def last_open(symbol: str, path: Path = DEFAULT_PATH) -> dict | None:
    """Return the most recent 'open' event for symbol, or None.

    Returns None if there's a later 'close' event after the last open
    (i.e. the position was fully closed since).
    """
    entries = read_all(path)
    last_open_idx = -1
    last_close_idx = -1
    for i, e in enumerate(entries):
        if e.get("symbol") != symbol:
            continue
        if e.get("event") == "open":
            last_open_idx = i
        elif e.get("event") == "close":
            last_close_idx = i
    if last_open_idx < 0:
        return None
    if last_close_idx > last_open_idx:
        return None
    return entries[last_open_idx]
