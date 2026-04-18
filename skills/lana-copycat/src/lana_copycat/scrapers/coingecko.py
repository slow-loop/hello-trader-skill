"""CoinGecko trending coins — drop-in replacement for Binance Square signal.

Binance Square is protected by AWS WAF that blocks all headless / direct access.
CoinGecko trending provides equivalent "what's hot right now" signal via free public API.
No API key required for basic usage (60 req/min free tier).
"""

from __future__ import annotations

import httpx

TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"

STABLECOINS = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USD", "USDD"}


async def get_trending_counts(client: httpx.AsyncClient | None = None) -> dict[str, int]:
    """
    Return {SYMBOL: score} where score = (8 - rank) so the top coin scores 8.
    Matches the interface of square.SquareSnapshot.ticker_counts.
    """
    own = client is None
    if own:
        client = httpx.AsyncClient(timeout=10)

    try:
        resp = await client.get(TRENDING_URL)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own:
            await client.aclose()

    counts: dict[str, int] = {}
    coins = data.get("coins", [])
    total = len(coins)
    for rank, item in enumerate(coins):
        sym = item["item"]["symbol"].upper()
        if sym in STABLECOINS:
            continue
        # invert rank so top trending = highest score
        counts[sym] = max(1, total - rank)

    return counts
