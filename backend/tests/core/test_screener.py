from unittest.mock import patch
from backend.core.screener import (
    _net_buy_streak,
    _margin_trend,
    run_momentum_screener,
)
from backend.models import ScreenerResult

def test_net_buy_streak():
    class Row:
        def __init__(self, val):
            self.foreign_net = val
            self.trust_net = val
    
    # Positive streak
    rows = [Row(100), Row(200), Row(300)]
    assert _net_buy_streak(rows, "foreign_net") == 3
    
    # Negative streak
    rows_neg = [Row(-100), Row(-200), Row(-300)]
    assert _net_buy_streak(rows_neg, "foreign_net") == -3
    
    # Direction change
    rows_mix = [Row(100), Row(-200), Row(300)]
    assert _net_buy_streak(rows_mix, "foreign_net") == 1
    
    # Zero break
    rows_zero = [Row(100), Row(0), Row(300)]
    assert _net_buy_streak(rows_zero, "foreign_net") == 1

def test_margin_trend():
    class RowMargin:
        def __init__(self, val):
            self.margin_balance = val
    
    # Stable
    rows = [RowMargin(100), RowMargin(102), RowMargin(103)]
    assert _margin_trend(rows) == "STABLE"
    
    # Increasing (>5%)
    rows_inc = [RowMargin(100)] + [RowMargin(106)]
    assert _margin_trend(rows_inc) == "INCREASING"
    
    # Decreasing (< -5%)
    rows_dec = [RowMargin(100)] + [RowMargin(94)]
    assert _margin_trend(rows_dec) == "DECREASING"

def test_momentum_screener_filters():
    mock_data = [
        {"Code": "2330", "Name": "TSMC", "TradeValue": 2_000_000_000, "Change": 5.0, "ClosingPrice": 600.0}, # Pass
        {"Code": "0050", "Name": "ETF", "TradeValue": 2_000_000_000, "Change": 5.0, "ClosingPrice": 150.0}, # Fail len(code)
        {"Code": "1101", "Name": "Cement", "TradeValue": 500_000_000, "Change": 1.0, "ClosingPrice": 50.0}, # Fail min_trade_value
        {"Code": "1234", "Name": "Red", "TradeValue": 2_000_000_000, "Change": -1.0, "ClosingPrice": 49.0}, # Fail change > 0
    ]
    
    with patch("backend.core.screener._fetch_twse_snapshot", return_value=mock_data), \
         patch("backend.core.screener._enrich_result", side_effect=lambda x: x):
        
        results = run_momentum_screener(enrich=False)
        assert len(results) == 2
        assert results[0].symbol == "2330"
        assert results[0].trade_value == 2000.0
