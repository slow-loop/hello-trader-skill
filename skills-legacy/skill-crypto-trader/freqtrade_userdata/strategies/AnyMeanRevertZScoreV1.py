"""Any Mean Reversion Z-Score V1

A statistical, high win-rate strategy focusing on liquidation wick hunting.
It hunts for extreme deviations from the mean (3+ standard deviations) 
accompanied by volume spikes indicating panic selling.

Regime: any (though best in ranging or bull-market dips)
Timeframe: 15m
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


class AnyMeanRevertZScoreV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    startup_candle_count: int = 200
    can_short: bool = False

    # High win-rate strategies need decent ROI
    minimal_roi = {
        "0": 0.05,        # 5% target if pump is huge
        "30": 0.03,       # 3% after 30 mins
        "120": 0.015,     # 1.5% after 2h
        "240": 0.01       # 1% after 4h
    }

    # Stoploss: somewhat wide to catch falling knives safely
    stoploss = -0.07  # -7%

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Hyperoptable parameters
    buy_bb_dev = DecimalParameter(2.5, 4.0, default=3.0, space="buy")
    buy_volume_spike = DecimalParameter(1.5, 3.0, default=2.0, space="buy")
    buy_rsi_max = IntParameter(15, 35, default=25, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Z-Score proxy
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['std_50'] = ta.STDDEV(dataframe, timeperiod=50)
        
        # Avoid division by zero
        dataframe['z_score'] = (dataframe['close'] - dataframe['sma_50']) / dataframe['std_50'].replace(0, 1e-9)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        dataframe['ema_200'] = ta.EMA(dataframe, timeperiod=200)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Extreme Z-score drop (-3.0 means 3 std devs below mean)
            (dataframe['z_score'] < -self.buy_bb_dev.value)
            &
            # Volume spike indicating capitulation/panic
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_spike.value))
            &
            # Extremely oversold
            (dataframe['rsi'] < self.buy_rsi_max.value)
            &
            # Filter: Do not buy if entirely under the 200 EMA (secular bearish trend)
            # Actually, let's allow it but wait for volume confirmation! The volume spike is the confirmation.
            (dataframe['volume'] > 0)
        )

        dataframe.loc[conditions, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Mean reversion achieved
            qtpylib.crossed_above(dataframe['close'], dataframe['sma_50'])
            |
            # Momentum locally exhausted
            (dataframe['rsi'] > 70)
        )

        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe
