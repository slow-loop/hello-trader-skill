"""Cattrade signal pipeline (v2 — rankings-based).

**Source of truth: `排行榜快照` sheet** — contains all 536 contracts with:
  - `综合分` (composite score, authoritative)
  - `结构标签` (structure label: 大户领先做多 / 大户领先做空 / 多头共振 / ...)
  - Multi-window pct changes (5m/15m/1h/4h/1d/1w)
  - Data freshness score

This replaces the old TUI总览 approach that reconstructed a score from
top-N rankings per window. With rankings:
  - every held position always has a score (no more "absent")
  - Pattern D/B/E detection is a direct string match on 结构标签
  - conviction = current_综合分 / entry_综合分 is always well-defined
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger(__name__)

XLSX_URL_TMPL = "https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
TUI_SHEET = "TUI总览"
RANKINGS_SHEET = "排行榜快照"

# 结构标签 canonical values (from cattrade.futures_metrics)
LABEL_WHALE_LONG   = "大户领先做多"     # primary entry signal (Pattern B)
LABEL_WHALE_SHORT  = "大户领先做空"     # exit signal (Pattern D)
LABEL_BULL_SYNC    = "多头共振"         # bullish multi-window alignment
LABEL_BUY_LEAD     = "主动买盘领先"     # active buying pressure
LABEL_SELL_LEAD    = "主动卖盘领先"     # bearish — active selling pressure
LABEL_NEUTRAL      = "中性"
LABEL_CONFLICT     = "结构冲突"

BULLISH_LABELS   = {LABEL_WHALE_LONG, LABEL_BULL_SYNC, LABEL_BUY_LEAD}
BEARISH_LABELS   = {LABEL_WHALE_SHORT, LABEL_SELL_LEAD}


@dataclass
class CattradeCandidate:
    symbol: str                 # base ticker, e.g. "AT"
    score: float = 0.0          # 综合分
    rank: int = 0               # 排名
    label: str = ""             # 结构标签
    freshness: float = 0.0      # 数据新鲜度分
    oi_usdt: float = 0.0        # 当前持仓额
    direction: str = "long"     # "long" / "short" / "neutral" / "veto"
    patterns: list[str] = field(default_factory=list)  # synthesized: B / D / E
    reasons: list[str] = field(default_factory=list)
    changes: dict[str, float] = field(default_factory=dict)  # {"5m": -0.1, "1h": 0.5, ...}
    raw: dict[str, Any] = field(default_factory=dict)


# ── fetch ────────────────────────────────────────────────────────────────────

_SNAPSHOT_TS_RE = re.compile(r"快照时间\(UTC\)[，,]([^，,\r\n]+)")


def _extract_snapshot_ts(tui_csv: str) -> str | None:
    m = _SNAPSHOT_TS_RE.search(tui_csv)
    return m.group(1).strip() if m else None


def _sheet_rows(xlsx_bytes: bytes, sheet_name: str) -> list[tuple]:
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True, read_only=True)
    return list(wb[sheet_name].iter_rows(values_only=True))


def _rows_to_csv(rows: list[tuple]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    for row in rows:
        w.writerow(["" if c is None else c for c in row])
    return buf.getvalue()


def fetch_cattrade_xlsx(sheet_id: str, timeout_sec: int = 15) -> tuple[bytes, list[dict], str | None]:
    """Fetch the full workbook + parse 排行榜快照 into a list of row dicts.

    Returns (xlsx_bytes, rankings, snapshot_ts).
    """
    url = XLSX_URL_TMPL.format(sheet_id=sheet_id)
    resp = httpx.get(url, follow_redirects=True, timeout=timeout_sec)
    resp.raise_for_status()
    xlsx_bytes = resp.content

    # snapshot_ts from TUI sheet metadata row
    tui_rows = _sheet_rows(xlsx_bytes, TUI_SHEET)
    snapshot_ts = _extract_snapshot_ts(_rows_to_csv(tui_rows[:2]))

    rankings = _parse_rankings(xlsx_bytes)
    return xlsx_bytes, rankings, snapshot_ts


# ── parse 排行榜快照 ─────────────────────────────────────────────────────────

_PCT_RE = re.compile(r"^-?[\d.]+%$")


def _num(v: Any) -> float | None:
    """Coerce 综合分 / percentages / K/M/B suffixed numbers to float."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    # percentage
    if _PCT_RE.match(s):
        try:
            return float(s[:-1])
        except ValueError:
            return None
    # K/M/B suffix
    suffix = {"K": 1e3, "M": 1e6, "B": 1e9}
    if len(s) > 1 and s[-1] in suffix:
        try:
            return float(s[:-1].replace(",", "")) * suffix[s[-1]]
        except ValueError:
            pass
    try:
        return float(s.replace(",", "").lstrip("+"))
    except ValueError:
        return None


def _parse_rankings(xlsx_bytes: bytes) -> list[dict]:
    """Parse 排行榜快照 sheet. Rows 1-2 are banners, row 3 is header, rest is data."""
    rows = _sheet_rows(xlsx_bytes, RANKINGS_SHEET)
    if len(rows) < 4:
        return []
    header = [h for h in rows[2]]  # row index 2 = row 3
    out: list[dict] = []
    for raw in rows[3:]:
        if not raw or raw[1] in (None, ""):
            continue
        item = {}
        for h, v in zip(header, raw):
            if h:
                item[h] = v
        if item.get("代码"):
            out.append(item)
    return out


