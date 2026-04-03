"""Support Resistance Breakout V1

Resistance = highest high over last N candles (rolling pivot).
Enter when price closes above resistance with volume surge.
Stoploss below the broken resistance (now support).

Regime: trending
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class SupportResistanceBreakV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.025, "2880": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    buy_lookback = IntParameter(10, 30, default=20, space="buy")
    buy_vol_factor = DecimalParameter(1.2, 2.5, default=1.5, decimals=1, space="buy")
    buy_rsi_min = IntParameter(45, 65, default=55, space="buy")
    sell_rsi_max = IntParameter(70, 85, default=78, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in range(10, 31):
            # Resistance = previous N-period high (shift(1) avoids lookahead)
            dataframe[f"resistance_{period}"] = dataframe["high"].rolling(period).max().shift(1)
            dataframe[f"support_{period}"] = dataframe["low"].rolling(period).min().shift(1)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        lb = self.buy_lookback.value
        resistance = f"resistance_{lb}"

        conditions = (
            # Close breaks above resistance
            qtpylib.crossed_above(dataframe["close"], dataframe[resistance])
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"] * self.buy_vol_factor.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "sr_breakout"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        lb = self.buy_lookback.value
        support = f"support_{lb}"

        conditions = (
            (dataframe["close"] < dataframe[support])
            | (dataframe["rsi"] > self.sell_rsi_max.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "sr_breakdown"
        return dataframe
