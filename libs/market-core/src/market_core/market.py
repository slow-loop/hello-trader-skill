from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
import os
import ssl
import urllib.request

import feedparser
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)
from fugle_marketdata import RestClient
import pandas as pd
import yfinance as yf

from market_core.models import AnalysisReport, AnalysisSnapshot, Bar, MarketOverview, MarketRuntimeConfig, NewsItem, Quote, utc_now_iso
from market_core.policies import MarketProfile, get_market_profile, get_market_session, market_data_symbol, normalize_symbol
from market_core.technical import (
    AnalysisConfig,
    ExpressionSpec,
    IndicatorSpec,
    build_technical_analysis,
    default_analysis_config,
)


def get_quote(symbol: str, profile: MarketProfile) -> Quote:
    normalized = normalize_symbol(symbol, profile)
    if profile.id == "tw_equity" and _is_tw_equity_symbol(normalized):
        fugle_quote = _try_fugle_quote(normalized, profile)
        if fugle_quote is not None:
            return fugle_quote
        # TW equity requires Fugle — set FUGLE_API_KEY env var to enable quote fetching.
        # yfinance is intentionally not used as a fallback: it returns TWD prices in NTD
        # but with stale/delayed data and inconsistent volume, which breaks technical analysis.
        raise ValueError(f"failed to fetch TW data for {normalized} from Fugle (required)")

    data_symbol = market_data_symbol(normalized, profile)
    ticker = yf.Ticker(data_symbol)
    info = ticker.fast_info

    price = _safe_float(getattr(info, "last_price", None))
    prev_close = _safe_float(getattr(info, "previous_close", None))
    if price is None:
        hist = ticker.history(period="2d", auto_adjust=False)
        if hist.empty:
            raise ValueError(f"no quote data for {normalized}")
        price = _safe_float(hist["Close"].iloc[-1])
        if len(hist) >= 2:
            prev_close = _safe_float(hist["Close"].iloc[-2])

    if price is None:
        raise ValueError(f"no price for {normalized}")

    change = None
    change_pct = None
    if prev_close not in (None, 0):
        change = round(price - prev_close, 4)
        change_pct = round((price - prev_close) / prev_close * 100, 4)

    name = getattr(info, "name", None)
    if not name:
        try:
            name = ticker.info.get("longName")
        except Exception:
            name = None

    return Quote(
        symbol=normalized,
        market_profile=profile.id,
        name=name,
        price=price,
        source="yfinance",
        open=_safe_float(getattr(info, "open", None)),
        high=_safe_float(getattr(info, "day_high", None)),
        low=_safe_float(getattr(info, "day_low", None)),
        prev_close=prev_close,
        change=change,
        change_pct=change_pct,
        volume=_safe_int(getattr(info, "last_volume", None)),
    )


def get_bars(
    symbol: str,
    profile: MarketProfile,
    *,
    timeframe: str = "1d",
    lookback_days: int = 180,
) -> list[Bar]:
    normalized = normalize_symbol(symbol, profile)
    if profile.id == "tw_equity" and _is_tw_equity_symbol(normalized):
        fugle_bars = _try_fugle_bars(normalized, profile, timeframe=timeframe, lookback_days=lookback_days)
        if fugle_bars:
            return fugle_bars
        # TW equity requires Fugle — set FUGLE_API_KEY env var to enable bar fetching.
        # yfinance is intentionally not used as a fallback: see get_quote() for rationale.
        raise ValueError(f"failed to fetch TW bar data for {normalized} from Fugle (required)")

    data_symbol = market_data_symbol(normalized, profile)
    if timeframe not in {"1d", "1h"}:
        raise ValueError("timeframe must be 1d or 1h")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    ticker = yf.Ticker(data_symbol)
    df = ticker.history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval=timeframe,
        auto_adjust=True,
    )
    if df.empty:
        raise ValueError(f"no bar data for {normalized}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower).reset_index()
    date_col = "date" if "date" in df.columns else df.columns[0]

    return [
        Bar(
            symbol=normalized,
            market_profile=profile.id,
            bar_time=pd.to_datetime(row[date_col]).to_pydatetime().isoformat(),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=_safe_int(row.get("volume")),
            source="yfinance",
        )
        for row in df.to_dict("records")
    ]


def build_overview(config: MarketRuntimeConfig, profile: MarketProfile | None = None) -> MarketOverview:
    resolved_profile = profile or get_market_profile(config.market.profile)
    session = get_market_session(resolved_profile)
    benchmark_symbol = config.market.benchmark_symbol or resolved_profile.benchmark_symbol
    benchmark_quote = None
    benchmark_metrics = None
    if benchmark_symbol:
        if resolved_profile.id == "tw_equity" and benchmark_symbol.upper() in {"^TWII", "TAIEX"}:
            benchmark_quote = _twse_taiex_quote(resolved_profile)
            live_price = benchmark_quote.price if benchmark_quote else None
            benchmark_metrics = _twse_taiex_benchmark_metrics(live_price)
        if benchmark_quote is None:
            try:
                benchmark_quote = get_quote(benchmark_symbol, resolved_profile)
            except Exception:
                benchmark_quote = None

    return MarketOverview(
        market_profile=resolved_profile.id,
        session=str(session["phase"]),
        is_open=bool(session["is_open"]),
        reason=str(session["reason"]),
        benchmark_symbol=benchmark_symbol,
        benchmark_quote=benchmark_quote,
        benchmark_metrics=benchmark_metrics,
        news=get_news(config),
    )


def build_analysis(symbol: str, config: MarketRuntimeConfig, profile: MarketProfile | None = None) -> AnalysisReport:
    snapshot = analyze_symbol(symbol, config, profile)
    return AnalysisReport.model_validate(snapshot.model_dump(exclude={"bars"}))


def analyze_symbol(
    symbol: str,
    config: MarketRuntimeConfig,
    profile: MarketProfile | None = None,
) -> AnalysisSnapshot:
    resolved_profile = profile or get_market_profile(config.market.profile)
    quote = get_quote(symbol, resolved_profile)
    bars = get_bars(
        symbol,
        resolved_profile,
        timeframe=config.analysis.timeframe,
        lookback_days=config.analysis.lookback_days,
    )
    df = bars_to_dataframe(bars)
    technical_config = _build_analysis_config(config)
    technical_analysis = build_technical_analysis(df, technical_config)
    metrics = {
        key: (round(value, 4) if isinstance(value, float) else value)
        for key, value in technical_analysis.values.items()
        if key in (technical_config.outputs or default_analysis_config().outputs)
    }

    return AnalysisSnapshot(
        symbol=normalize_symbol(symbol, resolved_profile),
        quote=quote,
        bars=bars,
        metrics=metrics,
        triggers={tag: names for tag, names in technical_analysis.triggers.items() if names},
        warnings=technical_analysis.warnings,
        news=_filter_news_for_symbol(symbol, get_news(config)),
        extra={"context": technical_analysis.values},
    )


def get_news(config: MarketRuntimeConfig) -> list[NewsItem]:
    news_config = config.news
    if not news_config.enabled or not news_config.sources:
        return []

    seen: set[tuple[str, str]] = set()
    items: list[NewsItem] = []
    for source in news_config.sources:
        if source.kind != "rss":
            continue
        feed = feedparser.parse(source.url)
        for entry in feed.entries[: news_config.max_items]:
            title = str(getattr(entry, "title", "")).strip()
            url = str(getattr(entry, "link", "")).strip()
            if not title or not url:
                continue
            key = (title, url)
            if key in seen:
                continue
            seen.add(key)
            published = str(getattr(entry, "published", "") or getattr(entry, "updated", ""))
            items.append(NewsItem(title=title, url=url, published=published, source=source.name or source.url))
            if len(items) >= news_config.max_items:
                return items
    return items


def bars_to_dataframe(bars: list[Bar]) -> pd.DataFrame:
    rows = [
        {
            "date": bar.bar_time,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]
    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    if "volume" in df.columns:
        df["volume"] = df["volume"].fillna(0)
    return df


def _build_analysis_config(config: MarketRuntimeConfig) -> AnalysisConfig:
    default = default_analysis_config()
    indicators = (
        [IndicatorSpec.model_validate(item.model_dump()) for item in config.analysis.indicators]
        if config.analysis.indicators
        else default.indicators
    )
    expressions = [ExpressionSpec.model_validate(item.model_dump()) for item in config.analysis.expressions]
    outputs = config.analysis.outputs or default.outputs
    return AnalysisConfig(indicators=indicators, expressions=expressions, outputs=outputs)


def _filter_news_for_symbol(symbol: str, items: list[NewsItem]) -> list[NewsItem]:
    normalized = symbol.upper()
    candidates = {
        normalized,
        normalized.removesuffix(".TW").removesuffix(".TWO"),
    }
    filtered: list[NewsItem] = []
    for item in items:
        title = item.title.upper()
        if any(candidate and candidate in title for candidate in candidates):
            filtered.append(item)
    return filtered


FUGLE_TIMEFRAME_MAP = {
    "1d": "D",
    "1h": "60",
    "30m": "30",
    "15m": "15",
    "5m": "5",
    "1m": "1",
}


def _try_fugle_bars(
    symbol: str,
    profile: MarketProfile,
    *,
    timeframe: str = "1d",
    lookback_days: int = 180,
) -> list[Bar] | None:
    tf = FUGLE_TIMEFRAME_MAP.get(timeframe)
    if tf is None:
        raise ValueError(f"unsupported Fugle timeframe '{timeframe}'; supported: {sorted(FUGLE_TIMEFRAME_MAP)}")
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        return None
    client = RestClient(api_key=api_key)
    stock_id = symbol.removesuffix(".TW").removesuffix(".TWO")
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)

    data = client.stock.historical.candles(**{
        "symbol": stock_id,
        "timeframe": tf,
        "from": start.strftime("%Y-%m-%d"),
        "to": end.strftime("%Y-%m-%d"),
        "fields": "open,high,low,close,volume,turnover,change",
    })
    if not data:
        return None

    # API returns {"data": [...], "symbol": ..., ...}
    rows = data["data"] if isinstance(data, dict) else data
    return [
        Bar(
            symbol=symbol,
            market_profile=profile.id,
            bar_time=row["date"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=_safe_int(row.get("volume")),
            source="fugle",
        )
        for row in rows
    ]


def _try_fugle_quote(symbol: str, profile: MarketProfile) -> Quote | None:
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        return None
    client = RestClient(api_key=api_key)
    stock_id = symbol.removesuffix(".TW").removesuffix(".TWO")
    payload = client.stock.intraday.quote(symbol=stock_id)
    ticker = client.stock.intraday.ticker(symbol=stock_id)
    price = payload.get("lastPrice") or payload.get("closePrice")
    if price is None:
        return None
    change_pct = _safe_float(payload.get("changePercent"))
    is_limit_up, is_limit_down = _tw_limit_flags(profile, change_pct)
    return Quote(
        symbol=symbol,
        market_profile=profile.id,
        name=ticker.get("name"),
        price=float(price),
        source="fugle",
        open=_safe_float(payload.get("openPrice")),
        high=_safe_float(payload.get("highPrice")),
        low=_safe_float(payload.get("lowPrice")),
        prev_close=_safe_float(payload.get("previousClose")),
        change=_safe_float(payload.get("change")),
        change_pct=change_pct,
        volume=_safe_int(payload.get("tradeVolume")),
        is_limit_up=is_limit_up,
        is_limit_down=is_limit_down,
    )


# TW equity 10% daily limit. Fugle's changePercent already accounts for tick rounding,
# so a 9.9%+ move is effectively limit-up (true limit-up rounds to ~9.92-10.00%).
_TW_LIMIT_THRESHOLD = 9.9


def _tw_limit_flags(profile: MarketProfile, change_pct: float | None) -> tuple[bool, bool]:
    if profile.id != "tw_equity" or change_pct is None:
        return False, False
    return change_pct >= _TW_LIMIT_THRESHOLD, change_pct <= -_TW_LIMIT_THRESHOLD


_TWSE_FMTQIK_URL = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
# www.twse.com.tw updates with today's data post-close; openapi.twse.com.tw lags by ~1 day
_TWSE_FMTQIK_WWW_URL = "https://www.twse.com.tw/exchangeReport/FMTQIK?response=json"
_logger = logging.getLogger(__name__)


def _fetch_twse_fmtqik_www() -> list[dict]:
    """Fetch TAIEX daily summary from www.twse.com.tw (same-day, post-close).

    Returns rows in the same dict format as fetch_twse_fmtqik():
    {Date, TradeVolume, TradeValue, Transaction, TAIEX, Change}
    where Date is a 7-digit ROC date string (e.g. "1150422").
    """
    try:
        request = urllib.request.Request(
            _TWSE_FMTQIK_WWW_URL,
            headers={"User-Agent": "market-core/1.0"},
        )
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, context=context, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        _logger.warning("twse fmtqik www fetch failed: %s", exc)
        return []

    if not isinstance(payload, dict) or payload.get("stat") != "OK":
        return []
    rows = payload.get("data", [])
    if not rows:
        return []

    # Array format: [日期, 成交股數, 成交金額, 成交筆數, 加權股價指數, 漲跌點數]
    # Date field is "115/04/22" — convert to 7-digit "1150422"
    result = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 6:
            continue
        roc_date = str(row[0]).replace("/", "").strip()  # "115/04/22" → "1150422"
        result.append({
            "Date": roc_date,
            "TradeVolume": str(row[1]),
            "TradeValue": str(row[2]),
            "Transaction": str(row[3]),
            "TAIEX": str(row[4]),
            "Change": str(row[5]),
        })
    return sorted(result, key=lambda r: str(r.get("Date", "")))


def fetch_twse_fmtqik() -> list[dict]:
    """Fetch TAIEX daily summary (FMTQIK). Tries same-day source first, falls back to T-1."""
    rows = _fetch_twse_fmtqik_www()
    if rows:
        return rows
    # Fallback: openapi.twse.com.tw lags by ~1 day but is more stable
    try:
        request = urllib.request.Request(
            _TWSE_FMTQIK_URL,
            headers={"User-Agent": "market-core/1.0"},
        )
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, context=context, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        _logger.warning("twse fmtqik fallback fetch failed: %s", exc)
        return []

    if not isinstance(payload, list):
        return []
    return sorted(payload, key=lambda row: str(row.get("Date", "")))


def latest_tw_trading_date() -> str | None:
    """Return latest TW trading date as ISO (YYYY-MM-DD) via FMTQIK."""
    rows = fetch_twse_fmtqik()
    if not rows:
        return None
    return _roc_date_to_iso(str(rows[-1].get("Date", "")))


def _roc_date_to_iso(roc: str) -> str | None:
    text = roc.strip()
    if len(text) != 7 or not text.isdigit():
        return None
    year = int(text[:3]) + 1911
    return f"{year:04d}-{text[3:5]}-{text[5:7]}"


_TWII_FUGLE_SYMBOL = "IX0001"


def _twse_taiex_quote(profile: MarketProfile) -> Quote | None:
    """Live TAIEX quote via Fugle IX0001 intraday feed."""
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        return None
    client = RestClient(api_key=api_key)
    payload = client.stock.intraday.quote(symbol=_TWII_FUGLE_SYMBOL)
    price = payload.get("closePrice") or payload.get("lastPrice")
    if price is None:
        return None

    last_updated_us = payload.get("lastUpdated")
    if last_updated_us:
        timestamp = datetime.fromtimestamp(last_updated_us / 1_000_000, tz=timezone.utc).isoformat()
    else:
        timestamp = utc_now_iso()

    total = payload.get("total") or {}
    trade_value = total.get("tradeValue")

    return Quote(
        symbol="^TWII",
        market_profile=profile.id,
        name="TAIEX",
        price=float(price),
        source="fugle",
        timestamp=timestamp,
        open=_safe_float(payload.get("openPrice")),
        high=_safe_float(payload.get("highPrice")),
        low=_safe_float(payload.get("lowPrice")),
        prev_close=_safe_float(payload.get("previousClose")),
        change=_safe_float(payload.get("change")),
        change_pct=_safe_float(payload.get("changePercent")),
        volume=_safe_int(trade_value),
    )


def _twse_taiex_benchmark_metrics(
    live_price: float | None = None,
    lookback_days: int = 90,
) -> dict[str, float] | None:
    """Compute SMA20 / ADX14 for TWII using Fugle IX0001 daily candles.

    When ``live_price`` is provided, ``dist_to_sma20_pct`` is computed against
    it so regime reflects the current intraday state instead of T-1 close.
    """
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        return None
    client = RestClient(api_key=api_key)
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    data = client.stock.historical.candles(**{
        "symbol": _TWII_FUGLE_SYMBOL,
        "timeframe": "D",
        "from": start.strftime("%Y-%m-%d"),
        "to": end.strftime("%Y-%m-%d"),
        "fields": "open,high,low,close,volume",
    })
    rows = data.get("data", []) if isinstance(data, dict) else data
    if not rows:
        return None

    rows = sorted(rows, key=lambda r: str(r.get("date", "")))
    bars = [
        Bar(
            symbol="^TWII",
            market_profile="tw_equity",
            bar_time=row["date"],
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=_safe_int(row.get("volume")),
            source="fugle",
        )
        for row in rows
    ]
    df_bars = bars_to_dataframe(bars)
    technical = build_technical_analysis(df_bars, default_analysis_config())

    vals = technical.values
    sma_20 = vals.get("sma_20")
    adx_14 = vals.get("adx_14")
    close = vals.get("close")

    metrics: dict[str, float] = {}
    if sma_20 is not None:
        metrics["sma_20"] = round(float(sma_20), 2)
    if adx_14 is not None:
        metrics["adx_14"] = round(float(adx_14), 4)

    reference_price = live_price if live_price is not None else (float(close) if close is not None else None)
    if reference_price is not None and sma_20 and sma_20 != 0:
        metrics["dist_to_sma20_pct"] = round((reference_price - float(sma_20)) / float(sma_20) * 100, 4)

    return metrics if metrics else None


def _is_tw_equity_symbol(symbol: str) -> bool:
    if not (symbol.endswith(".TW") or symbol.endswith(".TWO")):
        return False
    return symbol.removesuffix(".TW").removesuffix(".TWO").isdigit()


def _safe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _safe_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
