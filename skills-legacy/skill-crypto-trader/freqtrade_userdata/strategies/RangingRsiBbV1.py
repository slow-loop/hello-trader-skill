"""Ranging RSI Bollinger Bands V1

Mean-reversion strategy: buy at BB lower band with RSI oversold confirmation,
exit at BB middle band or RSI overbought. ADX filter ensures non-trending market.

Regime: ranging
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


class RangingRsiBbV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    # ROI: mean reversion takes profit quickly
    minimal_roi = {
        "0": 0.04,       # 4% immediate
        "60": 0.025,      # 2.5% after 1h
        "180": 0.015,     # 1.5% after 3h
        "360": 0.005,     # 0.5% after 6h
    }

    # Stoploss — tighter for mean reversion
    stoploss = -0.03  # -3%

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_rsi_max = IntParameter(20, 40, default=30, space="buy")
    buy_adx_max = IntParameter(20, 35, default=25, space="buy")
    buy_bb_factor = DecimalParameter(0.98, 1.02, default=1.0, decimals=3, space="buy")

    sell_rsi_min = IntParameter(55, 80, default=65, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ADX — to filter out trending markets
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # Bollinger Bands (20, 2)
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_middle"] = bollinger["mid"]
        dataframe["bb_upper"] = bollinger["upper"]
        dataframe["bb_width"] = (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]

        # Volume SMA
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # MFI — Money Flow Index as additional confirmation
        dataframe["mfi"] = ta.MFI(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Price at or below lower Bollinger Band
            (dataframe["close"] <= dataframe["bb_lower"] * self.buy_bb_factor.value)
            &
            # RSI oversold
            (dataframe["rsi"] < self.buy_rsi_max.value)
            &
            # ADX low = non-trending (ranging market)
            (dataframe["adx"] < self.buy_adx_max.value)
            &
            # Volume present
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "bb_lower_rsi_oversold"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Price reaches BB middle band (mean reversion target)
            (dataframe["close"] >= dataframe["bb_middle"])
            |
            # RSI overbought
            (dataframe["rsi"] > self.sell_rsi_min.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "bb_middle_or_rsi_ob"

        return dataframe
