"""Choppiness RSI V1

Choppiness Index as regime gate: only enter mean-reversion trades when CI > 61.8
(ranging market). RSI oversold + BB lower band as entry signal.

CI formula: 100 * log10(ATR_sum_N / (High_N - Low_N)) / log10(N)
CI > 61.8 = choppy/ranging; CI < 38.2 = trending

Regime: ranging
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class ChoppinessRsiV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {
        "0": 0.04,
        "60": 0.025,
        "180": 0.015,
        "360": 0.005,
    }

    stoploss = -0.03

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_ci_min = DecimalParameter(50.0, 70.0, default=61.8, decimals=1, space="buy")  # CI above = ranging
    buy_rsi_max = IntParameter(25, 40, default=32, space="buy")
    buy_ci_period = IntParameter(10, 20, default=14, space="buy")

    sell_rsi_min = IntParameter(55, 75, default=65, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ATR (True Range)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=1)  # single-period TR

        # Choppiness Index for multiple periods
        for period in range(10, 21):
            atr_sum = ta.SMA(dataframe["atr"], timeperiod=period) * period  # sum of TR over N periods
            high_n = ta.MAX(dataframe["high"], timeperiod=period)
            low_n = ta.MIN(dataframe["low"], timeperiod=period)
            hl_range = high_n - low_n
            # Avoid division by zero
            dataframe[f"chop_{period}"] = np.where(
                hl_range > 0,
                100 * np.log10(atr_sum / hl_range) / np.log10(period),
                50.0
            )

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger Bands
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chop_col = f"chop_{self.buy_ci_period.value}"

        conditions = (
            # Choppiness confirms ranging market
            (dataframe[chop_col] > self.buy_ci_min.value)
            &
            # RSI oversold
            (dataframe["rsi"] < self.buy_rsi_max.value)
            &
            # Price at lower BB
            (dataframe["close"] <= dataframe["bb_lower"])
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "chop_rsi_oversold"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close"] >= dataframe["bb_mid"])
            |
            (dataframe["rsi"] > self.sell_rsi_min.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "chop_exit"

        return dataframe
