"""RSI Divergence V1

Bullish divergence: price makes lower low but RSI makes higher low.
Signals exhaustion of downtrend. Enter on divergence + price at BB lower.
Exit at BB mid or RSI overbought.

Regime: ranging / trend reversal
Timeframe: 4h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib


class RsiDivergenceV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {"0": 0.06, "120": 0.03, "360": 0.015, "720": 0.01}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_rsi_max = IntParameter(30, 50, default=40, space="buy")
    buy_lookback = IntParameter(5, 20, default=10, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]

        # Bullish divergence: price lower low, RSI higher low over lookback window
        lb = self.buy_lookback.value
        price_low_now = dataframe["low"]
        price_low_prev = dataframe["low"].shift(lb)
        rsi_now = dataframe["rsi"]
        rsi_prev = dataframe["rsi"].shift(lb)

        dataframe["bullish_div"] = (
            (price_low_now < price_low_prev)   # price: lower low
            & (rsi_now > rsi_prev)              # RSI: higher low
            & (rsi_now < self.buy_rsi_max.value)
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["bullish_div"] == 1)
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.01)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "rsi_bullish_divergence"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
            | (dataframe["close"] >= dataframe["bb_mid"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "rsi_div_exit"
        return dataframe
