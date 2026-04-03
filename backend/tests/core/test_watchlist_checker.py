from unittest.mock import patch
from backend.core.watchlist_checker import _eval_conditions, check_watchlist_triggers

def test_eval_conditions():
    context = {"close": 100, "rsi_14": 75}
    conditions = ["close > 90", "rsi_14 < 70"]
    
    results = _eval_conditions(conditions, context)
    assert results[0]["result"] is True
    assert results[1]["result"] is False

def test_check_watchlist_triggers_price_met():
    watchlist = [
        {
            "symbol": "2330.TW",
            "status": "watch",
            "trigger_price": 600,
            "trigger_conditions": []
        }
    ]
    
    # Mock context and market status
    context = {"close": 610}
    market_status = {"is_open": True}
    quote = type('obj', (object,), {'price': 610})
    
    with patch("backend.core.watchlist_checker._build_eval_context", return_value=context), \
         patch("backend.core.watchlist_checker.get_twse_market_status", return_value=market_status), \
         patch("backend.core.watchlist_checker.get_quote", return_value=quote):
        
        results = check_watchlist_triggers(watchlist)
        assert results[0]["trigger_met"] is True
        assert results[0]["context_snapshot"]["live_price"] == 610

def test_check_watchlist_triggers_conditions_met():
    watchlist = [
        {
            "symbol": "2330.TW",
            "status": "watch",
            "trigger_conditions": ["rsi_14 > 70", "close > 600"]
        }
    ]
    
    context = {"close": 610, "rsi_14": 75}
    market_status = {"is_open": False}
    
    with patch("backend.core.watchlist_checker._build_eval_context", return_value=context), \
         patch("backend.core.watchlist_checker.get_twse_market_status", return_value=market_status):
        
        results = check_watchlist_triggers(watchlist)
        assert results[0]["trigger_met"] is True
        assert len(results[0]["trigger_results"]) == 2
