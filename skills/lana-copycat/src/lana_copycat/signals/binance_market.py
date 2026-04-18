"""Binance Futures public REST signals: 24h gainers + OI momentum."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx

FUTURES_BASE = "https://fapi.binance.com"
# OI history uses production endpoint even when testnet trading is on —
# testnet doesn't carry real OI data.


@dataclass
class TickerSignal:
    symbol: str
    price_change_pct: float     # 24h price change %
    volume_usdt: float          # 24h quote volume
    oi_change_pct: float = 0.0  # 48h OI change %
    oi_ratio: float = 0.0       # oi_change_pct / |price_change_pct|  (momentum divergence)


async def fetch_top_gainers(n: int = 20, client: httpx.AsyncClient | None = None) -> list[TickerSignal]:
    """Return top-n USDT-M futures by 24h price gain, filtering out tiny volume."""
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=10)

    try:
        resp = await client.get(f"{FUTURES_BASE}/fapi/v1/ticker/24hr")
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own_client:
            await client.aclose()

    tickers = [
        TickerSignal(
            symbol=t["symbol"],
            price_change_pct=float(t["priceChangePercent"]),
            volume_usdt=float(t["quoteVolume"]),
        )
        for t in data
        if t["symbol"].endswith("USDT") and float(t["quoteVolume"]) > 1_000_000
    ]
    tickers.sort(key=lambda x: x.price_change_pct, reverse=True)
    return tickers[:n]


async def fetch_oi_momentum(
    symbols: list[str],
    window_hours: int = 48,
    client: httpx.AsyncClient | None = None,
) -> dict[str, tuple[float, float]]:
    """
    For each symbol return (oi_change_pct, oi_ratio).
    oi_ratio = oi_change_pct / max(|price_change_pct|, 1)  — high ratio means
    OI surged but price hasn't reacted yet (Lana's edge).
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=15)

    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = int((datetime.now(timezone.utc) - timedelta(hours=window_hours)).timestamp() * 1000)
    result: dict[str, tuple[float, float]] = {}

    async def _fetch_one(sym: str) -> None:
        try:
            resp = await client.get(
                f"{FUTURES_BASE}/futures/data/openInterestHist",
                params={"symbol": sym, "period": "4h", "limit": window_hours // 4},
            )
            resp.raise_for_status()
            rows = resp.json()
            if len(rows) < 2:
                return
            first_oi = float(rows[0]["sumOpenInterestValue"])
            last_oi = float(rows[-1]["sumOpenInterestValue"])
            if first_oi == 0:
                return
            oi_chg = (last_oi - first_oi) / first_oi * 100
            result[sym] = (oi_chg, 0.0)  # ratio filled in caller
        except Exception:
            pass

    try:
        await asyncio.gather(*[_fetch_one(s) for s in symbols])
    finally:
        if own_client:
            await client.aclose()

    return result


async def enrich_with_oi(tickers: list[TickerSignal], window_hours: int = 48) -> list[TickerSignal]:
    """Attach OI momentum data to a list of TickerSignals in-place."""
    async with httpx.AsyncClient(timeout=15) as client:
        oi_map = await fetch_oi_momentum(
            [t.symbol for t in tickers], window_hours=window_hours, client=client
        )

    for t in tickers:
        if t.symbol in oi_map:
            oi_chg, _ = oi_map[t.symbol]
            t.oi_change_pct = oi_chg
            denom = max(abs(t.price_change_pct), 1.0)
            t.oi_ratio = oi_chg / denom

    return tickers


async def get_market_signals(top_n: int = 20, oi_window_hours: int = 48) -> list[TickerSignal]:
    """Full pipeline: top gainers → enrich with OI → return sorted list."""
    tickers = await fetch_top_gainers(n=top_n)
    tickers = await enrich_with_oi(tickers, window_hours=oi_window_hours)
    return tickers
