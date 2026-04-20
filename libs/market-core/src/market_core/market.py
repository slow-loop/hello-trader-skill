from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import feedparser
from fugle_marketdata import RestClient
import pandas as pd
import yfinance as yf

from market_core.models import AnalysisReport, AnalysisSnapshot, Bar, MarketOverview, MarketRuntimeConfig, NewsItem, Quote
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
    if benchmark_symbol:
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


def _try_fugle_bars(
    symbol: str,
    profile: MarketProfile,
    *,
    timeframe: str = "1d",
    lookback_days: int = 180,
) -> list[Bar] | None:
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        return None
    try:
        client = RestClient(api_key=api_key)
        stock_id = symbol.removesuffix(".TW").removesuffix(".TWO")
        tf = "D" if timeframe == "1d" else "60"
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
    except Exception:
        return None


def _try_fugle_quote(symbol: str, profile: MarketProfile) -> Quote | None:
    api_key = os.getenv("FUGLE_API_KEY")
    if not api_key:
        return None
    try:
        client = RestClient(api_key=api_key)
        stock_id = symbol.removesuffix(".TW").removesuffix(".TWO")
        payload = client.stock.intraday.quote(symbol=stock_id)
        ticker = client.stock.intraday.ticker(symbol=stock_id)
        price = payload.get("lastPrice") or payload.get("closePrice")
        if price is None:
            return None
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
            change_pct=_safe_float(payload.get("changePercent")),
            volume=_safe_int(payload.get("tradeVolume")),
        )
    except Exception:
        return None


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
