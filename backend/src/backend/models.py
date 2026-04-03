"""
models.py — Single source of truth for all Pydantic models.

Every layer (DB, engine, services, routes) imports from here.
No raw dicts cross module boundaries.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ── DB / Agent ────────────────────────────────────────────────────────────────

class AgentRow(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    name: str
    config: Dict[str, Any] = {}
    is_active: bool = True


# ── Trading Core ──────────────────────────────────────────────────────────────

class Position(BaseModel):
    """Open position for one symbol."""
    model_config = ConfigDict(frozen=False)

    shares: int
    avg_price: float
    reason: str = ""
    entry_date: str = Field(default_factory=lambda: date.today().isoformat())


class PendingOrder(BaseModel):
    """Stop-loss / take-profit order attached to a position."""
    model_config = ConfigDict(frozen=False)

    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    trigger: Optional[str] = None  # "stop_loss" | "take_profit" when auto-triggered


class Ledger(BaseModel):
    """Full account state: cash + open positions + pending orders."""
    model_config = ConfigDict(frozen=False)

    cash: float = 1_000_000.0
    realized_pnl: float = 0.0
    positions: Dict[str, Position] = Field(default_factory=dict)
    orders: Dict[str, PendingOrder] = Field(default_factory=dict)


class TradeRecord(BaseModel):
    """Immutable record of an executed trade (BUY or SELL)."""
    model_config = ConfigDict(frozen=False)

    action: Literal["BUY", "SELL"]
    symbol: str
    quantity: int
    price: float
    fee: float = 0.0
    reason: str = ""
    strategy: str = ""
    tags: List[str] = []
    confidence: Optional[float] = None
    executed_at: str  # ISO datetime string

    # BUY only
    total_cost: Optional[float] = None

    # SELL only
    tax_and_fee: Optional[float] = None
    net_revenue: Optional[float] = None
    pnl: Optional[float] = None
    pnl_r: Optional[float] = None

    # Auto-triggered by stop-loss / take-profit
    trigger: Optional[str] = None

    # Context snapshot at time of trade
    market_snapshot: Optional[Dict[str, Any]] = None


# ── Portfolio Status ──────────────────────────────────────────────────────────

class PositionStatus(BaseModel):
    """Enriched position with live price and P&L."""
    symbol: str
    shares: int
    avg_price: float
    cost: float
    reason: str = ""
    current_price: Optional[float] = None
    market_value: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    allocation_pct: Optional[float] = None


class OrderStatus(BaseModel):
    """Order status with distance-to-trigger calculations."""
    symbol: str
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    dist_to_stop_pct: Optional[float] = None
    dist_to_take_pct: Optional[float] = None


class PortfolioSummary(BaseModel):
    """Aggregate account metrics."""
    account_value: float
    market_value: float
    unrealized_pnl: float
    realized_pnl: float
    exposure_pct: float
    cash_pct: float
    today_realized_pnl: float
    today_realized_pnl_pct: float


class TodayTrade(BaseModel):
    """Simplified trade entry for today's summary."""
    action: str
    symbol: str
    quantity: int
    price: float
    pnl: Optional[float] = None


class PortfolioStatus(BaseModel):
    """Full portfolio view returned by the portfolio endpoint."""
    cash: float
    positions: List[PositionStatus]
    orders: List[OrderStatus]
    summary: PortfolioSummary
    alerts: List[str] = []
    today_trades: List[TodayTrade] = []


# ── Equity Snapshot ───────────────────────────────────────────────────────────

class EquitySnapshot(BaseModel):
    """Daily equity curve data point."""
    date: str
    account_value: float
    cash: float
    market_value: float
    realized_pnl: float
    unrealized_pnl: float
    exposure_pct: float
    positions_count: int


# ── Market Data ───────────────────────────────────────────────────────────────

class NewsItem(BaseModel):
    """Public-facing news item (no internal fields)."""
    title: str
    url: str
    published: str
    symbols: List[str] = []


class ChipsSummary(BaseModel):
    """Institutional investor chip data summary."""
    trade_date: str
    foreign_net: Optional[float] = None
    trust_net: Optional[float] = None
    dealer_net: Optional[float] = None
    margin_balance: Optional[float] = None
    margin_balance_trend: Optional[str] = None
    foreign_investors: Optional[str] = None
    investment_trust: Optional[str] = None
    dealer: Optional[str] = None


class QuoteSummary(BaseModel):
    """Lightweight quote used inside stock analysis."""
    name: Optional[str] = None
    price: float
    change: Optional[float] = None
    change_pct: Optional[float] = None
    source: str


class StockAnalysis(BaseModel):
    """Full technical + chips + news analysis for one symbol."""
    symbol: str
    quote: QuoteSummary
    metrics: Dict[str, Any] = {}
    triggers: Dict[str, List[str]] = {}
    warnings: List[str] = []
    chips: Optional[ChipsSummary] = None
    news: Optional[List[NewsItem]] = None


class MarketInfo(BaseModel):
    """TAIEX index snapshot and market open status."""
    taiex: Optional[float] = None
    change_pct: Optional[float] = None
    trend: Optional[str] = None
    is_open: bool = False
    reason: Optional[str] = None


class MarketOverview(BaseModel):
    """High-level market snapshot stored after each session."""
    date: str
    session: str
    market: MarketInfo
    headlines: List[NewsItem] = []


class HistoryRecord(BaseModel):
    """One OHLCV bar for API response."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


# ── Screener ──────────────────────────────────────────────────────────────────

class ScreenerResult(BaseModel):
    """One stock row from the momentum screener."""
    model_config = ConfigDict(frozen=False)  # enrichment mutates fields in place

    symbol: str
    name: str
    close: float
    change: float
    change_pct: float
    trade_value: float  # 百萬台幣

    # Technical indicators (filled by enrich)
    rsi_14: Optional[float] = None
    adx_14: Optional[float] = None
    volume_ratio_20: Optional[float] = None
    bb_position_ratio: Optional[float] = None

    # Chips (filled by enrich)
    foreign_net_days: int = 0
    trust_net_days: int = 0
    margin_trend: str = ""

    # Expression triggers
    triggers: List[str] = Field(default_factory=list)
