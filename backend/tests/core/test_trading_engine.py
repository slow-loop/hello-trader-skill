from unittest.mock import patch

from backend.core.trading_engine import (
    default_ledger,
    execute_order,
    validate_order,
    SpotPrice,
    _get_tick_size,
    _calc_limit_prices,
)
from backend.models import Position

def test_tick_size():
    assert _get_tick_size(5) == 0.01
    assert _get_tick_size(25) == 0.05
    assert _get_tick_size(150) == 0.5
    assert _get_tick_size(800) == 1.0
    assert _get_tick_size(1500) == 5.0

def test_limit_prices():
    # 100 * 1.1 = 110
    limit_up, limit_down = _calc_limit_prices(100.0)
    assert limit_up == 110.0
    assert limit_down == 90.0

    # Test tick rounding
    # 540 * 1.1 = 594. 594 // 1.0 * 1.0 = 594
    limit_up, limit_down = _calc_limit_prices(540.0)
    assert limit_up == 594.0
    assert limit_down == 486.0

def test_validate_order():
    spot = SpotPrice(symbol="2330", price=100.0, prev_close=100.0, market="tw", source="mock")
    
    # Normal buy
    ok, reason, fill = validate_order("2330", "BUY", 101.0, spot)
    assert ok is True
    assert fill == 101.0

    # Deviation rejection
    ok, reason, fill = validate_order("2330", "BUY", 105.0, spot)
    assert ok is False
    assert "deviates" in reason

    # Limit up rejection
    ok, reason, fill = validate_order("2330", "BUY", 112.0, spot)
    assert ok is False
    assert "exceeds limit-up" in reason

def test_execute_buy():
    ledger = default_ledger(1000000)
    with patch("backend.core.trading_engine.get_spot_price", return_value=SpotPrice(symbol="2330.TW", price=500.0, prev_close=500.0, market="tw", source="mock")), \
         patch("backend.core.trading_engine.get_twse_market_session", return_value="market_open"):
        
        msg, new_ledger, trade = execute_order(
            ledger, "2330", "BUY", 1000, price=505, stop_loss=450, reason="breakout"
        )
        
        assert trade is not None
        assert trade.action == "BUY"
        assert trade.price == 505
        assert "2330.TW" in new_ledger.positions
        assert new_ledger.positions["2330.TW"].shares == 1000
        assert new_ledger.cash < 1000000

def test_execute_sell():
    ledger = default_ledger(1000000)
    # Add manual position with normalized key
    ledger.positions["2330.TW"] = Position(shares=1000, avg_price=500.0, reason="buy")
    ledger.cash -= 500 * 1000
    
    with patch("backend.core.trading_engine.get_spot_price", return_value=SpotPrice(symbol="2330.TW", price=550.0, prev_close=500.0, market="tw", source="mock")), \
         patch("backend.core.trading_engine.get_twse_market_session", return_value="market_open"):
        
        msg, new_ledger, trade = execute_order(
            ledger, "2330", "SELL", 1000, price=550, reason="target reached"
        )
        
        assert trade is not None
        assert trade.action == "SELL"
        assert trade.pnl > 0
        assert "2330" not in new_ledger.positions
        assert new_ledger.realized_pnl > 0
