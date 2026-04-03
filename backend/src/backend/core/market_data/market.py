from __future__ import annotations

from datetime import date, datetime, timedelta

from backend.core.market_calendar import CHIPS_UPDATE_HM, get_last_trading_day
from backend.core.market_data.models import Bar, ChipsDaily, Quote
from backend.core.market_data.providers.finmind import fetch_chips
from backend.core.market_data.providers.fugle import (
    fetch_bars as fetch_fugle_bars,
    fetch_quote as fetch_fugle_quote,
)
from backend.core.market_data.providers.yfinance import (
    fetch_bars as fetch_yfinance_bars,
    fetch_quote as fetch_yfinance_quote,
)
from backend.core.market_data.storage import load_bars, load_chips, save_bars, save_chips
from backend.core.market_data.symbols import is_tw_equity_symbol, normalize_symbol


def get_quote(symbol: str) -> Quote:
    normalized = normalize_symbol(symbol)
    if is_tw_equity_symbol(normalized):
        return fetch_fugle_quote(normalized)
    return fetch_yfinance_quote(normalized)


def refresh_bars(symbol: str, lookback_days: int = 120, timeframe: str = "1d") -> list[Bar]:
    normalized = normalize_symbol(symbol)
    if is_tw_equity_symbol(normalized):
        bars = fetch_fugle_bars(normalized, lookback_days=lookback_days, timeframe=timeframe)
        save_bars(normalized, bars, timeframe=timeframe)
        return bars

    bars = fetch_yfinance_bars(normalized, lookback_days=lookback_days, timeframe=timeframe)
    save_bars(normalized, bars, timeframe=timeframe)
    return bars


def get_bars(
    symbol: str,
    lookback_days: int = 120,
    timeframe: str = "1d",
    start: date | datetime | None = None,
    end: date | datetime | None = None,
    refresh: bool = False,
) -> list[Bar]:
    normalized = normalize_symbol(symbol)
    if start is None and end is None:
        start = datetime.now() - timedelta(days=lookback_days)
    if not refresh:
        local = load_bars(normalized, timeframe=timeframe, start=start, end=end)
        if local:
            last_bar_date = local[-1].bar_time.date()
            last_trading_day = get_last_trading_day()
            if last_bar_date >= last_trading_day:
                return local
            # Cache is stale — fall through to refresh
    bars = refresh_bars(normalized, lookback_days=lookback_days, timeframe=timeframe)
    return _filter_bars(bars, start=start, end=end)


def refresh_chips(symbol: str, lookback_days: int = 180) -> list[ChipsDaily]:
    normalized = normalize_symbol(symbol)
    rows = fetch_chips(normalized, lookback_days=lookback_days)
    save_chips(normalized, rows)
    return rows


def get_chips(
    symbol: str,
    lookback_days: int = 180,
    start: date | datetime | None = None,
    end: date | datetime | None = None,
    refresh: bool = False,
) -> list[ChipsDaily]:
    normalized = normalize_symbol(symbol)
    if start is None and end is None:
        start = date.today() - timedelta(days=lookback_days)
    if not refresh:
        local = load_chips(normalized, start=start, end=end)
        if local:
            last_chip_date = local[-1].trade_date
            # Use a slightly later threshold for chips (T+0 4:30 PM)
            last_trading_day = get_last_trading_day(market_close_hm=CHIPS_UPDATE_HM)
            if last_chip_date >= last_trading_day:
                return local
            # Cache is stale — fall through to refresh
    rows = refresh_chips(normalized, lookback_days=lookback_days)
    return _filter_chips(rows, start=start, end=end)


def _filter_bars(
    bars: list[Bar],
    *,
    start: date | datetime | None,
    end: date | datetime | None,
) -> list[Bar]:
    if start is None and end is None:
        return bars

    filtered: list[Bar] = []
    for bar in bars:
        if start is not None and bar.bar_time < _coerce_datetime(start):
            continue
        if end is not None and bar.bar_time > _coerce_datetime(end, is_end=True):
            continue
        filtered.append(bar)
    return filtered


def _filter_chips(
    rows: list[ChipsDaily],
    *,
    start: date | datetime | None,
    end: date | datetime | None,
) -> list[ChipsDaily]:
    if start is None and end is None:
        return rows

    start_date = _coerce_date(start) if start is not None else None
    end_date = _coerce_date(end) if end is not None else None
    filtered: list[ChipsDaily] = []
    for row in rows:
        if start_date is not None and row.trade_date < start_date:
            continue
        if end_date is not None and row.trade_date > end_date:
            continue
        filtered.append(row)
    return filtered


def _coerce_datetime(value: date | datetime, is_end: bool = False) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, datetime.max.time() if is_end else datetime.min.time())


def _coerce_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value
