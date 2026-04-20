from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from backend2.models import (
    AnalysisSettings,
    MarketConfig,
    Quote,
    WatchlistConfig,
    WatchlistItem,
    WorkspaceConfig,
    WorkspaceRuntimeConfig,
)
from market_core import get_market_profile
from backend2.watchlist import load_evaluated_watchlist
from backend2.workspace import save_watchlist


def _make_workspace(tmp_path: Path, *, technical_config: dict | None = None) -> WorkspaceRuntimeConfig:
    root = tmp_path / "watchlist_workspace"
    (root / "data/config").mkdir(parents=True)
    (root / "data/account").mkdir(parents=True)

    if technical_config is not None:
        (root / "data/config/technical_config.yaml").write_text(
            yaml.safe_dump(technical_config, sort_keys=False),
            encoding="utf-8",
        )

    return WorkspaceRuntimeConfig(
        id="watchlist-test",
        name="Watchlist Test",
        market=MarketConfig(profile="tw_equity"),
        workspace=WorkspaceConfig(
            root_dir=str(root),
            technical_config="data/config/technical_config.yaml",
            account_dir="data/account",
        ),
        analysis=AnalysisSettings(timeframe="1d", lookback_days=30),
        watchlist=WatchlistConfig(),
    )


def _analysis_snapshot(*, close: float, extra_values: dict | None = None) -> SimpleNamespace:
    values = {"close": close, **(extra_values or {})}
    return SimpleNamespace(
        symbol="2330.TW",
        quote=Quote(symbol="2330.TW", market_profile="tw_equity", price=close, source="test"),
        technical_config=SimpleNamespace(outputs=["close", *[key for key in values if key != "close"]]),
        technical_analysis=SimpleNamespace(values=values, triggers={"entry": ["breakout_ready"]}, warnings=[]),
    )


def test_evaluated_watchlist_uses_named_expression_labels(tmp_path, monkeypatch):
    config = _make_workspace(
        tmp_path,
        technical_config={
            "outputs": ["close"],
            "expressions": [
                {"name": "breakout_ready", "expr": "close > 110", "tags": ["entry"]},
            ],
        },
    )
    save_watchlist(
        config,
        WatchlistConfig(
            items=[
                WatchlistItem(
                    symbol="2330",
                    trigger_conditions=["breakout_ready"],
                    invalidation_conditions=["close < 90"],
                )
            ]
        ),
    )

    monkeypatch.setattr(
        "market_core.watchlist.engine.analyze_symbol",
        lambda *args, **kwargs: _analysis_snapshot(close=120, extra_values={"breakout_ready": True}),
    )
    monkeypatch.setattr(
        "market_core.watchlist.engine.get_market_session",
        lambda profile: {"is_open": False, "phase": "closed", "reason": "test"},
    )

    result = load_evaluated_watchlist(config, get_market_profile("tw_equity"))

    assert len(result.items) == 1
    item = result.items[0]
    assert item.analysis is not None
    assert item.analysis.metrics["close"] == 120
    assert item.evaluation is not None
    assert item.evaluation.trigger_met is True
    assert item.evaluation.invalidation_met is False
    assert item.evaluation.context_snapshot["close"] == 120.0


def test_evaluated_watchlist_prefers_live_price_for_price_rules(tmp_path, monkeypatch):
    config = _make_workspace(tmp_path)
    save_watchlist(
        config,
        WatchlistConfig(
            items=[
                WatchlistItem(
                    symbol="2330",
                    trigger_price=105,
                    invalidation_price=95,
                )
            ]
        ),
    )

    monkeypatch.setattr(
        "market_core.watchlist.engine.analyze_symbol",
        lambda *args, **kwargs: _analysis_snapshot(close=100, extra_values={"price_above_sma_20": False}),
    )
    monkeypatch.setattr(
        "market_core.watchlist.engine.get_market_session",
        lambda profile: {"is_open": True, "phase": "market_open", "reason": "test"},
    )
    monkeypatch.setattr(
        "market_core.watchlist.engine.get_quote",
        lambda *args, **kwargs: Quote(
            symbol="2330.TW",
            market_profile="tw_equity",
            price=110.0,
            source="test",
        ),
    )

    result = load_evaluated_watchlist(config, get_market_profile("tw_equity"))

    item = result.items[0]
    assert item.analysis is not None
    assert item.evaluation is not None
    assert item.evaluation.trigger_met is True
    assert item.evaluation.invalidation_met is False
    assert item.evaluation.context_snapshot["price"] == 110.0


@pytest.mark.skip(reason="live Fugle call; requires valid FUGLE_API_KEY")
def test_evaluated_watchlist_skips_items_without_machine_rules(tmp_path):
    config = _make_workspace(tmp_path)
    save_watchlist(
        config,
        WatchlistConfig(
            items=[
                WatchlistItem(
                    symbol="2330",
                    trigger="站回整理區上緣",
                    invalidation="跌破支撐",
                )
            ]
        ),
    )

    result = load_evaluated_watchlist(config, get_market_profile("tw_equity"))

    assert result.items[0].analysis is not None
    assert result.items[0].evaluation is None
