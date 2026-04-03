"""Tests for backtest result parsing."""

from skill_crypto_trader.core.backtest_parser import meets_threshold, parse_backtest_result
import json
import tempfile
from pathlib import Path


def test_meets_threshold_pass():
    result = {
        "sharpe": 1.5,
        "max_drawdown_pct": 12.0,
        "win_rate": 0.55,
        "profit_factor": 1.8,
        "total_trades": 100,
    }
    passed, failures = meets_threshold(result, {
        "min_sharpe": 1.0,
        "max_drawdown_pct": 20.0,
        "min_win_rate": 0.40,
        "min_profit_factor": 1.3,
        "min_trades": 50,
    })
    assert passed is True
    assert failures == []


def test_meets_threshold_fail():
    result = {
        "sharpe": 0.5,
        "max_drawdown_pct": 25.0,
        "win_rate": 0.35,
        "profit_factor": 1.0,
        "total_trades": 30,
    }
    passed, failures = meets_threshold(result, {
        "min_sharpe": 1.0,
        "max_drawdown_pct": 20.0,
        "min_win_rate": 0.40,
        "min_profit_factor": 1.3,
        "min_trades": 50,
    })
    assert passed is False
    assert len(failures) == 5  # All fail
