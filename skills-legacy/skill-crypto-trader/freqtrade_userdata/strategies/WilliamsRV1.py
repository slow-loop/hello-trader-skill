"""Williams %R V1

Williams %R < -80 (oversold) with price bouncing off BB lower band.
Exit when %R crosses above -20 (overbought) or price reaches BB mid.

Regime: ranging
Timeframe: 1h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib


class WilliamsRV1(IStrategy):

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

    buy_willr_max = IntParameter(-90, -70, default=-80, space="buy")
    buy_adx_max = IntParameter(20, 35, default=25, space="buy")
    sell_willr_min = IntParameter(-30, -10, default=-20, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["willr"] = ta.WILLR(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["willr"] < self.buy_willr_max.value)
            & (dataframe["adx"] < self.buy_adx_max.value)
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.005)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "willr_oversold"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["willr"] > self.sell_willr_min.value)
            | (dataframe["close"] >= dataframe["bb_mid"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "willr_overbought"
        return dataframe
