"""MACD Histogram V1

MACD histogram turns from negative to positive (first positive bar after negative series).
More sensitive than crossover — catches momentum shifts earlier.
Price above EMA-50 for trend context.

Regime: trending
Timeframe: 1h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class MacdHistogramV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {"0": 0.06, "120": 0.03, "360": 0.015, "720": 0.008}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_hist_min = DecimalParameter(0.0, 50.0, default=0.0, decimals=1, space="buy")
    buy_rsi_min = IntParameter(35, 55, default=45, space="buy")
    buy_rsi_max = IntParameter(55, 70, default=65, space="buy")
    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd_hist"] = macd["macdhist"]
        dataframe["macd"] = macd["macd"]
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Histogram turns positive (crosses above 0 from below)
            qtpylib.crossed_above(dataframe["macd_hist"], self.buy_hist_min.value)
            # Was negative before (actual reversal, not just continuation)
            & (dataframe["macd_hist"].shift(1) < 0)
            & (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "macd_hist_flip_positive"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["macd_hist"] < 0)
            | (dataframe["rsi"] > self.sell_rsi_max.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "macd_hist_negative"
        return dataframe
