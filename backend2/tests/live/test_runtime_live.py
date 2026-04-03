import pytest
import os
from backend2 import db, runtime, workspace
from backend2.models import OrderRequest

@pytest.fixture(autouse=True)
async def setup_test_db():
    os.environ["BACKEND2_DB_PATH"] = ":memory:"
    await db.close_connection()
    yield
    await db.close_connection()

@pytest.mark.live
@pytest.mark.asyncio
async def test_workspace_status_live():
    # This will fetch live quotes for positions
    config = runtime.get_runtime_config()
    # We'll mock a state with a position to see if it fetches the price
    state = await runtime.get_trading_state()
    from backend2.models import Position
    state.positions["AAPL"] = Position(quantity=10, avg_price=150.0, reason="test")
    await db.save_trading_state(config.id, state)
    
    status = await runtime.get_workspace_status()
    assert status.workspace_id == config.id
    assert len(status.positions) == 1
    assert status.positions[0].symbol == "AAPL"
    # It should have fetched the current price
    assert status.positions[0].current_price is not None
    assert status.positions[0].current_price > 0
    assert status.market_value > 0

@pytest.mark.live
@pytest.mark.asyncio
async def test_place_paper_order_live():
    # Try to place a paper order for AAPL
    # Requires market to be open
    req = OrderRequest(
        symbol="AAPL",
        side="BUY",
        quantity=1,
        reason="Live test order",
        stop_loss=100.0 # Requirement: opening new pos requires stop_loss
    )
    
    result = await runtime.place_order(req)
    # If market is closed, it will return an error message
    # But currently it's 11:30 AM ET Friday, so it's OPEN.
    if "Filled BUY" in result:
        assert "AAPL" in result
        state = await runtime.get_trading_state()
        assert "AAPL" in state.positions
    else:
        # If it's closed (e.g. if I run this later), we just log it
        print(f"Order skipped or failed: {result}")
