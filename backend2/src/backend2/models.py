from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


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


class WorkspaceConfig(BaseModel):
    root_dir: str = ""
    technical_config: str = "data/config/technical_config.yaml"
    news_config: str = "data/config/news.yaml"
    account_dir: str = "data/account"


class RiskConfig(BaseModel):
    execution_mode: Literal["paper", "live"] = "paper"
    initial_cash: float | None = None
    max_positions: int | None = None
    max_position_pct: float | None = None
    stop_loss_required: bool = True
    max_price_deviation_pct: float = 0.03


class WatchlistItem(BaseModel):
    symbol: str
    thesis: str = ""
    status: Literal["watch", "hold", "archived"] = "watch"
    notes: str = ""
    trigger: str = ""
    invalidation: str = ""
    trigger_price: float | None = None
    invalidation_price: float | None = None
    updated_at: str = ""


class WatchlistConfig(BaseModel):
    items: list[WatchlistItem] = Field(default_factory=list)


class AgentConfig(BaseModel):
    enabled: bool = False
    strategy: str = ""
    prompt_file: str | None = None
    tags: list[str] = Field(default_factory=list)


class MarketConfig(BaseModel):
    profile: str
    benchmark_symbol: str | None = None


class ScheduleConfig(BaseModel):
    enabled: bool = False
    snapshot_interval_minutes: int = 30


class WorkspaceRuntimeConfig(BaseModel):
    id: str = "default"
    name: str
    market: MarketConfig
    workspace: WorkspaceConfig = Field(default_factory=WorkspaceConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    news: NewsConfig = Field(default_factory=NewsConfig)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    watchlist: WatchlistConfig = Field(default_factory=WatchlistConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    metadata: dict[str, Any] = Field(default_factory=dict)


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


class MarketOverview(BaseModel):
    workspace_id: str
    timestamp: str = Field(default_factory=utc_now_iso)
    market_profile: str
    session: str
    is_open: bool
    reason: str
    benchmark_symbol: str | None = None
    benchmark_quote: Quote | None = None
    news: list[NewsItem] = Field(default_factory=list)
    watchlist_symbols: list[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    symbol: str
    quote: Quote
    metrics: dict[str, Any] = Field(default_factory=dict)
    triggers: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)


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


class PositionStatus(BaseModel):
    symbol: str
    quantity: float
    avg_price: float
    cost: float
    reason: str = ""
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    allocation_pct: float | None = None


class OrderStatus(BaseModel):
    symbol: str
    stop_loss: float | None = None
    take_profit: float | None = None
    dist_to_stop_pct: float | None = None
    dist_to_take_pct: float | None = None


class WorkspaceStatus(BaseModel):
    workspace_id: str
    name: str
    market_profile: str
    cash: float
    realized_pnl: float
    account_value: float
    market_value: float
    exposure_pct: float
    positions: list[PositionStatus] = Field(default_factory=list)
    orders: list[OrderStatus] = Field(default_factory=list)
    today_trades: list[TradeRecord] = Field(default_factory=list)


class JournalEntry(BaseModel):
    at: str = ""
    type: str = "note"
    actions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class JournalDocument(BaseModel):
    date: str
    entries: list[JournalEntry] = Field(default_factory=list)


class JournalSummary(BaseModel):
    date: str
    entry_count: int


class LessonsDocument(BaseModel):
    content: str = ""


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
