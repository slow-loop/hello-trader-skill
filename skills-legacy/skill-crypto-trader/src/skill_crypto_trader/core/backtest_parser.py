"""Parse freqtrade backtest JSON results into structured metrics."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from skill_crypto_trader.journal.helpers import get_risk_rules_path


def parse_backtest_result(json_path: Path) -> dict:
    """Extract key metrics from freqtrade backtest JSON output."""
    raw = json.loads(json_path.read_text())

    # freqtrade stores results under strategy name key
    strategy_results = {}
    for key, val in raw.get("strategy", {}).items():
        strategy_results = val
        break

    if not strategy_results:
        # Try flat structure
        strategy_results = raw

    trades = strategy_results.get("trades", [])
    total_trades = len(trades)

    # Calculate metrics
    wins = sum(1 for t in trades if t.get("profit_ratio", 0) > 0)
    win_rate = wins / total_trades if total_trades > 0 else 0

    gross_profit = sum(
        t.get("profit_ratio", 0) for t in trades if t.get("profit_ratio", 0) > 0
    )
    gross_loss = abs(
        sum(t.get("profit_ratio", 0) for t in trades if t.get("profit_ratio", 0) < 0)
    )
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return {
        "total_trades": total_trades,
        "win_rate": round(win_rate, 4),
        "profit_factor": round(profit_factor, 4),
        "total_profit_pct": round(
            strategy_results.get("profit_total", 0) * 100, 2
        ),
        "max_drawdown_pct": round(
            strategy_results.get("max_drawdown", 0) * 100, 2
        ),
        "sharpe": round(strategy_results.get("sharpe", 0), 4),
        "sortino": round(strategy_results.get("sortino", 0), 4),
        "avg_profit_pct": round(
            strategy_results.get("profit_mean", 0) * 100, 4
        ),
        "avg_duration": strategy_results.get("holding_avg", "N/A"),
    }


def meets_threshold(result: dict, thresholds: dict | None = None) -> tuple[bool, list[str]]:
    """Check if backtest result meets promotion thresholds.

    Returns (passed, list_of_failures).
    """
    if thresholds is None:
        # Load from risk_rules.yaml
        rules_path = get_risk_rules_path()
        if rules_path.exists():
            rules = yaml.safe_load(rules_path.read_text()) or {}
            thresholds = rules.get("strategy_thresholds", {})
        else:
            thresholds = {}

    defaults = {
        "min_sharpe": 1.0,
        "max_drawdown_pct": 20.0,
        "min_win_rate": 0.40,
        "min_profit_factor": 1.3,
        "min_trades": 50,
    }
    thresholds = {**defaults, **thresholds}

    failures = []
    if result.get("sharpe", 0) < thresholds["min_sharpe"]:
        failures.append(
            f"Sharpe {result.get('sharpe', 0)} < {thresholds['min_sharpe']}"
        )
    if result.get("max_drawdown_pct", 100) > thresholds["max_drawdown_pct"]:
        failures.append(
            f"Max DD {result.get('max_drawdown_pct', 100)}% > {thresholds['max_drawdown_pct']}%"
        )
    if result.get("win_rate", 0) < thresholds["min_win_rate"]:
        failures.append(
            f"Win rate {result.get('win_rate', 0)} < {thresholds['min_win_rate']}"
        )
    if result.get("profit_factor", 0) < thresholds["min_profit_factor"]:
        failures.append(
            f"Profit factor {result.get('profit_factor', 0)} < {thresholds['min_profit_factor']}"
        )
    if result.get("total_trades", 0) < thresholds["min_trades"]:
        failures.append(
            f"Total trades {result.get('total_trades', 0)} < {thresholds['min_trades']}"
        )

    return (len(failures) == 0, failures)
