"""Tests for scoring logic — pure functions, no network."""

from lana_copycat.scoring import score_candidates, _normalise
from lana_copycat.signals.binance_market import TickerSignal


def test_normalise_basic():
    assert _normalise([0.0, 5.0, 10.0]) == [0.0, 0.5, 1.0]


def test_normalise_single_value():
    result = _normalise([42.0])
    assert result == [1.0]


def test_normalise_all_same():
    result = _normalise([3.0, 3.0, 3.0])
    assert all(v == 1.0 for v in result)


def test_score_candidates_intersection():
    """Only tickers in BOTH square and market should be scored."""
    square_counts = {"ETH": 10, "SOL": 5, "DOGE": 3, "GHOST": 99}
    market = [
        TickerSignal("ETHUSDT", 8.5, 5e9, oi_change_pct=20.0, oi_ratio=2.3),
        TickerSignal("SOLUSDT", 5.2, 2e9, oi_change_pct=10.0, oi_ratio=1.9),
        TickerSignal("AVAXUSDT", 3.1, 1.5e9, oi_change_pct=5.0, oi_ratio=1.6),
    ]
    candidates = score_candidates(square_counts, market, top_n=5)

    symbols = [c.symbol for c in candidates]
    assert "ETHUSDT" in symbols
    assert "SOLUSDT" in symbols
    # DOGE has no market signal, GHOST has no market signal — excluded
    assert "DOGUSDT" not in symbols
    # AVAXUSDT is in market but not in square — excluded
    assert "AVAXUSDT" not in symbols


def test_score_candidates_ordering():
    """Highest combined score should come first."""
    square_counts = {"ETH": 20, "SOL": 2}
    market = [
        TickerSignal("ETHUSDT", 9.0, 5e9, oi_change_pct=25.0, oi_ratio=2.7),
        TickerSignal("SOLUSDT", 2.0, 1e9, oi_change_pct=1.0, oi_ratio=0.5),
    ]
    candidates = score_candidates(square_counts, market, top_n=2)
    assert candidates[0].symbol == "ETHUSDT"


def test_score_candidates_empty():
    assert score_candidates({}, [], top_n=5) == []


def test_score_candidates_no_intersection():
    square_counts = {"GHOST": 100}
    market = [TickerSignal("ETHUSDT", 5.0, 1e9)]
    assert score_candidates(square_counts, market) == []
