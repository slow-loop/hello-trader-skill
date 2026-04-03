"""KST Momentum V1

Know Sure Thing (KST): weighted sum of 4 smoothed ROC periods.
KST crosses above signal line = bullish momentum confirmation.
Price above EMA-50 for trend context.

Regime: trending
Timeframe: 4h
"""

import pandas_ta as pta
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib


class KstMomentumV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 100
    can_short: bool = False

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02, "1440": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    buy_rsi_min = IntParameter(40, 60, default=50, space="buy")
    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # KST from pandas_ta (standard parameters)
        kst = pta.kst(dataframe["close"])
        if kst is not None and not kst.empty:
            dataframe["kst"] = kst.iloc[:, 0]       # KST line
            dataframe["kst_signal"] = kst.iloc[:, 1]  # Signal line
        else:
            dataframe["kst"] = 0.0
            dataframe["kst_signal"] = 0.0

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # KST crosses above signal line
            qtpylib.crossed_above(dataframe["kst"], dataframe["kst_signal"])
            & (dataframe["kst"] > 0)  # KST positive = bullish momentum
            & (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "kst_cross_bullish"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            qtpylib.crossed_above(dataframe["kst_signal"], dataframe["kst"])
            | (dataframe["rsi"] > self.sell_rsi_max.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "kst_cross_bearish"
        return dataframe
