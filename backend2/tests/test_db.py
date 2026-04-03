import pytest
import os
import asyncio
from backend2 import db
from backend2.models import TradingState, TradeRecord

@pytest.fixture(autouse=True)
async def setup_db():
    # Use in-memory DB for tests
    os.environ["BACKEND2_DB_PATH"] = ":memory:"
    # Ensure a fresh connection for each test
    await db.close_connection()
    yield
    await db.close_connection()

@pytest.mark.asyncio
async def test_trading_state_persistence():
    ws_id = "test-ws"
    state = TradingState(cash=50000.0)
    
    # Initially None
    assert await db.get_trading_state(ws_id) is None
    
    # Save and retrieve
    await db.save_trading_state(ws_id, state)
    retrieved = await db.get_trading_state(ws_id)
    assert retrieved is not None
    assert retrieved.cash == 50000.0

@pytest.mark.asyncio
async def test_trade_records():
    ws_id = "test-ws"
    trade1 = TradeRecord(action="BUY", symbol="2330", quantity=1.0, price=1000.0, executed_at="2026-04-03T10:00:00Z")
    trade2 = TradeRecord(action="SELL", symbol="2330", quantity=1.0, price=1100.0, executed_at="2026-04-03T10:01:00Z")
    
    await db.insert_trade(ws_id, trade1)
    await db.insert_trade(ws_id, trade2)
    
    trades = await db.list_trades(ws_id)
    assert len(trades) == 2
    assert trades[0].action == "SELL" # Descending order
    assert trades[1].action == "BUY"

@pytest.mark.asyncio
async def test_market_snapshots():
    ws_id = "test-ws"
    snapshot_data = {"symbols": {"2330": {"price": 1000}}}
    
    await db.insert_market_snapshot(ws_id, "tw_equity", "live", snapshot_data)
    
    latest = await db.get_latest_market_snapshot(ws_id)
    assert latest == snapshot_data
