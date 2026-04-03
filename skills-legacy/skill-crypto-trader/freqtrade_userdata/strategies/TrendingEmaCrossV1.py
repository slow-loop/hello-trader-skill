"""Trending EMA Cross V1

Trend-following strategy using EMA 9/21 crossover with ADX trend strength filter
and RSI momentum confirmation. Trailing stop for risk management.

Regime: trending_up, trending_down (spot = long only, so best in trending_up)
Timeframe: 1h
"""

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
)
import talib.abstract as ta
from technical import qtpylib


class TrendingEmaCrossV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    # ROI: take profit at these thresholds
    minimal_roi = {
        "0": 0.08,       # 8% immediate
        "120": 0.04,      # 4% after 2h
        "360": 0.02,      # 2% after 6h
        "720": 0.01,      # 1% after 12h
    }

    # Stoploss (mandatory)
    stoploss = -0.05  # -5%

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.02       # Lock in 2% profit
    trailing_stop_positive_offset = 0.04  # Activate after 4% gain
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_ema_short = IntParameter(5, 15, default=9, space="buy")
    buy_ema_long = IntParameter(15, 30, default=21, space="buy")
    buy_adx_min = IntParameter(15, 35, default=25, space="buy")
    buy_rsi_min = IntParameter(30, 55, default=40, space="buy")
    buy_rsi_max = IntParameter(65, 80, default=70, space="buy")

    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA (compute all in hyperopt range)
        for period in range(5, 31):
            dataframe[f"ema_{period}"] = ta.EMA(dataframe, timeperiod=period)

        # ADX — trend strength
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # RSI — momentum
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ATR — volatility reference
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Volume SMA — for volume confirmation
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_short = f"ema_{self.buy_ema_short.value}"
        ema_long = f"ema_{self.buy_ema_long.value}"

        conditions = (
            # EMA golden cross: short EMA crosses above long EMA
            qtpylib.crossed_above(dataframe[ema_short], dataframe[ema_long])
            &
            # ADX confirms trend strength
            (dataframe["adx"] > self.buy_adx_min.value)
            &
            # RSI in momentum zone (not overbought, not oversold)
            (dataframe["rsi"] > self.buy_rsi_min.value)
            &
            (dataframe["rsi"] < self.buy_rsi_max.value)
            &
            # Volume above average (confirmation)
            (dataframe["volume"] > dataframe["volume_sma_20"])
            &
            # Basic volume filter
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "ema_cross_up"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_short = f"ema_{self.buy_ema_short.value}"
        ema_long = f"ema_{self.buy_ema_long.value}"

        conditions = (
            # EMA death cross: long EMA crosses above short EMA
            qtpylib.crossed_above(dataframe[ema_long], dataframe[ema_short])
            |
            # RSI overbought exit
            (dataframe["rsi"] > self.sell_rsi_max.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "ema_cross_down_or_rsi_ob"

        return dataframe
