"""Stock universes for factor evaluation.

SP500 is fetched from Wikipedia at call time (free, reliable-ish). Smaller
curated lists are hard-coded for fast iteration. Extend as needed.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

logger = logging.getLogger(__name__)


# Small curated list for quick smoke tests & first-pass momentum runs.
MEGACAP_TECH = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AVGO", "TSLA",
    "AMD", "QCOM", "CRM", "ORCL", "ADBE", "NFLX", "INTC",
]

# Curated snapshot of S&P 500 top ~100 by market cap (approximate, end-2024).
# Used for broader-universe IC / backtest validation after megacap_tech passes.
# Refresh with a future helper; alphabetical order within for readability.
SP500_TOP100 = [
    "AAPL", "ABBV", "ABT", "ACN", "ADBE", "AMD", "AMGN", "AMZN", "AVGO", "AXP",
    "BA", "BAC", "BK", "BLK", "BMY", "BRK-B", "BX", "C", "CAT", "CB",
    "CMCSA", "COP", "COST", "CRM", "CSCO", "CVS", "CVX", "DE", "DHR", "DIS",
    "ELV", "EOG", "ETN", "FI", "GD", "GE", "GILD", "GOOG", "GOOGL", "GS",
    "HD", "HON", "IBM", "INTC", "INTU", "ISRG", "JNJ", "JPM", "KKR", "KO",
    "LIN", "LLY", "LMT", "LOW", "MA", "MCD", "MDLZ", "MDT", "META", "MMC",
    "MO", "MRK", "MS", "MSFT", "MU", "NEE", "NFLX", "NKE", "NOW", "NVDA",
    "ORCL", "PEP", "PFE", "PG", "PGR", "PLTR", "PM", "QCOM", "RTX", "SBUX",
    "SCHW", "SO", "SPGI", "SYK", "T", "TJX", "TMO", "TMUS", "TSLA", "TXN",
    "UBER", "UNH", "UNP", "UPS", "V", "VRTX", "VZ", "WFC", "WMT", "XOM",
]

# Indices for regime evaluation (SPX/QQQ/SOX/VIX/DJIA).
BENCHMARKS = {
    "SPX": "^GSPC",
    "QQQ": "QQQ",
    "SOX": "^SOX",
    "VIX": "^VIX",
    "DJIA": "^DJI",
    "US10Y": "^TNX",
}


@lru_cache(maxsize=1)
def load_sp500() -> list[str]:
    """Fetch current S&P 500 constituents from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        tables = pd.read_html(url)
        df = tables[0]
        # Column is 'Symbol' on Wikipedia. Convert BRK.B → BRK-B for yfinance.
        tickers = [t.replace(".", "-") for t in df["Symbol"].tolist()]
        return tickers
    except Exception as exc:
        logger.warning("failed fetching S&P 500 list: %s", exc)
        return []


def resolve_universe(name: str) -> list[str]:
    """Resolve a universe name to ticker list."""
    name = name.lower()
    if name == "sp500":
        return load_sp500()
    if name == "sp500_top100":
        return SP500_TOP100
    if name == "megacap_tech":
        return MEGACAP_TECH
    if name == "benchmarks":
        return list(BENCHMARKS.values())
    raise ValueError(f"unknown universe: {name}")
