"""cattrade public Google Sheet signal.

Fetches cattrade's 11 ranking sections and extracts "大戶領先做多" (Pattern B)
stealth accumulation signals — the most direct MM-positioning edge in the sheet.

Exposes ``get_cattrade_scores()`` returning ``{base_ticker: score}`` for merging
into the main scoring pipeline.
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)

CSV_URL_TMPL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

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

LONG_STRUCT = "大户领先做多"
SHORT_STRUCT_FORMS = {"大户领先做空", "主动买领先空"}
UP_DIRECTIONS = {"同向上", "上拐"}
DOWN_DIRECTIONS = {"同向下", "下拐"}
_STRING_FIELDS = {"合约代码", "方向一致性", "结构形态", "量方向", "额方向"}


@dataclass
class CattradeCandidate:
    symbol: str  # e.g. "AT" (base ticker)
    score: float = 0.0
    direction: str = "long"
    patterns: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    oi_usdt: float = 0.0
    raw: dict[str, dict] = field(default_factory=dict)


# ── fetch + parse ─────────────────────────────────────────────────────────────

def _coerce(key: str, v: str) -> object:
    if v == "" or v is None:
        return None
    if key in _STRING_FIELDS:
        return v
    if v.endswith("%"):
        try:
            return float(v[:-1])
        except ValueError:
            return v
    suffix_map = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}
    if len(v) > 1 and v[-1] in suffix_map:
        try:
            return float(v[:-1]) * suffix_map[v[-1]]
        except ValueError:
            pass
    try:
        return float(v.replace(",", "").lstrip("+"))
    except ValueError:
        return v


def _parse(text: str) -> dict[str, list[dict]]:
    rows = list(csv.reader(io.StringIO(text)))
    sections: dict[str, list[dict]] = {}
    current_key: str | None = None
    current_header: list[str] = []
    for row in rows:
        if not row:
            continue
        first = row[0].strip() if row[0] else ""
        if first in SECTIONS:
            current_key = SECTIONS[first]
            current_header = [c.strip() for c in row[1:]]
            sections[current_key] = []
            continue
        if current_key and first == "" and len(row) > 1 and row[1].strip():
            values = [c.strip() for c in row[1:]]
            item: dict = {}
            for h, v in zip(current_header, values):
                if h:
                    item[h] = _coerce(h, v)
            if item.get("合约代码"):
                sections[current_key].append(item)
    return sections


def fetch_cattrade_sections(sheet_id: str, timeout_sec: int = 15) -> dict[str, list[dict]]:
    url = CSV_URL_TMPL.format(sheet_id=sheet_id)
    resp = httpx.get(url, follow_redirects=True, timeout=timeout_sec)
    resp.raise_for_status()
    return _parse(resp.text)


# ── scoring ───────────────────────────────────────────────────────────────────

def _build_candidates(sections: dict[str, list[dict]]) -> dict[str, CattradeCandidate]:
    pool: dict[str, CattradeCandidate] = {}
    for section_key, rows in sections.items():
        for row in rows:
            sym = row.get("合约代码")
            if not sym:
                continue
            cand = pool.setdefault(sym, CattradeCandidate(symbol=sym))
            cand.raw[section_key] = row
            oi = row.get("现持仓额")
            if isinstance(oi, (int, float)) and oi > cand.oi_usdt:
                cand.oi_usdt = float(oi)
    return pool


def _score(cand: CattradeCandidate, cfg: dict[str, Any]) -> None:
    score = 0.0
    scoring = cfg.get("scoring", {})
    veto = cfg.get("veto", {})

    # Veto: Pattern E (already pumped)
    r1d = cand.raw.get("move_1d", {}).get("量排名")
    r1w = cand.raw.get("move_1w", {}).get("量排名")
    if (
        isinstance(r1d, (int, float))
        and isinstance(r1w, (int, float))
        and r1d <= veto.get("pumped_1d_rank_max", 3)
        and r1w <= veto.get("pumped_1w_rank_max", 3)
    ):
        cand.direction = "veto"
        cand.patterns.append("E")
        cand.reasons.append(f"pumped: 1d#{int(r1d)} + 1w#{int(r1w)}")
        cand.score = -999
        return

    # Veto: Pattern C (fake spike)
    r5m = cand.raw.get("move_5m", {}).get("量排名")
    row_mv = cand.raw.get("multi_volume") or {}
    short_impact = row_mv.get("短时冲击占比")
    if (
        isinstance(r5m, (int, float))
        and r5m <= 3
        and "move_1h" not in cand.raw
        and isinstance(short_impact, (int, float))
        and short_impact > veto.get("short_impact_threshold", 1.0)
    ):
        cand.direction = "veto"
        cand.patterns.append("C")
        cand.score = -999
        return

    # Pattern B: top-trader stealth long
    struct_row = cand.raw.get("structure")
    if struct_row:
        form = struct_row.get("结构形态")
        strength = struct_row.get("结构强度") or 0
        if form == LONG_STRUCT and isinstance(strength, (int, float)) and strength > 10:
            score += scoring.get("pattern_b_base", 40) + float(strength)
            cand.patterns.append("B")
            cand.reasons.append(f"大户领先做多 strength={strength}")
            concentration = struct_row.get("大户集中度") or 0
            if isinstance(concentration, (int, float)) and concentration > 2:
                score += 10
                cand.reasons.append(f"concentration={concentration}")

        if form in SHORT_STRUCT_FORMS and isinstance(strength, (int, float)) and strength > 10:
            cand.direction = "short"
            cand.patterns.append("D")
            score -= 20 + float(strength)

    # Pattern A: early momentum
    in_15m = "move_15m" in cand.raw
    direction_key = None
    if "multi_volume" in cand.raw:
        direction_key = cand.raw["multi_volume"].get("方向一致性")
    if in_15m and direction_key in UP_DIRECTIONS:
        r1d_check = cand.raw.get("move_1d", {}).get("量排名")
        if not (isinstance(r1d_check, (int, float)) and r1d_check <= 3):
            score += 20
            cand.patterns.append("A")
            cand.reasons.append(f"early momentum 15m + {direction_key}")

    if direction_key in UP_DIRECTIONS:
        score += scoring.get("same_up_bonus", 15)
    elif direction_key in DOWN_DIRECTIONS and cand.direction != "short":
        score -= scoring.get("down_penalty", 10)

    # Cross-section breadth
    short_hits = sum(1 for k in ("move_15m", "move_1h") if k in cand.raw)
    mid_hits = sum(1 for k in ("multi_volume", "multi_amount") if k in cand.raw)
    score += short_hits * scoring.get("short_rank_weight", 5)
    score += mid_hits * scoring.get("mid_rank_weight", 8)

    # Volume Z sweet spot
    for key in ("move_15m", "move_1h"):
        row = cand.raw.get(key)
        if not row:
            continue
        z = row.get("量Z分数")
        if not isinstance(z, (int, float)):
            continue
        lo, hi = scoring.get("vol_z_sweet_spot", [1.5, 3.0])
        if lo < z < hi:
            score += 10
        elif z > scoring.get("vol_z_overheated", 5.0):
            score -= 15
        break

    cand.score = round(score, 2)


def pick_cattrade(
    sections: dict[str, list[dict]],
    cfg: dict[str, Any],
) -> list[CattradeCandidate]:
    """Filter + score + rank. Returns longs only, positive-scored."""
    pool = _build_candidates(sections)
    min_oi = cfg.get("filters", {}).get("min_oi_usdt", 5_000_000)
    out: list[CattradeCandidate] = []
    for cand in pool.values():
        if cand.oi_usdt and cand.oi_usdt < min_oi:
            continue
        _score(cand, cfg)
        if cand.direction == "veto":
            continue
        if cand.direction == "long" and cand.score > 0:
            out.append(cand)
    out.sort(key=lambda c: c.score, reverse=True)
    return out


# ── public API ────────────────────────────────────────────────────────────────

DEFAULT_CATTRADE_CFG: dict[str, Any] = {
    "scoring": {
        "pattern_b_base": 40,
        "same_up_bonus": 15,
        "down_penalty": 10,
        "short_rank_weight": 5,
        "mid_rank_weight": 8,
        "vol_z_sweet_spot": [1.5, 3.0],
        "vol_z_overheated": 5.0,
    },
    "veto": {
        "pumped_1d_rank_max": 3,
        "pumped_1w_rank_max": 3,
        "short_impact_threshold": 1.0,
    },
    "filters": {"min_oi_usdt": 5_000_000},
}


def get_cattrade_scores(
    sheet_id: str,
    cfg: dict[str, Any] | None = None,
    timeout_sec: int = 15,
) -> dict[str, float]:
    """Fetch cattrade sheet, pick long candidates, return ``{base_ticker: score}``.

    Returns empty dict on any failure (network, parse, empty sheet).
    """
    merged_cfg = {**DEFAULT_CATTRADE_CFG, **(cfg or {})}
    try:
        sections = fetch_cattrade_sections(sheet_id, timeout_sec=timeout_sec)
    except Exception as e:
        log.warning("cattrade fetch failed: %s", e)
        return {}
    cands = pick_cattrade(sections, merged_cfg)
    return {c.symbol: c.score for c in cands}
