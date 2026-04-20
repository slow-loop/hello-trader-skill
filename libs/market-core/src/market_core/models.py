from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

# Paper-trading state lives here so multiple callers (backend2 legacy, future
# local skills) can share the same schema and engine.


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class NewsSourceConfig(BaseModel):
    name: str = ""
    kind: Literal["rss"] = "rss"
    url: str


class NewsConfig(BaseModel):
    enabled: bool = False
    max_items: int = 10
    sources: list[NewsSourceConfig] = Field(default_factory=list)


class AnalysisIndicatorConfig(BaseModel):
    name: str
    ta_fn: str
    params: dict[str, bool | int | float | str] = Field(default_factory=dict)


class AnalysisExpressionConfig(BaseModel):
    name: str
    expr: str
    tags: list[str] = Field(default_factory=list)


class AnalysisSettings(BaseModel):
    timeframe: Literal["1d", "1h"] = "1d"
    lookback_days: int = 180
    indicators: list[AnalysisIndicatorConfig] = Field(default_factory=list)
    expressions: list[AnalysisExpressionConfig] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class MarketConfig(BaseModel):
    profile: str
    benchmark_symbol: str | None = None


class MarketRuntimeConfig(BaseModel):
    market: MarketConfig
    news: NewsConfig = Field(default_factory=NewsConfig)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)


class Quote(BaseModel):
    symbol: str
    market_profile: str
    name: str | None = None
    price: float
    source: str
    timestamp: str = Field(default_factory=utc_now_iso)
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None


class Bar(BaseModel):
    symbol: str
    market_profile: str
    bar_time: str
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None
    source: str


class NewsItem(BaseModel):
    title: str
    url: str
    published: str = ""
    source: str = ""


class AnalysisReport(BaseModel):
    symbol: str
    quote: Quote
    metrics: dict[str, Any] = Field(default_factory=dict)
    triggers: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class AnalysisSnapshot(AnalysisReport):
    bars: list[Bar] = Field(default_factory=list)


class Position(BaseModel):
    quantity: float
    avg_price: float
    reason: str = ""
    opened_at: str = Field(default_factory=utc_now_iso)


class ExitOrder(BaseModel):
    stop_loss: float | None = None
    take_profit: float | None = None
    updated_at: str = Field(default_factory=utc_now_iso)


class TradingState(BaseModel):
    cash: float
    realized_pnl: float = 0.0
    positions: dict[str, Position] = Field(default_factory=dict)
    orders: dict[str, ExitOrder] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=utc_now_iso)


class TradeRecord(BaseModel):
    action: Literal["BUY", "SELL"]
    symbol: str
    quantity: float
    price: float
    executed_at: str = Field(default_factory=utc_now_iso)
    fee: float = 0.0
    reason: str = ""
    strategy: str = ""
    tags: list[str] = Field(default_factory=list)
    pnl: float | None = None
    market_snapshot: dict[str, Any] | None = None


class OrderRequest(BaseModel):
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""
    strategy: str = ""
    tags: list[str] = Field(default_factory=list)


class OrderUpdateRequest(BaseModel):
    symbol: str
    stop_loss: float | None = None
    take_profit: float | None = None


class WatchlistItem(BaseModel):
    symbol: str
    thesis: str = ""
    status: Literal["watch", "hold", "archived"] = "watch"
    notes: str = ""
    trigger: str = ""
    invalidation: str = ""
    trigger_conditions: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    trigger_price: float | None = None
    invalidation_price: float | None = None
    updated_at: str = ""


class WatchlistConfig(BaseModel):
    items: list[WatchlistItem] = Field(default_factory=list)


class WatchlistConditionResult(BaseModel):
    expr: str
    result: bool | None = None
    error: str | None = None


class WatchlistEvaluation(BaseModel):
    trigger_met: bool = False
    invalidation_met: bool = False
    trigger_results: list[WatchlistConditionResult] = Field(default_factory=list)
    invalidation_results: list[WatchlistConditionResult] = Field(default_factory=list)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    evaluated_at: str = Field(default_factory=utc_now_iso)
    error: str | None = None


class EvaluatedWatchlistItem(WatchlistItem):
    analysis: AnalysisReport | None = None
    evaluation: WatchlistEvaluation | None = None


class EvaluatedWatchlistConfig(BaseModel):
    items: list[EvaluatedWatchlistItem] = Field(default_factory=list)


class ScreenerResult(BaseModel):
    symbol: str
    name: str
    close: float
    change: float
    change_pct: float
    trade_value: float
    analysis: AnalysisReport | None = None
    chips: dict[str, Any] = Field(default_factory=dict)


class ScreenerResponse(BaseModel):
    strategy: str
    market_profile: str
    generated_at: str = Field(default_factory=utc_now_iso)
    items: list[ScreenerResult] = Field(default_factory=list)


class MarketOverview(BaseModel):
    workspace_id: str = ""
    timestamp: str = Field(default_factory=utc_now_iso)
    market_profile: str
    session: str
    is_open: bool
    reason: str
    benchmark_symbol: str | None = None
    benchmark_quote: Quote | None = None
    news: list[NewsItem] = Field(default_factory=list)
    watchlist_symbols: list[str] = Field(default_factory=list)
