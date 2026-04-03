"""Tests for strategy registry CRUD operations."""

import tempfile
from pathlib import Path

import yaml

from skill_crypto_trader.core.strategy_registry import (
    add_strategy,
    get_strategy,
    list_by_status,
    load_registry,
    promote,
    record_backtest,
    retire,
    save_registry,
)


def _tmp_registry():
    """Create a temp registry file for testing."""
    tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False)
    Path(tmp.name).write_text(yaml.dump({"strategies": []}))
    return Path(tmp.name)


def test_add_and_get(monkeypatch):
    path = _tmp_registry()
    monkeypatch.setattr(
        "skill_crypto_trader.core.strategy_registry.get_registry_path",
        lambda: path,
    )

    entry = add_strategy("test_v1", regime="trending_up", description="test")
    assert entry["name"] == "test_v1"
    assert entry["status"] == "candidate"

    found = get_strategy("test_v1")
    assert found is not None
    assert found["regime"] == "trending_up"


def test_promote(monkeypatch):
    path = _tmp_registry()
    monkeypatch.setattr(
        "skill_crypto_trader.core.strategy_registry.get_registry_path",
        lambda: path,
    )

    add_strategy("test_v1")
    s = promote("test_v1")
    assert s["status"] == "validated"

    s = promote("test_v1")
    assert s["status"] == "active"


def test_list_by_status(monkeypatch):
    path = _tmp_registry()
    monkeypatch.setattr(
        "skill_crypto_trader.core.strategy_registry.get_registry_path",
        lambda: path,
    )

    add_strategy("a")
    add_strategy("b")
    promote("a")

    candidates = list_by_status("candidate")
    assert len(candidates) == 1
    assert candidates[0]["name"] == "b"

    validated = list_by_status("validated")
    assert len(validated) == 1
    assert validated[0]["name"] == "a"


def test_record_backtest(monkeypatch):
    path = _tmp_registry()
    monkeypatch.setattr(
        "skill_crypto_trader.core.strategy_registry.get_registry_path",
        lambda: path,
    )

    add_strategy("test_v1")
    record_backtest("test_v1", {"sharpe": 1.5, "win_rate": 0.55})

    s = get_strategy("test_v1")
    assert len(s["backtest_results"]) == 1
    assert s["backtest_results"][0]["sharpe"] == 1.5
