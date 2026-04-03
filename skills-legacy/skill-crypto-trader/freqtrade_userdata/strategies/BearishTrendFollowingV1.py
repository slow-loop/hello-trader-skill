"""Bearish Trend Following V1

Targeting short-term relief rallies in a structural bear market.
Regime: Bearish only (Price < 200 SMA Daily)
Strategy: Buy momentum breakouts on 15m timeframe.
"""
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
    merge_informative_pair
)
import talib.abstract as ta
from technical import qtpylib


class BearishTrendFollowingV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    startup_candle_count: int = 1500
    can_short: bool = False

    minimal_roi = {
        "0": 0.04,
        "60": 0.02,
        "120": 0.01,
        "240": 0
    }

    # Tighter stoploss for bear market
    stoploss = -0.04

    trailing_stop = True
    trailing_stop_positive = 0.005
    trailing_stop_positive_offset = 0.01
    trailing_only_offset_is_reached = True

    # Parameters
    buy_rsi_min = IntParameter(45, 55, default=50, space="buy")
    buy_volume_mult = DecimalParameter(1.1, 2.5, default=1.5, space="buy")
    
    def informative_pairs(self):
        return [
            ("BTC/USDT", "1d"),
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 15m Indicators
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # BTC Daily Macro Filter
        if self.dp:
            informative_1d = self.dp.get_pair_dataframe(pair="BTC/USDT", timeframe="1d")
            informative_1d['btc_sma_200'] = ta.SMA(informative_1d, timeperiod=200)
            dataframe = merge_informative_pair(dataframe, informative_1d, self.timeframe, "1d", ffill=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Core: Price > SMA 50 + RSI > 50 + Volume Spike
        # Filter: BTC < 200 SMA Daily (Active only in BEAR regimes)
        
        conditions = [
            (dataframe['close'] > dataframe['sma_50']),
            (dataframe['rsi'] > self.buy_rsi_min.value),
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_mult.value)),
            (dataframe['volume'] > 0),
        ]
        
        # Macro Bear filter
        macro_sma_col = 'BTC_USDT_btc_sma_200_1d'
        macro_close_col = 'BTC_USDT_close_1d'
        if macro_sma_col in dataframe.columns and macro_close_col in dataframe.columns:
            # ONLY trade if Price < 200 SMA (Bearish Regime)
            conditions.append(dataframe[macro_close_col] < dataframe[macro_sma_col])

        if conditions:
            dataframe.loc[pd.concat(conditions, axis=1).all(axis=1), 'enter_long'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            qtpylib.crossed_below(dataframe['close'], dataframe['sma_50']) |
            (dataframe['rsi'] > 75)
        )
        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe
