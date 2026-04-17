from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from market_core import get_quote, get_bars, bars_to_dataframe, get_news as _mc_get_news
from market_core.policies import MarketProfile, get_market_session, normalize_symbol
from market_core.technical import (
    AnalysisConfig,
    ExpressionSpec,
    IndicatorSpec,
    TechnicalAnalysis,
    build_technical_analysis,
    default_analysis_config,
)
from market_core.data.tw import build_tw_company_context

from backend2.models import AnalysisReport, Bar, MarketOverview, NewsItem, Quote, WorkspaceRuntimeConfig
from backend2.workspace import (
    load_analysis_config as load_workspace_analysis_config,
    load_news_config as load_workspace_news_config,
    load_watchlist as load_workspace_watchlist,
)


@dataclass
class AnalysisSnapshot:
    symbol: str
    quote: Quote
    bars: list[Bar]
    dataframe: pd.DataFrame
    technical_config: AnalysisConfig
    technical_analysis: TechnicalAnalysis


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
    snapshot = analyze_symbol(symbol, config, profile)
    analysis = snapshot.technical_analysis
    technical_config = snapshot.technical_config
    metrics = {
        key: (round(value, 4) if isinstance(value, float) else value)
        for key, value in analysis.values.items()
        if key in (technical_config.outputs or default_analysis_config().outputs)
    }

    # Enrich with TW official data (revenue, valuation, peers, insider, chips)
    tw_context: dict = {}
    if profile.id == "tw_equity":
        try:
            tw_context = build_tw_company_context(snapshot.symbol, latest_price=snapshot.quote.price)
        except Exception:
            pass

    return AnalysisReport(
        symbol=snapshot.symbol,
        quote=snapshot.quote,
        metrics=metrics,
        triggers={tag: names for tag, names in analysis.triggers.items() if names},
        warnings=analysis.warnings,
        news=[item for item in get_news(config) if symbol.upper() in item.title.upper()],
        extra=tw_context,
    )


def analyze_symbol(symbol: str, config: WorkspaceRuntimeConfig, profile: MarketProfile) -> AnalysisSnapshot:
    quote = get_quote(symbol, profile)
    bars = get_bars(
        symbol,
        profile,
        timeframe=config.analysis.timeframe,
        lookback_days=config.analysis.lookback_days,
    )
    df = bars_to_dataframe(bars)
    technical_config = _build_analysis_config(config)
    analysis = build_technical_analysis(df, technical_config)
    return AnalysisSnapshot(
        symbol=normalize_symbol(symbol, profile),
        quote=quote,
        bars=bars,
        dataframe=df,
        technical_config=technical_config,
        technical_analysis=analysis,
    )


def get_news(config: WorkspaceRuntimeConfig) -> list[NewsItem]:
    news_config = load_workspace_news_config(config) or config.news
    if not news_config.enabled or not news_config.sources:
        return []

    import feedparser

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
