"""Any MACD RSI V1

Trend-following / Momentum strategy utilizing MACD crossovers
filtered by long-term EMA and RSI. Designed for 15m timeframe to capture
more frequent trades.

Regime: any
Timeframe: 15m
"""

import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
    CategoricalParameter,
)
import talib.abstract as ta
from technical import qtpylib


class AnyMacdRsiV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    startup_candle_count: int = 200
    can_short: bool = False

    # ROI thresholds (let's keep them reasonable for 15m)
    minimal_roi = {
        "0": 0.05,       # 5% immediate
        "60": 0.03,      # 3% after 1h (4 candles)
        "180": 0.02,     # 2% after 3h (12 candles)
        "360": 0.01,     # 1% after 6h
    }

    # Stoploss
    stoploss = -0.05

    # Trailing stop
    trailing_stop = True
    trailing_stop_positive = 0.015       # Lock in 1.5% profit
    trailing_stop_positive_offset = 0.03  # Activate after 3% gain
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_rsi_min = IntParameter(40, 60, default=50, space="buy")
    buy_ema_period = CategoricalParameter([100, 150, 200, 250, 300], default=200, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # EMAs
        for period in [100, 150, 200, 250, 300]:
            dataframe[f'ema_{period}'] = ta.EMA(dataframe, timeperiod=period)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_col = f"ema_{self.buy_ema_period.value}"

        conditions = (
            qtpylib.crossed_above(dataframe['macd'], dataframe['macdsignal'])
            &
            (dataframe['close'] > dataframe[ema_col])
            &
            (dataframe['rsi'] > self.buy_rsi_min.value)
            &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[conditions, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            qtpylib.crossed_below(dataframe['macd'], dataframe['macdsignal'])
        )

        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe
