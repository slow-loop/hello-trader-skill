from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from backend.core.market_data.models import Bar, Quote
from backend.core.market_data.symbols import detect_market, normalize_symbol


def fetch_quote(symbol: str) -> Quote:
    normalized = normalize_symbol(symbol)
    ticker = yf.Ticker(normalized)
    info = ticker.fast_info

    try:
        price = _maybe_float(getattr(info, "last_price", None))
    except Exception:
        price = None

    try:
        prev_close = _maybe_float(getattr(info, "previous_close", None))
    except Exception:
        prev_close = None

    if price is None:
        hist = ticker.history(period="2d", auto_adjust=False)
        if hist.empty:
            raise ValueError(f"yfinance returned no quote data for {normalized}")
        price = _maybe_float(hist["Close"].iloc[-1])
        if len(hist) >= 2:
            prev_close = _maybe_float(hist["Close"].iloc[-2])

    if price is None:
        raise ValueError(f"yfinance returned no price for {normalized}")

    change = None
    change_pct = None
    if prev_close not in (None, 0):
        change = round(price - prev_close, 4)
        change_pct = round((price - prev_close) / prev_close * 100, 4)

    name = getattr(info, "name", None) or ticker.info.get("longName")
    return Quote(
        symbol=normalized,
        market=detect_market(normalized),
        name=name,
        price=price,
        source="yfinance",
        timestamp=datetime.now(),
        open=_maybe_float(getattr(info, "open", None)),
        high=_maybe_float(getattr(info, "day_high", None)),
        low=_maybe_float(getattr(info, "day_low", None)),
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        volume=_maybe_int(getattr(info, "last_volume", None)),
    )


def fetch_bars(symbol: str, lookback_days: int = 365, timeframe: str = "1d") -> list[Bar]:
    if timeframe != "1d":
        raise ValueError("market_data only supports 1d bars")

    normalized = normalize_symbol(symbol)
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    df = yf.download(
        normalized,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        interval=timeframe,
    )
    if df.empty:
        raise ValueError(f"yfinance returned no bar data for {normalized}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.rename(columns=str.lower).reset_index()
    date_col = "date" if "date" in df.columns else df.columns[0]
    market = detect_market(normalized)

    bars: list[Bar] = []
    for row in df.to_dict("records"):
        bars.append(
            Bar(
                symbol=normalized,
                market=market,
                timeframe="1d",
                bar_time=pd.to_datetime(row[date_col]).to_pydatetime(),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=_maybe_int(row.get("volume")),
                adjusted=True,
                source="yfinance",
            )
        )
    return bars


def _maybe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _maybe_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
