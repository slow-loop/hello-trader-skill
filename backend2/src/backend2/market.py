from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os

import feedparser
from fugle_marketdata import RestClient
import pandas as pd
import yfinance as yf

from backend2.models import AnalysisReport, Bar, MarketOverview, NewsItem, Quote, WorkspaceRuntimeConfig
from backend2.policies import MarketProfile, get_market_session, market_data_symbol, normalize_symbol
from backend2.technical import AnalysisConfig, ExpressionSpec, IndicatorSpec, build_technical_analysis, default_analysis_config
from backend2.workspace import (
    load_analysis_config as load_workspace_analysis_config,
    load_news_config as load_workspace_news_config,
    load_watchlist as load_workspace_watchlist,
)


def get_quote(symbol: str, profile: MarketProfile) -> Quote:
    normalized = normalize_symbol(symbol, profile)
    if profile.id == "tw_equity" and _is_tw_equity_symbol(normalized):
        fugle_quote = _try_fugle_quote(normalized, profile)
        if fugle_quote is not None:
            return fugle_quote

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
    data_symbol = market_data_symbol(normalized, profile)
    interval = timeframe
    if interval not in {"1d", "1h"}:
        raise ValueError("timeframe must be 1d or 1h")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    ticker = yf.Ticker(data_symbol)
    df = ticker.history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval=interval,
        auto_adjust=True,
    )
    if df.empty:
        raise ValueError(f"no bar data for {normalized}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower).reset_index()
    date_col = "date" if "date" in df.columns else df.columns[0]

    bars: list[Bar] = []
    for row in df.to_dict("records"):
        bars.append(
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
        )
    return bars


def build_overview(config: WorkspaceRuntimeConfig, profile: MarketProfile) -> MarketOverview:
    session = get_market_session(profile)
    benchmark_symbol = config.market.benchmark_symbol or profile.benchmark_symbol
    benchmark_quote = None
    if benchmark_symbol:
        try:
            benchmark_quote = get_quote(benchmark_symbol, profile)
        except Exception:
            benchmark_quote = None

    watchlist = load_workspace_watchlist(config)

    return MarketOverview(
        workspace_id=config.id,
        market_profile=profile.id,
        session=str(session["phase"]),
        is_open=bool(session["is_open"]),
        reason=str(session["reason"]),
        benchmark_symbol=benchmark_symbol,
        benchmark_quote=benchmark_quote,
        news=get_news(config),
        watchlist_symbols=[item.symbol for item in watchlist.items],
    )


def build_analysis(symbol: str, config: WorkspaceRuntimeConfig, profile: MarketProfile) -> AnalysisReport:
    quote = get_quote(symbol, profile)
    bars = get_bars(
        symbol,
        profile,
        timeframe=config.analysis.timeframe,
        lookback_days=config.analysis.lookback_days,
    )
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

    technical_config = _build_analysis_config(config)
    analysis = build_technical_analysis(df, technical_config)
    metrics = {
        key: (round(value, 4) if isinstance(value, float) else value)
        for key, value in analysis.values.items()
        if key in (technical_config.outputs or default_analysis_config().outputs)
    }

    return AnalysisReport(
        symbol=normalize_symbol(symbol, profile),
        quote=quote,
        metrics=metrics,
        triggers={tag: names for tag, names in analysis.triggers.items() if names},
        warnings=analysis.warnings,
        news=[item for item in get_news(config) if symbol.upper() in item.title.upper()],
    )


def get_news(config: WorkspaceRuntimeConfig) -> list[NewsItem]:
    news_config = load_workspace_news_config(config) or config.news
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


def _build_analysis_config(config: WorkspaceRuntimeConfig) -> AnalysisConfig:
    workspace_config = load_workspace_analysis_config(config)
    if workspace_config is not None:
        return workspace_config

    default = default_analysis_config()
    indicators = (
        [IndicatorSpec.model_validate(item.model_dump()) for item in config.analysis.indicators]
        if config.analysis.indicators
        else default.indicators
    )
    expressions = [ExpressionSpec.model_validate(item.model_dump()) for item in config.analysis.expressions]
    outputs = config.analysis.outputs or default.outputs
    return AnalysisConfig(indicators=indicators, expressions=expressions, outputs=outputs)


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
