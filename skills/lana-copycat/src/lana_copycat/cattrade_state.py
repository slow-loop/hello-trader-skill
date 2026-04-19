"""Per-symbol tick state for cattrade daemon (persists across runs).

Current contents:
    {"ATUSDT": {"absent_streak": 2}}

absent_streak is used to debounce sheet-absence before trimming.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_PATH = Path("data/cattrade/state.json")


def load(path: Path = DEFAULT_PATH) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save(state: dict, path: Path = DEFAULT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def bump_absent(state: dict, symbol: str) -> int:
    s = state.setdefault(symbol, {})
    s["absent_streak"] = int(s.get("absent_streak", 0)) + 1
    return s["absent_streak"]


def reset_absent(state: dict, symbol: str) -> None:
    s = state.setdefault(symbol, {})
    s["absent_streak"] = 0


def drop(state: dict, symbol: str) -> None:
    state.pop(symbol, None)


def get_absent_streak(state: dict, symbol: str) -> int:
    return int(state.get(symbol, {}).get("absent_streak", 0))
