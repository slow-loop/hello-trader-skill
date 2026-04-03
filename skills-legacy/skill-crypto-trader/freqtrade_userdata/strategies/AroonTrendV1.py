"""Aroon Trend V1

Aroon Up > 70 and Aroon Down < 30 signals a new uptrend beginning.
Aroon oscillator (Up - Down) crossing above 0 is the primary signal.
Volume confirms trend.

Regime: trending (trend initiation)
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib


class AroonTrendV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 30
    can_short: bool = False

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.02, "2880": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    buy_aroon_up_min = IntParameter(60, 85, default=70, space="buy")
    buy_aroon_down_max = IntParameter(15, 40, default=30, space="buy")
    buy_vol_factor = IntParameter(1, 2, default=1, space="buy")
    sell_aroon_down_min = IntParameter(50, 80, default=70, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        aroon = ta.AROON(dataframe, timeperiod=14)
        dataframe["aroon_up"] = aroon["aroonup"]
        dataframe["aroon_down"] = aroon["aroondown"]
        dataframe["aroon_osc"] = ta.AROONOSC(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Aroon Up strong, Aroon Down weak = new uptrend
            (dataframe["aroon_up"] > self.buy_aroon_up_min.value)
            & (dataframe["aroon_down"] < self.buy_aroon_down_max.value)
            # Oscillator crosses above 0 (uptrend confirmed)
            & qtpylib.crossed_above(dataframe["aroon_osc"], 0)
            # Price above EMA50
            & (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["volume"] >= dataframe["volume_sma_20"] * self.buy_vol_factor.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "aroon_uptrend"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["aroon_down"] > self.sell_aroon_down_min.value)
            | (dataframe["close"] < dataframe["ema_50"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "aroon_trend_exit"
        return dataframe
