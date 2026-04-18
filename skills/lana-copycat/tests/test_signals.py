"""Tests for Binance market signals — uses pytest-httpx to avoid real network calls."""

import pytest
import pytest_asyncio
import json

from lana_copycat.signals.binance_market import (
    fetch_top_gainers,
    enrich_with_oi,
    TickerSignal,
)


MOCK_24HR = [
    {"symbol": "ETHUSDT", "priceChangePercent": "8.5", "quoteVolume": "5000000000"},
    {"symbol": "SOLUSDT", "priceChangePercent": "5.2", "quoteVolume": "2000000000"},
    {"symbol": "AVAXUSDT", "priceChangePercent": "3.1", "quoteVolume": "1500000000"},
    {"symbol": "LINKUSDT", "priceChangePercent": "-1.0", "quoteVolume": "800000000"},
    # filtered out — low volume
    {"symbol": "XYZUSDT", "priceChangePercent": "99.0", "quoteVolume": "50000"},
    # filtered out — not USDT pair
    {"symbol": "ETHBTC", "priceChangePercent": "2.0", "quoteVolume": "9000000000"},
]

MOCK_OI_HIST = [
    {"sumOpenInterestValue": "1000000000", "timestamp": 1000},
    {"sumOpenInterestValue": "1200000000", "timestamp": 2000},  # +20%
]


@pytest.mark.asyncio
async def test_fetch_top_gainers(httpx_mock):
    httpx_mock.add_response(
        url="https://fapi.binance.com/fapi/v1/ticker/24hr",
        json=MOCK_24HR,
    )
    tickers = await fetch_top_gainers(n=5)

    symbols = [t.symbol for t in tickers]
    assert "ETHUSDT" in symbols          # top gainer
    assert "XYZUSDT" not in symbols      # volume too low
    assert "ETHBTC" not in symbols       # not USDT pair
    assert tickers[0].price_change_pct >= tickers[1].price_change_pct  # sorted desc


@pytest.mark.asyncio
async def test_enrich_with_oi(httpx_mock):
    # mock OI history endpoint for each symbol
    for sym in ["ETHUSDT", "SOLUSDT", "AVAXUSDT"]:
        httpx_mock.add_response(
            url=f"https://fapi.binance.com/futures/data/openInterestHist?symbol={sym}&period=4h&limit=12",
            json=MOCK_OI_HIST,
        )

    tickers = [
        TickerSignal(symbol="ETHUSDT", price_change_pct=8.5, volume_usdt=5e9),
        TickerSignal(symbol="SOLUSDT", price_change_pct=5.2, volume_usdt=2e9),
        TickerSignal(symbol="AVAXUSDT", price_change_pct=3.1, volume_usdt=1.5e9),
    ]
    enriched = await enrich_with_oi(tickers, window_hours=48)

    for t in enriched:
        assert t.oi_change_pct != 0.0, f"{t.symbol} OI should be enriched"
        assert t.oi_ratio > 0.0
