"""Fetch + parse the cattrade public Google Sheet.

The sheet is a single tab with 11 ranking sections stacked vertically.
Each section starts with a header row whose first column is the section title,
followed by Top-7 data rows.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Iterable

import httpx

CSV_URL_TMPL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

# Section titles → section key (stable identifier)
SECTIONS: dict[str, str] = {
    "5m 异动榜": "move_5m",
    "15m 异动榜": "move_15m",
    "1h 异动榜": "move_1h",
    "4h 异动榜": "move_4h",
    "1d 异动榜": "move_1d",
    "1w 异动榜": "move_1w",
    "多窗口持仓量榜": "multi_volume",
    "多窗口持仓额榜": "multi_amount",
    "市场份额相对榜": "market_share",
    "波动区间榜": "range",
    "结构分歧榜": "structure",
}


@dataclass
class Snapshot:
    """A parsed sheet snapshot."""

    export_time: str = ""
    snapshot_time: str = ""
    latency: str = ""
    schema: str = ""
    sections: dict[str, list[dict]] = field(default_factory=dict)

    def section(self, key: str) -> list[dict]:
        return self.sections.get(key, [])


def fetch_csv(sheet_id: str, timeout_sec: int = 15) -> str:
    url = CSV_URL_TMPL.format(sheet_id=sheet_id)
    resp = httpx.get(url, follow_redirects=True, timeout=timeout_sec)
    resp.raise_for_status()
    return resp.text


def parse_csv(text: str) -> Snapshot:
    snap = Snapshot()
    rows = list(csv.reader(io.StringIO(text)))

    # Metadata line (has "数据源=cattrade" somewhere in row[0])
    for row in rows:
        if row and "数据源=cattrade" in row[0]:
            snap.export_time, snap.snapshot_time, snap.latency, snap.schema = (
                _parse_meta(row[0])
            )
            break

    # Walk sections
    current_key: str | None = None
    current_header: list[str] = []
    for row in rows:
        if not row:
            continue
        first = row[0].strip() if row[0] else ""
        if first in SECTIONS:
            current_key = SECTIONS[first]
            # Header is: [section_title, col1, col2, ...]; real columns start at index 1
            current_header = [c.strip() for c in row[1:]]
            snap.sections[current_key] = []
            continue
        if current_key and first == "" and len(row) > 1 and row[1].strip():
            # Data row: first col empty, index col at 1
            values = [c.strip() for c in row[1:]]
            item = _zip_row(current_header, values)
            if item.get("合约代码"):
                snap.sections[current_key].append(item)

    return snap


def _parse_meta(meta: str) -> tuple[str, str, str, str]:
    parts = [p.strip() for p in meta.split("|")]
    kv: dict[str, str] = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            kv[k.strip()] = v.strip()
    return (
        kv.get("导出时间(UTC+8)", ""),
        kv.get("快照时间", ""),
        kv.get("延迟", ""),
        kv.get("schema", ""),
    )


def _zip_row(header: Iterable[str], values: Iterable[str]) -> dict:
    out: dict = {}
    for h, v in zip(header, values):
        if not h:
            continue
        out[h] = _coerce(h, v)
    return out


# Fields we never coerce (keep as str)
_STRING_FIELDS = {"合约代码", "方向一致性", "结构形态", "量方向", "额方向"}


def _coerce(key: str, v: str) -> object:
    if v == "" or v is None:
        return None
    if key in _STRING_FIELDS:
        return v
    # Percentage
    if v.endswith("%"):
        try:
            return float(v[:-1])
        except ValueError:
            return v
    # Suffix units: K / M / B
    suffix_map = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    if len(v) > 1 and v[-1] in suffix_map:
        try:
            return float(v[:-1]) * suffix_map[v[-1]]
        except ValueError:
            pass
    # Signed number
    try:
        return float(v.replace(",", "").lstrip("+"))
    except ValueError:
        return v


def load_snapshot(sheet_id: str, timeout_sec: int = 15) -> Snapshot:
    return parse_csv(fetch_csv(sheet_id, timeout_sec))
