"""CRUD operations on the strategy registry (data/strategies/registry.yaml)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from skill_crypto_trader.journal.helpers import get_registry_path

VALID_STATUSES = ("candidate", "validated", "active", "deployed", "retired")


def _load_raw(path: Path | None = None) -> dict:
    path = path or get_registry_path()
    if not path.exists():
        return {"strategies": []}
    return yaml.safe_load(path.read_text()) or {"strategies": []}


def _save(data: dict, path: Path | None = None) -> None:
    path = path or get_registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))


def load_registry(path: Path | None = None) -> list[dict]:
    return _load_raw(path).get("strategies", [])


def save_registry(entries: list[dict], path: Path | None = None) -> None:
    _save({"strategies": entries}, path)


def get_strategy(name: str) -> dict | None:
    for s in load_registry():
        if s["name"] == name:
            return s
    return None


def add_strategy(
    name: str,
    *,
    regime: str = "",
    description: str = "",
    strategy_file: str = "",
    pairs: list[str] | None = None,
    timeframe: str = "1h",
) -> dict:
    entries = load_registry()
    if any(s["name"] == name for s in entries):
        raise ValueError(f"Strategy '{name}' already exists")
    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "name": name,
        "status": "candidate",
        "regime": regime,
        "description": description,
        "strategy_file": strategy_file,
        "pairs": pairs or ["BTC/USDT"],
        "timeframe": timeframe,
        "created_at": now,
        "updated_at": now,
        "backtest_results": [],
        "walk_forward": [],
        "decay_checks": [],
    }
    entries.append(entry)
    save_registry(entries)
    return entry


def update_strategy(name: str, updates: dict) -> dict:
    entries = load_registry()
    for s in entries:
        if s["name"] == name:
            s.update(updates)
            s["updated_at"] = datetime.now(timezone.utc).isoformat()
            save_registry(entries)
            return s
    raise ValueError(f"Strategy '{name}' not found")


def promote(name: str) -> dict:
    s = get_strategy(name)
    if not s:
        raise ValueError(f"Strategy '{name}' not found")
    flow = {"candidate": "validated", "validated": "active"}
    current = s["status"]
    if current not in flow:
        raise ValueError(f"Cannot promote from '{current}'")
    return update_strategy(name, {"status": flow[current]})


def retire(name: str) -> dict:
    s = get_strategy(name)
    if not s:
        raise ValueError(f"Strategy '{name}' not found")
    if s["status"] == "retired":
        raise ValueError(f"Strategy '{name}' already retired")
    # Move file to archive/
    from skill_crypto_trader.journal.helpers import get_strategy_dir, get_data_dir

    src = get_strategy_dir() / s.get("strategy_file", "")
    if src.exists():
        archive = get_data_dir() / "strategies" / "archive"
        archive.mkdir(parents=True, exist_ok=True)
        src.rename(archive / src.name)
    return update_strategy(name, {"status": "retired"})


def list_by_status(status: str) -> list[dict]:
    return [s for s in load_registry() if s["status"] == status]


def record_backtest(name: str, result: dict) -> dict:
    s = get_strategy(name)
    if not s:
        raise ValueError(f"Strategy '{name}' not found")
    entries = load_registry()
    for e in entries:
        if e["name"] == name:
            e["backtest_results"].append(result)
            e["updated_at"] = datetime.now(timezone.utc).isoformat()
            break
    save_registry(entries)
    return e
