from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_timestamp(value: Any) -> Any:
    """Coerce a timestamp into canonical UTC ISO-8601 (``YYYY-MM-DDTHH:MM:SSZ``).

    Accepts an ISO-8601 string (with ``Z`` or explicit offset) or a timezone-aware
    ``datetime``. Naive values are rejected — every timestamp entering a model
    must carry explicit timezone information. Producers (data adapters, etc.)
    are responsible for tagging their inputs at the source.

    This is the single point that enforces the model invariant: any timestamp
    field on any model holds canonical UTC ISO-8601 with a ``Z`` suffix, which
    makes string-level lexicographic comparison correct across the codebase.
    """
    if value is None or value == "":
        return value
    if isinstance(value, str):
        text = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    elif isinstance(value, datetime):
        dt = value
    else:
        raise TypeError(
            f"timestamp must be str or datetime, got {type(value).__name__}"
        )
    if dt.tzinfo is None:
        raise ValueError(
            f"naive timestamp {value!r}: provide explicit timezone "
            "(e.g. '...Z' or '...+08:00'). Tag at the data source, not here."
        )
    return (
        dt.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


# Use ``Timestamp`` for required timestamp fields and ``OptionalTimestamp``
# for nullable ones. Empty strings on optional fields pass through unchanged.
Timestamp = Annotated[str, BeforeValidator(_normalize_timestamp)]
OptionalTimestamp = Annotated[str | None, BeforeValidator(_normalize_timestamp)]


def new_order_id() -> str:
    return uuid.uuid4().hex[:12]


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
    timestamp: Timestamp = Field(default_factory=utc_now_iso)
    open: float | None = None
    high: float | None = None
    low: float | None = None
    prev_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    is_limit_up: bool = False
    is_limit_down: bool = False
    is_halted: bool = False


class Bar(BaseModel):
    symbol: str
    market_profile: str
    bar_time: Timestamp
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
    opened_at: Timestamp = Field(default_factory=utc_now_iso)


OrderType = Literal["MARKET", "LIMIT", "STOP_LOSS", "TAKE_PROFIT"]
OrderStatus = Literal["PENDING", "FILLED", "CANCELLED"]


class Order(BaseModel):
    """Unified order model — entry (MARKET/LIMIT) and exit (STOP_LOSS/TAKE_PROFIT).

    Lifecycle: PENDING → FILLED | CANCELLED. The fill engine evaluates pending
    orders against quotes (MARKET) or bars since placed_at (LIMIT/STOP/TAKE).
    """

    id: str = Field(default_factory=new_order_id)
    symbol: str
    side: Literal["BUY", "SELL"]
    type: OrderType
    quantity: float
    limit_price: float | None = None
    trigger_price: float | None = None
    status: OrderStatus = "PENDING"
    placed_at: Timestamp = Field(default_factory=utc_now_iso)
    filled_at: OptionalTimestamp = None
    fill_price: float | None = None
    cancelled_at: OptionalTimestamp = None
    cancelled_reason: str | None = None
    # Entry orders may carry attached exit levels — created as separate orders on fill.
    attach_stop_loss: float | None = None
    attach_take_profit: float | None = None
    reason: str = ""
    strategy: str = ""
    tags: list[str] = Field(default_factory=list)


class TradingState(BaseModel):
    cash: float
    realized_pnl: float = 0.0
    positions: dict[str, Position] = Field(default_factory=dict)
    orders: list[Order] = Field(default_factory=list)
    updated_at: Timestamp = Field(default_factory=utc_now_iso)


class TradeRecord(BaseModel):
    action: Literal["BUY", "SELL"]
    symbol: str
    quantity: float
    price: float
    executed_at: Timestamp = Field(default_factory=utc_now_iso)
    fee: float = 0.0
    reason: str = ""
    strategy: str = ""
    tags: list[str] = Field(default_factory=list)
    pnl: float | None = None
    order_id: str | None = None
    market_snapshot: dict[str, Any] | None = None


class OrderRequest(BaseModel):
    """Caller-facing order intent. Becomes one Order via place_order()."""

    symbol: str
    side: Literal["BUY", "SELL"]
    type: Literal["MARKET", "LIMIT"] = "MARKET"
    quantity: float
    limit_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str = ""
    strategy: str = ""
    tags: list[str] = Field(default_factory=list)


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


class RelativePerformance(BaseModel):
    symbol_change_pct: float | None = None
    benchmark_symbol: str | None = None
    benchmark_change_pct: float | None = None
    excess_vs_benchmark_pct: float | None = None


class WatchlistEvaluation(BaseModel):
    trigger_met: bool = False
    invalidation_met: bool = False
    trigger_results: list[WatchlistConditionResult] = Field(default_factory=list)
    invalidation_results: list[WatchlistConditionResult] = Field(default_factory=list)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    relative_performance: RelativePerformance | None = None
    evaluated_at: Timestamp = Field(default_factory=utc_now_iso)
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
    generated_at: Timestamp = Field(default_factory=utc_now_iso)
    # Trading-day date string (e.g. "2026-04-21"), not a UTC timestamp.
    as_of: str | None = None
    items: list[ScreenerResult] = Field(default_factory=list)


class MarketOverview(BaseModel):
    workspace_id: str = ""
    timestamp: Timestamp = Field(default_factory=utc_now_iso)
    market_profile: str
    session: str
    is_open: bool
    reason: str
    benchmark_symbol: str | None = None
    benchmark_quote: Quote | None = None
    benchmark_metrics: dict[str, float] | None = None
    news: list[NewsItem] = Field(default_factory=list)
    watchlist_symbols: list[str] = Field(default_factory=list)
