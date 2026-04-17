from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

# Re-export shared types from market-core
from market_core.models import (  # noqa: F401
    AnalysisReport,
    AnalysisSettings,
    Bar,
    MarketConfig,
    MarketOverview,
    NewsConfig,
    NewsItem,
    NewsSourceConfig,
    Quote,
    utc_now_iso,
)

# --- Backend2-only types below ---


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


class AgentConfig(BaseModel):
    enabled: bool = False
    strategy: str = ""
    prompt_file: str | None = None
    tags: list[str] = Field(default_factory=list)


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