# ── scoring ──────────────────────────────────────────────────────────────────

def _build_candidate(row: dict) -> CattradeCandidate:
    sym = str(row.get("代码", "")).strip()
    score = _num(row.get("综合分")) or 0.0
    rank = int(_num(row.get("排名")) or 0)
    label = str(row.get("结构标签") or "").strip()
    freshness = _num(row.get("数据新鲜度分")) or 0.0
    oi = _num(row.get("当前持仓额")) or 0.0

    # pct changes across windows
    changes: dict[str, float] = {}
    for win in ("5m", "15m", "1h", "4h", "1d", "1w"):
        v = _num(row.get(f"{win}额变(%)"))
        if v is not None:
            changes[win] = v

    return CattradeCandidate(
        symbol=sym, score=score, rank=rank, label=label,
        freshness=freshness, oi_usdt=oi, changes=changes, raw=row,
    )


def _classify(cand: CattradeCandidate, cfg: dict) -> None:
    """Attach direction / patterns / reasons based on label + pumped filter."""
    label = cand.label
    veto = cfg.get("veto", {})
    pumped_1d_pct = float(veto.get("pumped_1d_pct", 50.0))
    pumped_1w_pct = float(veto.get("pumped_1w_pct", 100.0))

    # Exit signal: 大户领先做空 (Pattern D)
    if label == LABEL_WHALE_SHORT:
        cand.direction = "short"
        cand.patterns.append("D")
        cand.reasons.append("label=大户领先做空")
        return

    # Bearish (active selling lead) — treat as exit/skip for longs
    if label == LABEL_SELL_LEAD:
        cand.direction = "short"
        cand.patterns.append("SELL_LEAD")
        cand.reasons.append("label=主动卖盘领先")
        return

    # Pumped veto (Pattern E): already ran 1d+1w → don't chase
    d1 = cand.changes.get("1d")
    w1 = cand.changes.get("1w")
    if d1 is not None and w1 is not None and d1 > pumped_1d_pct and w1 > pumped_1w_pct:
        cand.direction = "veto"
        cand.patterns.append("E")
        cand.reasons.append(f"pumped 1d={d1:.0f}% 1w={w1:.0f}%")
        return

    # Bullish labels
    if label == LABEL_WHALE_LONG:
        cand.direction = "long"
        cand.patterns.append("B")
        cand.reasons.append("label=大户领先做多")
    elif label in (LABEL_BULL_SYNC, LABEL_BUY_LEAD):
        cand.direction = "long"
        cand.patterns.append("BULL")
        cand.reasons.append(f"label={label}")
    else:
        # 中性 / 结构冲突 — hold if held, don't enter
        cand.direction = "neutral"


def pick_cattrade(
    rankings: list[dict],
    cfg: dict[str, Any],
    include_symbols: set[str] | None = None,
) -> list[CattradeCandidate]:
    """Score + rank all 500+ contracts. Returns list sorted by score desc.

    - Every contract gets a CattradeCandidate (no more "absent").
    - Longs (direction=="long") above min_oi sorted by score.
    - include_symbols forces inclusion regardless of OI / direction filters,
      so callers can always look up held positions.
    """
    min_oi = cfg.get("filters", {}).get("min_oi_usdt", 5_000_000)
    min_freshness = cfg.get("filters", {}).get("min_freshness", 60.0)
    include_symbols = include_symbols or set()

    out: list[CattradeCandidate] = []
    for row in rankings:
        cand = _build_candidate(row)
        _classify(cand, cfg)
        forced = cand.symbol in include_symbols
        if not forced:
            if cand.freshness < min_freshness:
                continue
            if cand.oi_usdt and cand.oi_usdt < min_oi:
                continue
            if cand.direction != "long":
                continue
        out.append(cand)

    out.sort(key=lambda c: c.score, reverse=True)
    return out


# ── public API ───────────────────────────────────────────────────────────────

DEFAULT_CATTRADE_CFG: dict[str, Any] = {
    "veto": {
        "pumped_1d_pct": 50.0,   # 1d 额变 >50% AND
        "pumped_1w_pct": 100.0,  # 1w 额变 >100% → skip (already pumped)
    },
    "filters": {
        "min_oi_usdt": 5_000_000,
        "min_freshness": 60.0,
    },
}


def get_cattrade_scores(
    sheet_id: str,
    cfg: dict[str, Any] | None = None,
    timeout_sec: int = 15,
) -> dict[str, float]:
    """Fetch cattrade sheet, return {base_ticker: 综合分} for all bullish longs."""
    merged_cfg = {**DEFAULT_CATTRADE_CFG, **(cfg or {})}
    try:
        _, rankings, _ = fetch_cattrade_xlsx(sheet_id, timeout_sec=timeout_sec)
    except Exception as e:
        log.warning("cattrade fetch failed: %s", e)
        return {}
    cands = pick_cattrade(rankings, merged_cfg)
    return {c.symbol: c.score for c in cands}
