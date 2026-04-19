"""Detect patterns and score candidates across the 11 cattrade rankings.

Pattern taxonomy (see design doc in session history):
    A = early momentum (long)
    B = top-trader stealth accumulation (long, strongest Lana-style edge)
    C = fake breakout (veto)
    D = top-trader stealth distribution (short)
    E = already pumped (veto)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sheet import Snapshot

LONG_STRUCT = "大户领先做多"
SHORT_STRUCT_FORMS = {"大户领先做空", "主动买领先空"}
UP_DIRECTIONS = {"同向上", "上拐"}
DOWN_DIRECTIONS = {"同向下", "下拐"}


@dataclass
class Candidate:
    symbol: str
    score: float = 0.0
    direction: str = "long"          # "long" / "short" / "veto"
    patterns: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    oi_usdt: float = 0.0
    raw: dict[str, dict] = field(default_factory=dict)  # section_key → row


def build_candidates(snap: Snapshot) -> dict[str, Candidate]:
    """Collect every symbol that appears anywhere, with per-section rows attached."""
    pool: dict[str, Candidate] = {}
    for section_key, rows in snap.sections.items():
        for row in rows:
            sym = row.get("合约代码")
            if not sym:
                continue
            cand = pool.setdefault(sym, Candidate(symbol=sym))
            cand.raw[section_key] = row
            oi = row.get("现持仓额")
            if isinstance(oi, (int, float)) and oi > cand.oi_usdt:
                cand.oi_usdt = float(oi)
    return pool


def _rank_in(cand: Candidate, section_key: str) -> int | None:
    row = cand.raw.get(section_key)
    if not row:
        return None
    r = row.get("量排名") or row.get("序号")
    if isinstance(r, (int, float)):
        return int(r)
    # Rows are stored in order; index is 1-based position
    return None


def score_candidate(cand: Candidate, cfg: dict[str, Any]) -> Candidate:
    score = 0.0

    # --- Veto checks first ---
    # Pattern E: already pumped (top of 1d AND 1w)
    r1d = cand.raw.get("move_1d", {}).get("量排名")
    r1w = cand.raw.get("move_1w", {}).get("量排名")
    if (
        isinstance(r1d, (int, float))
        and isinstance(r1w, (int, float))
        and r1d <= cfg["veto"]["pumped_1d_rank_max"]
        and r1w <= cfg["veto"]["pumped_1w_rank_max"]
    ):
        cand.direction = "veto"
        cand.patterns.append("E")
        cand.reasons.append(f"pumped: 1d#{int(r1d)} + 1w#{int(r1w)}")
        cand.score = -999
        return cand

    # Pattern C: fake short-term spike (5m top, no 1h follow-through)
    r5m = cand.raw.get("move_5m", {}).get("量排名")
    row_multi_vol = cand.raw.get("multi_volume") or {}
    short_impact = row_multi_vol.get("短时冲击占比")
    if (
        isinstance(r5m, (int, float))
        and r5m <= 3
        and "move_1h" not in cand.raw
        and isinstance(short_impact, (int, float))
        and short_impact > cfg["veto"]["short_impact_threshold"]
    ):
        cand.direction = "veto"
        cand.patterns.append("C")
        cand.reasons.append(f"fake spike: 5m#{int(r5m)} no 1h, impact={short_impact}")
        cand.score = -999
        return cand

    # --- Pattern B: top-trader stealth long ---
    struct_row = cand.raw.get("structure")
    if struct_row:
        form = struct_row.get("结构形态")
        strength = struct_row.get("结构强度") or 0
        if form == LONG_STRUCT and isinstance(strength, (int, float)) and strength > 10:
            score += cfg["scoring"]["pattern_b_base"] + float(strength)
            cand.patterns.append("B")
            cand.reasons.append(f"大户领先做多 strength={strength}")
            concentration = struct_row.get("大户集中度") or 0
            if isinstance(concentration, (int, float)) and concentration > 2:
                score += 10
                cand.reasons.append(f"concentration={concentration}")

    # --- Pattern D: top-trader short ---
    if struct_row:
        form = struct_row.get("结构形态")
        strength = struct_row.get("结构强度") or 0
        if form in SHORT_STRUCT_FORMS and isinstance(strength, (int, float)) and strength > 10:
            cand.direction = "short"
            cand.patterns.append("D")
            cand.reasons.append(f"{form} strength={strength}")
            # Short score is tracked separately (negative score = short candidate)
            score -= 20 + float(strength)

    # --- Pattern A: early momentum (long) ---
    in_15m = "move_15m" in cand.raw
    in_1h = "move_1h" in cand.raw
    direction_key = None
    if "multi_volume" in cand.raw:
        direction_key = cand.raw["multi_volume"].get("方向一致性")
    if in_15m and direction_key in UP_DIRECTIONS:
        # Check not already at top of 1d (追高)
        r1d = cand.raw.get("move_1d", {}).get("量排名")
        if not (isinstance(r1d, (int, float)) and r1d <= 3):
            score += 20
            cand.patterns.append("A")
            cand.reasons.append(f"early momentum 15m + {direction_key}")

    # --- Direction consistency signal ---
    if direction_key in UP_DIRECTIONS:
        score += cfg["scoring"]["same_up_bonus"]
    elif direction_key in DOWN_DIRECTIONS and cand.direction != "short":
        score -= cfg["scoring"]["down_penalty"]

    # --- Cross-section breadth ---
    short_hits = sum(1 for k in ("move_15m", "move_1h") if k in cand.raw)
    mid_hits = sum(1 for k in ("multi_volume", "multi_amount") if k in cand.raw)
    score += short_hits * cfg["scoring"]["short_rank_weight"]
    score += mid_hits * cfg["scoring"]["mid_rank_weight"]

    # --- Volume Z score sweet spot ---
    for key in ("move_15m", "move_1h"):
        row = cand.raw.get(key)
        if not row:
            continue
        z = row.get("量Z分数")
        if not isinstance(z, (int, float)):
            continue
        lo, hi = cfg["scoring"]["vol_z_sweet_spot"]
        if lo < z < hi:
            score += 10
            cand.reasons.append(f"{key} vol_z={z:.2f} (sweet)")
        elif z > cfg["scoring"]["vol_z_overheated"]:
            score -= 15
            cand.reasons.append(f"{key} vol_z={z:.2f} (overheated)")
        break  # only apply once

    # --- Determine final direction ---
    if cand.direction == "long" and score < 0 and "D" in cand.patterns:
        cand.direction = "short"

    cand.score = round(score, 2)
    return cand


def pick(snap: Snapshot, cfg: dict[str, Any], top_n: int = 10) -> list[Candidate]:
    pool = build_candidates(snap)
    min_oi = cfg["filters"]["min_oi_usdt"]
    out: list[Candidate] = []
    for cand in pool.values():
        if cand.oi_usdt and cand.oi_usdt < min_oi:
            continue
        score_candidate(cand, cfg)
        if cand.direction == "veto":
            continue
        out.append(cand)

    # Sort: shorts (negative score) at bottom; longs descending by score
    longs = sorted(
        [c for c in out if c.direction == "long" and c.score > 0],
        key=lambda c: c.score,
        reverse=True,
    )
    shorts = sorted(
        [c for c in out if c.direction == "short"],
        key=lambda c: c.score,
    )
    return (longs + shorts)[:top_n]
