"""Tests for current strategy candidate scanning."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yaml

from skill_crypto_trader.cli import main
from skill_crypto_trader.core.strategy_scanner import scan_registry_candidates


def _write_strategy(path: Path, class_name: str, entry_body: str, indicators_body: str = "return dataframe"):
    path.write_text(
        f"""from pandas import DataFrame
from freqtrade.strategy import IStrategy


class {class_name}(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    minimal_roi = {{"0": 0.1}}
    stoploss = -0.1

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        {indicators_body}

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        {entry_body}

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
"""
    )


def _write_market_data(path: Path, *, closes: list[float], start: datetime):
    rows = []
    current = start
    for idx, close in enumerate(closes):
        rows.append(
            {
                "date": current,
                "open": close - 1,
                "high": close + 1,
                "low": close - 2,
                "close": close,
                "volume": 100 + idx,
            }
        )
        current += timedelta(hours=1)
    pd.DataFrame(rows).to_feather(path)


def test_scan_registry_candidates_prefers_strategies_with_recent_signals(tmp_path):
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()
    data_root = tmp_path / "data" / "bybit"
    data_root.mkdir(parents=True)

    _write_strategy(
        strategy_dir / "EligibleTrend.py",
        "EligibleTrend",
        'dataframe.loc[dataframe["close"] > 110, "enter_long"] = 1\n        return dataframe',
    )
    _write_strategy(
        strategy_dir / "BlockedTrend.py",
        "BlockedTrend",
        'dataframe.loc[dataframe["close"] > 999, "enter_long"] = 1\n        return dataframe',
    )

    start = datetime(2026, 3, 28, 0, 0, tzinfo=timezone.utc)
    closes = [100, 101, 103, 108, 112, 114]
    _write_market_data(data_root / "BTC_USDT-1h.feather", closes=closes, start=start)

    registry_entries = [
        {
            "name": "EligibleTrend",
            "status": "candidate",
            "strategy_file": "EligibleTrend.py",
            "pairs": ["BTC/USDT"],
            "timeframe": "1h",
        },
        {
            "name": "BlockedTrend",
            "status": "candidate",
            "strategy_file": "BlockedTrend.py",
            "pairs": ["BTC/USDT"],
            "timeframe": "1h",
        },
    ]

    result = scan_registry_candidates(
        registry_entries=registry_entries,
        strategy_dir=strategy_dir,
        data_root=data_root,
        lookback_bars=4,
        now_utc=start + timedelta(hours=len(closes)),
    )

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["name"] == "EligibleTrend"
    assert result["candidates"][0]["total_recent_signals"] == 2
    assert result["blocked"][0]["name"] == "BlockedTrend"
    assert result["blocked"][0]["blocked_reasons"]["no_recent_signals"] == 1


def test_scan_registry_candidates_uses_regime_ok_when_strategy_exposes_it(tmp_path):
    strategy_dir = tmp_path / "strategies"
    strategy_dir.mkdir()
    data_root = tmp_path / "data" / "bybit"
    data_root.mkdir(parents=True)

    _write_strategy(
        strategy_dir / "RegimeOnly.py",
        "RegimeOnly",
        'dataframe.loc[dataframe["close"] > 500, "enter_long"] = 1\n        return dataframe',
        'dataframe["regime_ok"] = dataframe["close"] > 105\n        return dataframe',
    )

    start = datetime(2026, 3, 28, 0, 0, tzinfo=timezone.utc)
    closes = [100, 103, 106, 107, 108, 109]
    _write_market_data(data_root / "BTC_USDT-1h.feather", closes=closes, start=start)

    registry_entries = [
        {
            "name": "RegimeOnly",
            "status": "candidate",
            "strategy_file": "RegimeOnly.py",
            "pairs": ["BTC/USDT"],
            "timeframe": "1h",
        }
    ]

    result = scan_registry_candidates(
        registry_entries=registry_entries,
        strategy_dir=strategy_dir,
        data_root=data_root,
        lookback_bars=4,
        now_utc=start + timedelta(hours=len(closes)),
    )

    candidate = result["candidates"][0]
    assert candidate["name"] == "RegimeOnly"
    assert candidate["eligible"] is True
    assert candidate["total_recent_signals"] == 0
    assert candidate["pair_summaries"][0]["regime_pass_count"] == 4


def test_cli_portfolio_candidates_dispatch(monkeypatch, capsys):
    expected = {
        "candidate_count": 1,
        "candidates": [{"name": "MacdHistogramV1"}],
        "blocked": [],
        "skipped": [],
    }

    monkeypatch.setattr(
        "skill_crypto_trader.core.strategy_scanner.scan_registry_candidates",
        lambda lookback_bars, limit, statuses: {
            **expected,
            "lookback_bars": lookback_bars,
            "limit": limit,
            "statuses": sorted(statuses) if statuses else [],
        },
    )

    monkeypatch.setattr(
        "sys.argv",
        [
            "crypto-trader",
            "portfolio",
            "candidates",
            "--lookback-bars",
            "48",
            "--limit",
            "5",
            "--statuses",
            "candidate,active",
        ],
    )

    main()
    parsed = yaml.safe_load(capsys.readouterr().out)
    assert parsed["candidate_count"] == 1
    assert parsed["lookback_bars"] == 48
    assert parsed["limit"] == 5
    assert parsed["statuses"] == ["active", "candidate"]
