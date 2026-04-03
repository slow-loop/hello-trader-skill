from __future__ import annotations

import os
from datetime import date, datetime, timedelta

from fugle_marketdata import RestClient

from backend.core.market_data.models import Bar, Quote
from backend.core.market_data.symbols import normalize_symbol, strip_suffix


def fetch_quote(symbol: str) -> Quote:
    api_key = os.environ.get("FUGLE_API_KEY")
    if not api_key:
        raise ValueError("FUGLE_API_KEY environment variable is not set")

    normalized = normalize_symbol(symbol)
    client = RestClient(api_key=api_key)
    payload = client.stock.intraday.quote(symbol=strip_suffix(normalized))
    ticker = client.stock.intraday.ticker(symbol=strip_suffix(normalized))

    price = payload.get("lastPrice") or payload.get("closePrice")
    if price is None:
        raise ValueError(f"fugle returned no price for {normalized}")

    return Quote(
        symbol=normalized,
        market="tw",
        name=ticker.get("name"),
        price=float(price),
        source="fugle",
        timestamp=_parse_timestamp(payload),
        open=_maybe_float(payload.get("openPrice")),
        high=_maybe_float(payload.get("highPrice")),
        low=_maybe_float(payload.get("lowPrice")),
        prev_close=_maybe_float(payload.get("previousClose")),
        change=_maybe_float(payload.get("change")),
        change_pct=_maybe_float(payload.get("changePercent")),
        volume=_maybe_int(payload.get("tradeVolume")),
    )


def fetch_bars(
    symbol: str,
    lookback_days: int = 120,
    timeframe: str = "1d",
) -> list[Bar]:
    if timeframe != "1d":
        raise ValueError("fugle currently only supports 1d via this interface")

    api_key = os.environ.get("FUGLE_API_KEY")
    if not api_key:
        raise ValueError("FUGLE_API_KEY is not set")

    normalized = normalize_symbol(symbol)
    client = RestClient(api_key=api_key)

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    params = {
        "symbol": strip_suffix(normalized),
        "from": start_date.isoformat(),
        "to": end_date.isoformat(),
    }
    try:
        payload = client.stock.historical.candles(**params)
        data = payload.get("data")
        if not data:
            print(f"[FUGLE] No data returned for {normalized}")
            raise ValueError(f"fugle returned no bar data for {normalized}")
        print(f"[FUGLE] Retrieved {len(data)} bars for {normalized}")
    except Exception as e:
        print(f"[FUGLE] Error fetching bars for {normalized}: {e}")
        raise

    bars: list[Bar] = []
    # Sort chronological (oldest first)
    sorted_data = sorted(data, key=lambda x: x["date"])

    for row in sorted_data:
        bars.append(
            Bar(
                symbol=normalized,
                market="tw",
                timeframe="1d",
                bar_time=datetime.fromisoformat(row["date"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
                adjusted=True,
                source="fugle",
            )
        )
    return bars


def _parse_timestamp(payload: dict) -> datetime | None:
    raw = payload.get("lastUpdated")
    if raw:
        return datetime.fromtimestamp(raw / 1_000_000)
    return None


def _maybe_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _maybe_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)

