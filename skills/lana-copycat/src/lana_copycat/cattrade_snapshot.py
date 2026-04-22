"""Persistent snapshots of the cattrade Google Sheet.

Stores the full XLSX workbook (all 4 tabs: TUI总览 / 全市场统计 / 排行榜快照 / API)
for every distinct `快照时间(UTC)`, so we can
(a) replay/backtest later using any tab, and
(b) skip a tick when the source sheet hasn't refreshed (gsheet updates every 5 min).

Filename format: `{snapshot_ts}.xlsx` with `:` → `-` for filesystem safety.
The original ISO timestamp is also preserved inside the TUI sheet's metadata row.
"""

from __future__ import annotations

from pathlib import Path

DEFAULT_DIR = Path("data/cattrade/snapshots")


def _safe_name(snapshot_ts: str) -> str:
    return snapshot_ts.replace(":", "-") + ".xlsx"


def path_for(snapshot_ts: str, dir_: Path = DEFAULT_DIR) -> Path:
    return dir_ / _safe_name(snapshot_ts)


def exists(snapshot_ts: str, dir_: Path = DEFAULT_DIR) -> bool:
    return path_for(snapshot_ts, dir_).exists()


def save(snapshot_ts: str, xlsx_bytes: bytes, dir_: Path = DEFAULT_DIR) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = path_for(snapshot_ts, dir_)
    p.write_bytes(xlsx_bytes)
    return p


def count(dir_: Path = DEFAULT_DIR) -> int:
    if not dir_.exists():
        return 0
    return sum(1 for _ in dir_.glob("*.xlsx"))
