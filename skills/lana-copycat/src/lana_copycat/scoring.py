"""Combine Square sentiment + OI + gainers into a ranked candidate list."""

from __future__ import annotations

from dataclasses import dataclass

from .signals.binance_market import TickerSignal


@dataclass
class Candidate:
    symbol: str             # e.g. "ETHUSDT"
    base: str               # e.g. "ETH"
    score: float
    square_rank: float      # normalised 0-1 (1 = most mentioned)
    oi_rank: float          # normalised 0-1 (1 = highest OI ratio)
    gainers_rank: float     # normalised 0-1 (1 = top gainer)
    price_change_pct: float
    oi_ratio: float

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 4),
            "square_rank": round(self.square_rank, 3),
            "oi_rank": round(self.oi_rank, 3),
            "gainers_rank": round(self.gainers_rank, 3),
            "price_change_pct": round(self.price_change_pct, 2),
            "oi_ratio": round(self.oi_ratio, 2),
        }


def _normalise(values: list[float]) -> list[float]:
    if not values:
        return []
    mn, mx = min(values), max(values)
    if mx == mn:
        return [1.0] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def score_candidates(
    square_counts: dict[str, int],
    market_signals: list[TickerSignal],
    w_square: float = 0.4,
    w_oi: float = 0.35,
    w_gainers: float = 0.25,
    top_n: int = 5,
) -> list[Candidate]:
    """
    Merge Square mentions with market signals.

    Only symbols present in BOTH Square counts AND market_signals are scored —
    this ensures we're only looking at coins people are actively talking about
    AND that are moving on Binance Futures.
    """
    # build lookup: base ticker → TickerSignal
    signal_map: dict[str, TickerSignal] = {}
    for ts in market_signals:
        base = ts.symbol.removesuffix("USDT")
        signal_map[base] = ts

    # intersect
    candidates_raw = []
    for base, count in square_counts.items():
        if base in signal_map:
            candidates_raw.append((base, count, signal_map[base]))

    if not candidates_raw:
        return []

    sq_counts = [c for _, c, _ in candidates_raw]
    oi_ratios = [ts.oi_ratio for _, _, ts in candidates_raw]
    price_chgs = [ts.price_change_pct for _, _, ts in candidates_raw]

    sq_norm = _normalise(sq_counts)
    oi_norm = _normalise(oi_ratios)
    gn_norm = _normalise(price_chgs)

    results = []
    for i, (base, count, ts) in enumerate(candidates_raw):
        score = w_square * sq_norm[i] + w_oi * oi_norm[i] + w_gainers * gn_norm[i]
        results.append(Candidate(
            symbol=ts.symbol,
            base=base,
            score=score,
            square_rank=sq_norm[i],
            oi_rank=oi_norm[i],
            gainers_rank=gn_norm[i],
            price_change_pct=ts.price_change_pct,
            oi_ratio=ts.oi_ratio,
        ))

    results.sort(key=lambda c: c.score, reverse=True)
    return results[:top_n]
