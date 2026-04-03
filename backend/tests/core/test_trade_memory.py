import math
from backend.core.trade_memory import (
    _safe_float,
    _weighted_distance,
    recall_similar_trades,
    compute_performance,
    SNAPSHOT_KEYS
)

def test_safe_float():
    assert _safe_float(None, 0.0) == 0.0
    assert _safe_float("123.5", 0.0) == 123.5
    assert _safe_float(math.nan, 50.0) == 50.0
    assert _safe_float("abc", 10.0) == 10.0

def test_weighted_distance():
    a = {k: 0.0 for k in SNAPSHOT_KEYS}
    b = {k: 0.0 for k in SNAPSHOT_KEYS}
    
    assert _weighted_distance(a, b) == 0.0
    
    # Change one field
    # rsi_14 weight is 1/100
    a["rsi_14"] = 100.0
    b["rsi_14"] = 0.0
    # dist = sqrt((1/100 * 100)**2) = 1.0
    assert _weighted_distance(a, b) == 1.0

def test_recall_similar_trades():
    current = {k: 0.0 for k in SNAPSHOT_KEYS}
    history = [
        {"id": 1, "market_snapshot": {k: 0.1 for k in SNAPSHOT_KEYS}}, # Close
        {"id": 2, "market_snapshot": {k: 100 for k in SNAPSHOT_KEYS}}, # Far
        {"id": 3, "market_snapshot": {k: 0.05 for k in SNAPSHOT_KEYS}}, # Closest
    ]
    
    recalled = recall_similar_trades(current, history, top_k=2)
    assert len(recalled) == 2
    assert recalled[0]["id"] == 3 # Closest
    assert recalled[1]["id"] == 1 # Second closest

def test_compute_performance():
    history = [
        {"action": "SELL", "strategy": "momentum", "pnl": 1000, "pnl_r": 2.0},
        {"action": "SELL", "strategy": "momentum", "pnl": -500, "pnl_r": -1.0},
        {"action": "SELL", "strategy": "value", "pnl": 2000, "pnl_r": 3.0},
        {"action": "BUY", "strategy": "value", "pnl": 0}, # Should be ignored
    ]
    
    stats = compute_performance(history)
    assert stats["momentum"]["trades"] == 2
    assert stats["momentum"]["wins"] == 1
    assert stats["momentum"]["win_rate"] == 0.5
    assert stats["momentum"]["total_pnl"] == 500
    assert stats["momentum"]["avg_pnl_r"] == 0.5 # (2 - 1) / 2
    
    assert stats["value"]["trades"] == 1
    assert stats["value"]["total_pnl"] == 2000
