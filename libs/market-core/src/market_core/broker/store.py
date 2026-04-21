"""YAML persistence for paper-trading state.

Local-first: TradingState + TradeRecord ledger live in plain YAML files
under a workspace directory. Pure I/O — no engine logic, no API calls.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from market_core.models import TradeRecord, TradingState

STATE_FILENAME = "state.yaml"
TRADES_FILENAME = "trades.yaml"


def _resolve(path: str | Path) -> Path:
    return Path(path).expanduser()


def load_state(path: str | Path) -> TradingState | None:
    p = _resolve(path)
    if not p.exists():
        return None
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return TradingState.model_validate(raw)


def save_state(path: str | Path, state: TradingState) -> Path:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(state.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return p


def load_trades(path: str | Path) -> list[TradeRecord]:
    p = _resolve(path)
    if not p.exists():
        return []
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    return [TradeRecord.model_validate(item) for item in raw]


def append_trade(path: str | Path, trade: TradeRecord) -> Path:
    p = _resolve(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load_trades(p)
    existing.append(trade)
    p.write_text(
        yaml.safe_dump(
            [t.model_dump(mode="json") for t in existing],
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return p


def workspace_paths(workspace_dir: str | Path) -> tuple[Path, Path]:
    """Return (state_path, trades_path) for a workspace directory."""
    base = _resolve(workspace_dir)
    return base / STATE_FILENAME, base / TRADES_FILENAME
