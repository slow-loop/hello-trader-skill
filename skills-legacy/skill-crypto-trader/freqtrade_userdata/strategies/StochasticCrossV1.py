"""Stochastic Cross V1

Stochastic %K crosses above %D in oversold zone (<20). BB lower band confirms
price is at support. Only trade when ADX is low (ranging market).

Regime: ranging
Timeframe: 1h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib


class StochasticCrossV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 30
    can_short: bool = False

    minimal_roi = {"0": 0.04, "60": 0.02, "180": 0.01, "360": 0.005}
    stoploss = -0.03
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    buy_stoch_max = IntParameter(15, 30, default=20, space="buy")
    buy_adx_max = IntParameter(20, 35, default=25, space="buy")
    sell_stoch_min = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        stoch = ta.STOCH(dataframe, fastk_period=14, slowk_period=3, slowd_period=3)
        dataframe["slowk"] = stoch["slowk"]
        dataframe["slowd"] = stoch["slowd"]

        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # %K crosses above %D in oversold zone
            qtpylib.crossed_above(dataframe["slowk"], dataframe["slowd"])
            & (dataframe["slowk"] < self.buy_stoch_max.value)
            # Ranging market
            & (dataframe["adx"] < self.buy_adx_max.value)
            # Price at BB lower
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.005)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "stoch_cross_oversold"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            qtpylib.crossed_above(dataframe["slowd"], dataframe["slowk"])
            & (dataframe["slowk"] > self.sell_stoch_min.value)
        ) | (dataframe["close"] >= dataframe["bb_mid"])
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "stoch_cross_overbought"
        return dataframe
