# market-core

Reusable market data and technical analysis core.

This package is the lean shared layer extracted from `backend2`.
It keeps only reusable market capabilities:

- quote fetching
- OHLCV bar fetching
- RSS news loading
- technical indicator calculation
- symbol analysis snapshots via Pydantic models

It does not include:

- FastAPI routes
- workspace/file loading
- SQLite state
- trading runtime / orders

## Install

```bash
uv add market-core
```

For local development in this repo:

```bash
uv add --editable ./libs/market-core
```

## Example

```python
from market_core import MarketConfig, MarketRuntimeConfig, analyze_symbol

config = MarketRuntimeConfig(
    market=MarketConfig(profile="us_equity"),
)

snapshot = analyze_symbol("AAPL", config)
print(snapshot.quote.price)
print(snapshot.metrics)
```

## Live data providers

- `yfinance` for quotes and bars
- `fugle-marketdata` for Taiwan intraday quotes when `FUGLE_API_KEY` is set
- RSS feeds for news
