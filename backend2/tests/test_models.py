from backend2.models import (
    Quote, 
    Position, 
    TradingState, 
    OrderRequest, 
    utc_now_iso
)
from datetime import datetime

def test_utc_now_iso():
    ts = utc_now_iso()
    assert ts.endswith("Z")
    assert "T" in ts
    # Basic format check: 2026-04-03T23:18:58Z
    dt = datetime.fromisoformat(ts[:-1])
    assert dt.year >= 2024

def test_quote_model():
    q = Quote(
        symbol="AAPL",
        market_profile="us_equity",
        price=150.0,
        source="yfinance",
    )
    assert q.symbol == "AAPL"
    assert q.price == 150.0
    assert q.timestamp.endswith("Z")

def test_trading_state_defaults():
    state = TradingState(cash=1000000.0)
    assert state.cash == 1000000.0
    assert state.realized_pnl == 0.0
    assert state.positions == {}
    assert state.orders == {}

def test_position_model():
    pos = Position(quantity=10.0, avg_price=10.0, reason="test")
    assert pos.quantity == 10.0
    assert pos.avg_price == 10.0
    assert pos.reason == "test"
    assert pos.opened_at.endswith("Z")
