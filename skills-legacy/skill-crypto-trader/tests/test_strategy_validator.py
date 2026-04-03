"""Tests for strategy code validation."""

import tempfile
from pathlib import Path

from skill_crypto_trader.core.strategy_validator import validate_syntax


def test_valid_strategy():
    code = '''
from freqtrade.strategy import IStrategy
from pandas import DataFrame

class TestStrategy(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    stoploss = -0.05
    minimal_roi = {"0": 0.1}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe
'''
    tmp = Path(tempfile.mktemp(suffix=".py"))
    tmp.write_text(code)
    errors = validate_syntax(tmp)
    assert errors == []
    tmp.unlink()


def test_missing_istrategy():
    code = '''
class NotAStrategy:
    stoploss = -0.05
    pass
'''
    tmp = Path(tempfile.mktemp(suffix=".py"))
    tmp.write_text(code)
    errors = validate_syntax(tmp)
    assert any("IStrategy" in e for e in errors)
    tmp.unlink()


def test_missing_stoploss():
    code = '''
from freqtrade.strategy import IStrategy
class BadStrategy(IStrategy):
    pass
'''
    tmp = Path(tempfile.mktemp(suffix=".py"))
    tmp.write_text(code)
    errors = validate_syntax(tmp)
    assert any("stoploss" in e for e in errors)
    tmp.unlink()


def test_syntax_error():
    code = '''
def broken(
'''
    tmp = Path(tempfile.mktemp(suffix=".py"))
    tmp.write_text(code)
    errors = validate_syntax(tmp)
    assert len(errors) > 0
    tmp.unlink()
