# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from typing import Dict, Any
from pandas import DataFrame

from freqtrade.strategy import IStrategy

class AgentExecutionStrategy(IStrategy):
    """
    AgentExecutionStrategy
    Dummy strategy for Freqtrade.
    This strategy does not enter or exit any trades automatically.
    It relies entirely on the Freqtrade API (forceenter / forceexit) to be driven by an external Agent.
    """

    INTERFACE_VERSION = 3

    # Strategy settings
    timeframe = '5m'
    
    # Process only minimal indicators to save CPU
    process_only_new_candles = True

    # Disable automatic ROI and stoploss. Agent is entirely responsible.
    minimal_roi = {"0": 100.0} # Needs 10000% gain to auto-close, essentially disabled
    stoploss = -1.0            # Drop by 100% to auto-stop, essentially disabled
    trailing_stop = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # No built-in indicators needed
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Never enter automatically
        dataframe['enter_long'] = 0
        dataframe['enter_short'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Never exit automatically
        dataframe['exit_long'] = 0
        dataframe['exit_short'] = 0
        return dataframe
