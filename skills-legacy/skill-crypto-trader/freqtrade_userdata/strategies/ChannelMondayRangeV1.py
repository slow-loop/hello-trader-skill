"""Channel Monday Range V1

Range-reversion strategy:
- only trade when market is choppy / non-trending
- use Monday's range as a weekly anchor
- buy near Monday low or rolling channel low
- exit quickly back to the middle of the range

Regime: ranging
Timeframe: 1h
"""

from __future__ import annotations

import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
import talib.abstract as ta


class ChannelMondayRangeV1(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 96
    can_short: bool = False

    minimal_roi = {
        "0": 0.025,
        "180": 0.015,
        "360": 0.008,
    }
    stoploss = -0.025
    trailing_stop = False

    buy_adx_max = IntParameter(18, 30, default=25, space="buy")
    buy_rsi_max = IntParameter(28, 45, default=40, space="buy")
    buy_support_tolerance = DecimalParameter(0.002, 0.015, default=0.008, decimals=3, space="buy")
    buy_channel_period = IntParameter(24, 96, default=48, space="buy")
    sell_rsi_min = IntParameter(55, 70, default=60, space="sell")

    @staticmethod
    def _add_monday_range(dataframe: DataFrame) -> DataFrame:
        df = dataframe.copy()
        dt = pd.DatetimeIndex(df.index)
        week = dt.to_period("W-SUN")
        monday_mask = dt.dayofweek == 0

        monday_high = df["high"].where(monday_mask).groupby(week).cummax()
        monday_low = df["low"].where(monday_mask).groupby(week).cummin()

        df["monday_high"] = monday_high.groupby(week).ffill()
        df["monday_low"] = monday_low.groupby(week).ffill()
        df["monday_mid"] = (df["monday_high"] + df["monday_low"]) / 2.0
        return df

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self._add_monday_range(dataframe)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)

        period = int(self.buy_channel_period.value)
        dataframe["channel_high"] = dataframe["high"].rolling(period).max()
        dataframe["channel_low"] = dataframe["low"].rolling(period).min()
        dataframe["channel_mid"] = (dataframe["channel_high"] + dataframe["channel_low"]) / 2.0
        dataframe["channel_width_pct"] = (
            (dataframe["channel_high"] - dataframe["channel_low"]) / dataframe["close"]
        ).fillna(0.0)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tol = self.buy_support_tolerance.value

        near_monday_low = dataframe["close"] <= dataframe["monday_low"] * (1 + tol)
        near_channel_low = dataframe["close"] <= dataframe["channel_low"] * (1 + tol)

        conditions = (
            (dataframe["adx"] < self.buy_adx_max.value)
            & (dataframe["channel_width_pct"] > 0.01)
            & (dataframe["channel_width_pct"] < 0.12)
            & (near_monday_low | near_channel_low)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "channel_monday_revert"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close"] >= dataframe["channel_mid"])
            | (dataframe["close"] >= dataframe["monday_mid"])
            | (dataframe["rsi"] > self.sell_rsi_min.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "range_mid_exit"
        return dataframe
