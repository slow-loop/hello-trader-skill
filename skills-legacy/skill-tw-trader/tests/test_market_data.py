from __future__ import annotations

import os
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from skill_tw_trader.core.market_data.market import get_bars, get_chips, get_quote
from skill_tw_trader.core.market_data.models import Bar, ChipsDaily, Quote
from skill_tw_trader.core.market_data.symbols import (
    detect_market,
    is_tw_equity_symbol,
    normalize_symbol,
    strip_suffix,
    symbol_key,
)
from skill_tw_trader.core.market_data.storage import MARKET_DIR, bars_path, chips_path, load_bars, save_bars, load_chips, save_chips


def test_normalize_symbol():
    assert normalize_symbol("2317") == "2317.TW"
    assert normalize_symbol("2317.TW") == "2317.TW"
    assert normalize_symbol("2330.TWO") == "2330.TWO"
    assert normalize_symbol("AAPL") == "AAPL"
    assert normalize_symbol("^TWII") == "^TWII"
    with pytest.raises(ValueError):
        normalize_symbol("")


def test_detect_market():
    assert detect_market("2317") == "tw"
    assert detect_market("2317.TW") == "tw"
    assert detect_market("2330.TWO") == "tw"
    assert detect_market("AAPL") == "us"
    assert detect_market("^TWII") == "tw"


def test_strip_suffix():
    assert strip_suffix("2317.TW") == "2317"
    assert strip_suffix("2330.TWO") == "2330"
    assert strip_suffix("AAPL") == "AAPL"


def test_symbol_key():
    assert symbol_key("2317.TW") == "2317.tw"
    assert symbol_key("^TWII") == "twii"
    assert symbol_key("BRK-B") == "brk-b"


def test_is_tw_equity_symbol():
    assert is_tw_equity_symbol("2317.TW") is True
    assert is_tw_equity_symbol("2330.TWO") is True
    assert is_tw_equity_symbol("AAPL") is False
    assert is_tw_equity_symbol("^TWII") is False


class TestStorage:
    @pytest.fixture(autouse=True)
    def setup_tmp_data(self, tmp_path):
        with patch("skill_tw_trader.core.market_data.storage.MARKET_DIR", tmp_path):
            yield

    def test_bars_path(self, tmp_path):
        path = bars_path("2317.TW")
        assert "bars/tw/1d/2317.tw_1d.parquet" in str(path)

    def test_save_load_bars(self, tmp_path):
        symbol = "2317.TW"
        bars = [
            Bar(
                symbol=symbol,
                market="tw",
                timeframe="1d",
                bar_time=datetime(2024, 1, 1),
                open=100.0,
                high=105.0,
                low=99.0,
                close=103.0,
                volume=1000,
                source="test",
            ),
            Bar(
                symbol=symbol,
                market="tw",
                timeframe="1d",
                bar_time=datetime(2024, 1, 2),
                open=103.0,
                high=110.0,
                low=102.0,
                close=108.0,
                volume=1200,
                source="test",
            ),
        ]
        
        save_bars(symbol, bars)
        loaded = load_bars(symbol)
        
        assert len(loaded) == 2
        assert loaded[0].close == 103.0
        assert loaded[1].bar_time == datetime(2024, 1, 2)

    def test_save_bars_merging(self, tmp_path):
        symbol = "2317.TW"
        bar1 = Bar(
            symbol=symbol, market="tw", bar_time=datetime(2024, 1, 1),
            open=100, high=105, low=99, close=103, source="test"
        )
        bar2 = Bar(
            symbol=symbol, market="tw", bar_time=datetime(2024, 1, 2),
            open=103, high=110, low=102, close=108, source="test"
        )
        
        save_bars(symbol, [bar1])
        save_bars(symbol, [bar2])
        
        loaded = load_bars(symbol)
        assert len(loaded) == 2
        assert loaded[0].bar_time == datetime(2024, 1, 1)
        assert loaded[1].bar_time == datetime(2024, 1, 2)


    def test_save_load_chips(self, tmp_path):
        symbol = "2317.TW"
        rows = [
            ChipsDaily(
                symbol=symbol,
                trade_date=date(2024, 1, 1),
                source="test",
                foreign_net=1000,
                trust_net=500,
            ),
            ChipsDaily(
                symbol=symbol,
                trade_date=date(2024, 1, 2),
                source="test",
                foreign_net=-200,
                trust_net=100,
            ),
        ]
        
        save_chips(symbol, rows)
        loaded = load_chips(symbol)
        
        assert len(loaded) == 2
        assert loaded[0].foreign_net == 1000
        assert loaded[1].trade_date == date(2024, 1, 2)


class TestMarketLogic:
    @patch("skill_tw_trader.core.market_data.market.fetch_fugle_quote")
    @patch("skill_tw_trader.core.market_data.market.fetch_yfinance_quote")
    def test_get_quote_routing(self, mock_yf, mock_fugle):
        mock_fugle.return_value = Quote(symbol="2317.TW", market="tw", price=100, source="fugle")
        mock_yf.return_value = Quote(symbol="AAPL", market="us", price=150, source="yf")
        
        q1 = get_quote("2317.TW")
        assert q1.source == "fugle"
        mock_fugle.assert_called_once()
        
        q2 = get_quote("AAPL")
        assert q2.source == "yf"
        mock_yf.assert_called_once()

    @patch("skill_tw_trader.core.market_data.market.get_last_trading_day")
    @patch("skill_tw_trader.core.market_data.market.load_bars")
    @patch("skill_tw_trader.core.market_data.market.refresh_bars")
    def test_get_bars_cache(self, mock_refresh, mock_load, mock_ltd):
        test_bar_time = datetime(2024, 1, 1)
        mock_ltd.return_value = test_bar_time.date()
        test_bar = Bar(
            symbol="2317.TW", market="tw", bar_time=test_bar_time,
            open=100, high=105, low=99, close=103, source="test"
        )
        start_date = test_bar_time - timedelta(days=1)
        
        # Case 1: Local data exists
        mock_load.return_value = [test_bar]
        bars = get_bars("2317.TW", start=start_date, refresh=False)
        assert len(bars) == 1
        mock_refresh.assert_not_called()
        
        # Case 2: Local data missing
        mock_load.return_value = []
        mock_refresh.return_value = [test_bar]
        bars = get_bars("2317.TW", start=start_date, refresh=False)
        assert len(bars) == 1
        mock_refresh.assert_called_once()
        
        # Case 3: Force refresh
        mock_refresh.reset_mock()
        get_bars("2317.TW", start=start_date, refresh=True)
        mock_refresh.assert_called_once()

    @patch("skill_tw_trader.core.market_data.market.get_last_trading_day")
    @patch("skill_tw_trader.core.market_data.market.load_chips")
    @patch("skill_tw_trader.core.market_data.market.refresh_chips")
    def test_get_chips_cache(self, mock_refresh, mock_load, mock_ltd):
        test_date = date(2024, 1, 1)
        mock_ltd.return_value = test_date
        test_row = ChipsDaily(symbol="2317.TW", trade_date=test_date, source="test")
        start_date = test_date - timedelta(days=1)

        # Case 1: Local data exists
        mock_load.return_value = [test_row]
        rows = get_chips("2317.TW", start=start_date, refresh=False)
        assert len(rows) == 1
        mock_refresh.assert_not_called()

        # Case 2: Local data missing
        mock_load.return_value = []
        mock_refresh.return_value = [test_row]
        rows = get_chips("2317.TW", start=start_date, refresh=False)
        assert len(rows) == 1
        mock_refresh.assert_called_once()
