"""Pivot Points V1

Classic pivot points: P = (H + L + C) / 3 from previous period.
Support/Resistance levels: S1, S2, R1, R2.
Buy when price bounces off S1/S2 with RSI oversold confirmation.
Exit at Pivot (P) or R1.

Uses daily pivot levels on hourly chart (informative pair pattern).

Regime: any (daily S/R levels)
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from freqtrade.strategy import merge_informative_pair


class PivotPointsV1(IStrategy):

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

    buy_rsi_max = IntParameter(25, 45, default=35, space="buy")
    buy_pivot_tolerance = DecimalParameter(0.002, 0.01, default=0.005, decimals=3, space="buy")
    sell_rsi_min = IntParameter(55, 75, default=65, space="sell")

    def informative_pairs(self):
        # Use daily candles for pivot calculation
        return []  # Handled via resampling in populate_indicators

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Compute daily pivot from rolling 24-hour window (24 x 1h candles)
        # Previous day's H, L, C
        dataframe["prev_high"] = dataframe["high"].rolling(24).max().shift(24)
        dataframe["prev_low"] = dataframe["low"].rolling(24).min().shift(24)
        dataframe["prev_close"] = dataframe["close"].shift(24)

        # Classic pivot formulas
        P = (dataframe["prev_high"] + dataframe["prev_low"] + dataframe["prev_close"]) / 3
        dataframe["pivot"] = P
        dataframe["s1"] = (2 * P) - dataframe["prev_high"]
        dataframe["s2"] = P - (dataframe["prev_high"] - dataframe["prev_low"])
        dataframe["r1"] = (2 * P) - dataframe["prev_low"]
        dataframe["r2"] = P + (dataframe["prev_high"] - dataframe["prev_low"])

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tol = self.buy_pivot_tolerance.value

        # Price bouncing off S1 or S2
        near_s1 = (
            (dataframe["low"] <= dataframe["s1"] * (1 + tol))
            & (dataframe["close"] > dataframe["s1"] * (1 - tol))
        )
        near_s2 = (
            (dataframe["low"] <= dataframe["s2"] * (1 + tol))
            & (dataframe["close"] > dataframe["s2"] * (1 - tol))
        )

        conditions = (
            (near_s1 | near_s2)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            # Bullish close (rejection of support)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "pivot_support_bounce"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Price reaches Pivot or R1
            (dataframe["close"] >= dataframe["pivot"])
            | (dataframe["rsi"] > self.sell_rsi_min.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "pivot_target_exit"
        return dataframe
