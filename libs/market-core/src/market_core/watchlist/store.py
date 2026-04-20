"""YAML persistence for watchlists.

Local-first: WatchlistConfig lives in plain YAML. Pure I/O — evaluation
logic is in engine.py.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from market_core.models import WatchlistConfig, WatchlistItem


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser()


def load_watchlist(path: str | Path) -> WatchlistConfig:
    p = _resolve(path)
    if not p.exists():
        return WatchlistConfig()
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    if isinstance(raw, dict):
        items = raw.get("items") or []
    elif isinstance(raw, list):
        items = raw
    else:
        raise ValueError(f"watchlist must be list or mapping: {p}")
    return WatchlistConfig(items=[WatchlistItem.model_validate(item) for item in items])


def save_watchlist(path: str | Path, watchlist: WatchlistConfig) -> Path:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [item.model_dump(mode="json", exclude_none=True) for item in watchlist.items]
    p.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    return p


def delete_watchlist_item(path: str | Path, symbol: str) -> WatchlistConfig:
    current = load_watchlist(path)
    normalized = symbol.upper()
    items = [item for item in current.items if item.symbol.upper() != normalized]
    if len(items) == len(current.items):
        raise KeyError(symbol)
    updated = WatchlistConfig(items=items)
    save_watchlist(path, updated)
    return updated


def upsert_watchlist_item(path: str | Path, item: WatchlistItem) -> WatchlistConfig:
    current = load_watchlist(path)
    normalized_symbol = item.symbol.upper()
    items: list[WatchlistItem] = []
    replaced = False
    for existing in current.items:
        if existing.symbol.upper() == normalized_symbol:
            items.append(item)
            replaced = True
        else:
            items.append(existing)
    if not replaced:
        items.append(item)
    updated = WatchlistConfig(items=items)
    save_watchlist(path, updated)
    return updated
