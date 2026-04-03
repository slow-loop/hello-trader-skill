from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
import os

import pandas as pd

from backend.core.market_data.models import Bar, ChipsDaily
from backend.core.market_data.symbols import detect_market, normalize_symbol, symbol_key

MARKET_DIR = Path(os.getenv("TW_TRADER_DATA_DIR", str(Path(__file__).parents[4] / "data"))) / "market"


def bars_path(symbol: str, timeframe: str = "1d") -> Path:
    normalized = normalize_symbol(symbol)
    market = detect_market(normalized)
    return MARKET_DIR / "bars" / market / timeframe / f"{symbol_key(normalized)}_{timeframe}.parquet"


def chips_path(symbol: str) -> Path:
    normalized = normalize_symbol(symbol)
    market = detect_market(normalized)
    if market != "tw":
        raise ValueError("chips storage only supports tw symbols")
    return MARKET_DIR / "chips" / market / f"{symbol_key(normalized)}.parquet"


def load_bars(
    symbol: str,
    timeframe: str = "1d",
    start: date | datetime | None = None,
    end: date | datetime | None = None,
) -> list[Bar]:
    path = bars_path(symbol, timeframe=timeframe)
    if not path.exists():
        return []

    df = pd.read_parquet(path)
    if df.empty:
        return []

    df["bar_time"] = pd.to_datetime(df["bar_time"])
    if start is not None:
        df = df[df["bar_time"] >= _as_datetime(start, is_end=False)]
    if end is not None:
        df = df[df["bar_time"] <= _as_datetime(end, is_end=True)]

    bars: list[Bar] = []
    for row in df.sort_values("bar_time").to_dict("records"):
        bars.append(Bar(**row))
    return bars


def save_bars(symbol: str, bars: list[Bar], timeframe: str = "1d") -> Path:
    path = bars_path(symbol, timeframe=timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)

    incoming = pd.DataFrame([bar.model_dump() for bar in bars])
    if incoming.empty:
        return path

    incoming["bar_time"] = pd.to_datetime(incoming["bar_time"])
    incoming = incoming.sort_values("bar_time")

    if path.exists():
        existing = pd.read_parquet(path)
        if not existing.empty:
            existing["bar_time"] = pd.to_datetime(existing["bar_time"])
            incoming = pd.concat([existing, incoming], ignore_index=True)

    incoming = incoming.drop_duplicates(subset=["bar_time"], keep="last")
    incoming = incoming.sort_values("bar_time")
    incoming.to_parquet(path, index=False)
    return path


def load_chips(
    symbol: str,
    start: date | datetime | None = None,
    end: date | datetime | None = None,
) -> list[ChipsDaily]:
    path = chips_path(symbol)
    if not path.exists():
        return []

    df = pd.read_parquet(path)
    if df.empty:
        return []

    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    if start is not None:
        start_date = _as_date(start)
        df = df[df["trade_date"] >= start_date]
    if end is not None:
        end_date = _as_date(end)
        df = df[df["trade_date"] <= end_date]

    chips_rows: list[ChipsDaily] = []
    # Replace NaN with None to avoid Pydantic validation errors
    for row in df.sort_values("trade_date").to_dict("records"):
        sanitized = {k: (v if pd.notnull(v) else None) for k, v in row.items()}
        chips_rows.append(ChipsDaily(**sanitized))
    return chips_rows


def save_chips(symbol: str, rows: list[ChipsDaily]) -> Path:
    path = chips_path(symbol)
    path.parent.mkdir(parents=True, exist_ok=True)

    incoming = pd.DataFrame([row.model_dump() for row in rows])
    if incoming.empty:
        return path

    incoming["trade_date"] = pd.to_datetime(incoming["trade_date"]).dt.date
    incoming = incoming.sort_values("trade_date")

    if path.exists():
        existing = pd.read_parquet(path)
        if not existing.empty:
            existing["trade_date"] = pd.to_datetime(existing["trade_date"]).dt.date
            incoming = pd.concat([existing, incoming], ignore_index=True)

    incoming = incoming.drop_duplicates(subset=["trade_date"], keep="last")
    incoming = incoming.sort_values("trade_date")
    incoming.to_parquet(path, index=False)
    return path


def _as_datetime(value: date | datetime, *, is_end: bool) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.max if is_end else time.min)


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value
