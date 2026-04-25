"""Historical OHLC cache for bulk research / backtests.

Cached daily OHLC in parquet, one file per symbol. Re-download fetches only
missing tail. Safe to call repeatedly.

Use case: factor-IC and strategy backtests that need years of daily bars across
many symbols. Complementary to `market_core.get_bars`, which is a profile-aware
live lookback returning `list[Bar]`.

Both use the same yfinance access path: `yf.Ticker(sym).history(...)`.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "market-core" / "yfinance"

_EMPTY = pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


def _cache_path(symbol: str, cache_dir: Path) -> Path:
    return cache_dir / f"{symbol.upper()}.parquet"


def _fetch_yf(symbol: str, fetch_start: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
    """Fetch daily OHLCV via yf.Ticker — same call path as market_core.get_bars.

    Returns normalised DataFrame (lowercase cols, DatetimeIndex named 'date').
    Empty frame if yfinance has no data.
    """
    ticker = yf.Ticker(symbol.upper())
    raw = ticker.history(
        start=fetch_start.strftime("%Y-%m-%d"),
        end=(end_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),  # end is exclusive
        interval="1d",
        auto_adjust=True,
    )
    if raw is None or raw.empty:
        return _EMPTY.copy()

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    raw = raw.rename(columns=str.lower)
    # Keep only standard OHLCV; drop dividends, splits, repaired?, etc.
    raw = raw[[c for c in ["open", "high", "low", "close", "volume"] if c in raw.columns]]
    raw = raw.astype(float)
    idx = pd.to_datetime(raw.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    raw.index = idx.normalize()  # strip time-of-day (e.g. 05:00:00 UTC-offset artifact)
    raw.index.name = "date"
    return raw


def load_ohlc(
    symbol: str,
    *,
    start: str | date = "2018-01-01",
    end: str | date | None = None,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    """Load daily OHLCV for a single symbol. Cached to parquet.

    Returns DataFrame indexed by `date` (DatetimeIndex), columns: open, high,
    low, close, volume. Empty frame if yfinance returns nothing.
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol, cache_dir)

    end_dt = pd.to_datetime(end) if end else pd.Timestamp.today().normalize()
    start_dt = pd.to_datetime(start)

    cached: pd.DataFrame | None = None
    if path.exists() and not refresh:
        cached = pd.read_parquet(path)

    if cached is not None and not cached.empty:
        first_cached = cached.index.min()
        last_cached = cached.index.max()
        # Cache covers the full requested window — return slice directly.
        if first_cached <= start_dt and last_cached >= end_dt - pd.Timedelta(days=1):
            return cached.loc[start_dt:end_dt]
        # Need history before cache start — discard cache, refetch everything.
        if first_cached > start_dt:
            cached = None
            fetch_start = start_dt
        else:
            fetch_start = last_cached + pd.Timedelta(days=1)
    else:
        fetch_start = start_dt

    logger.info("yfinance fetch %s %s..%s", symbol, fetch_start.date(), end_dt.date())
    raw = _fetch_yf(symbol, fetch_start, end_dt)
    if raw.empty:
        if cached is not None:
            return cached.loc[start_dt:end_dt]
        return _EMPTY.copy()

    combined = raw if cached is None else pd.concat([cached, raw]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.to_parquet(path)
    return combined.loc[start_dt:end_dt]


def _normalise_batch_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise a single-symbol slice of a yf.download frame.

    Shared tail with `_fetch_yf`: lowercase OHLCV, tz-naive DatetimeIndex
    named 'date', float dtypes, empty frame if nothing usable.
    """
    if raw is None or raw.empty:
        return _EMPTY.copy()
    raw = raw.rename(columns=str.lower)
    raw = raw[[c for c in ["open", "high", "low", "close", "volume"] if c in raw.columns]]
    raw = raw.dropna(how="all")
    if raw.empty:
        return _EMPTY.copy()
    raw = raw.astype(float)
    idx = pd.to_datetime(raw.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    raw.index = idx.normalize()
    raw.index.name = "date"
    return raw


def _split_batch(download: pd.DataFrame, symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Split the MultiIndex frame returned by yf.download into per-symbol frames."""
    out: dict[str, pd.DataFrame] = {}
    if download is None or download.empty:
        return out
    # yf.download with group_by="ticker" gives columns as MultiIndex (ticker, field).
    # Single-symbol returns flat columns.
    if isinstance(download.columns, pd.MultiIndex):
        top = download.columns.get_level_values(0).unique()
        for sym in symbols:
            key = sym.upper()
            if key not in top:
                continue
            sub = download[key].copy()
            out[sym] = _normalise_batch_frame(sub)
    else:
        # Only one symbol was fetched.
        if symbols:
            out[symbols[0]] = _normalise_batch_frame(download.copy())
    return out


def load_many(
    symbols: list[str],
    *,
    start: str | date = "2018-01-01",
    end: str | date | None = None,
    cache_dir: Path | None = None,
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Bulk load daily OHLCV. Uses `yf.download` batch for symbols that need fetching.

    Per-symbol caches are honoured: fully-cached symbols are served from parquet
    without a network call. Remaining symbols are fetched in one batch request
    from the earliest needed start date, then merged into each symbol's cache.
    """
    cache_dir = cache_dir or DEFAULT_CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    end_dt = pd.to_datetime(end) if end else pd.Timestamp.today().normalize()
    start_dt = pd.to_datetime(start)

    out: dict[str, pd.DataFrame] = {}
    to_fetch: list[str] = []
    fetch_starts: dict[str, pd.Timestamp] = {}
    caches: dict[str, pd.DataFrame | None] = {}

    for sym in symbols:
        path = _cache_path(sym, cache_dir)
        cached: pd.DataFrame | None = None
        if path.exists() and not refresh:
            try:
                cached = pd.read_parquet(path)
            except Exception as exc:
                logger.warning("failed reading cache for %s: %s", sym, exc)
                cached = None

        if cached is not None and not cached.empty:
            first_cached = cached.index.min()
            last_cached = cached.index.max()
            if first_cached <= start_dt and last_cached >= end_dt - pd.Timedelta(days=1):
                out[sym] = cached.loc[start_dt:end_dt]
                continue
            if first_cached > start_dt:
                caches[sym] = None
                fetch_starts[sym] = start_dt
            else:
                caches[sym] = cached
                fetch_starts[sym] = last_cached + pd.Timedelta(days=1)
        else:
            caches[sym] = None
            fetch_starts[sym] = start_dt
        to_fetch.append(sym)

    if not to_fetch:
        return out

    batch_start = min(fetch_starts[s] for s in to_fetch)
    logger.info(
        "yfinance batch fetch %d symbols from %s..%s",
        len(to_fetch),
        batch_start.date(),
        end_dt.date(),
    )

    try:
        download = yf.download(
            tickers=[s.upper() for s in to_fetch],
            start=batch_start.strftime("%Y-%m-%d"),
            end=(end_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=True,
            group_by="ticker",
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logger.warning("batch download failed (%s); falling back to sequential", exc)
        download = None

    fetched = _split_batch(download, to_fetch) if download is not None else {}

    for sym in to_fetch:
        raw = fetched.get(sym, _EMPTY.copy())
        if raw.empty:
            # Per-symbol fallback — some tickers routinely fail inside batch.
            try:
                raw = _fetch_yf(sym, fetch_starts[sym], end_dt)
            except Exception as exc:
                logger.warning("failed loading %s: %s", sym, exc)
                raw = _EMPTY.copy()

        cached = caches.get(sym)
        if raw.empty:
            if cached is not None:
                out[sym] = cached.loc[start_dt:end_dt]
            continue

        combined = raw if cached is None else pd.concat([cached, raw]).sort_index()
        combined = combined[~combined.index.duplicated(keep="last")]
        try:
            combined.to_parquet(_cache_path(sym, cache_dir))
        except Exception as exc:
            logger.warning("failed writing cache for %s: %s", sym, exc)
        sliced = combined.loc[start_dt:end_dt]
        if not sliced.empty:
            out[sym] = sliced

    return out
