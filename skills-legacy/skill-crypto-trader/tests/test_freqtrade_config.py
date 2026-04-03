"""Tests for freqtrade config management."""

from skill_crypto_trader.core.freqtrade_config import (
    _deep_merge,
    validate_against_rules,
)


def test_deep_merge():
    base = {"a": 1, "b": {"c": 2, "d": 3}}
    overlay = {"b": {"c": 99}, "e": 5}
    result = _deep_merge(base, overlay)
    assert result["a"] == 1
    assert result["b"]["c"] == 99
    assert result["b"]["d"] == 3
    assert result["e"] == 5


def test_validate_against_rules_pass():
    config = {"max_open_trades": 5, "trading_mode": "spot"}
    rules = {"max_open_trades": 10, "max_leverage": 1}
    violations = validate_against_rules(config, rules)
    assert violations == []


def test_validate_against_rules_fail():
    config = {"max_open_trades": 15, "trading_mode": "spot"}
    rules = {"max_open_trades": 10, "max_leverage": 1}
    violations = validate_against_rules(config, rules)
    assert len(violations) == 1
    assert "max_open_trades" in violations[0]
