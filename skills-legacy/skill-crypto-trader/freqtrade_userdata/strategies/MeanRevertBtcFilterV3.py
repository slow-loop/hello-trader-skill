"""Mean Reversion BTC Filter V3

Implements a Hard Macro-Regime Filter (Daily BTC 200 SMA) and 
Time-Based Bailout. 

Regime: Bull only (enforced by filter)
Timeframe: 15m
"""
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime, timedelta

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
    merge_informative_pair
)
from freqtrade.persistence import Trade
import talib.abstract as ta
from technical import qtpylib


class MeanRevertBtcFilterV3(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    startup_candle_count: int = 1500
    can_short: bool = False

    minimal_roi = {
        "0": 0.05,
        "30": 0.03,
        "120": 0.015,
        "240": 0.01
    }

    # Strict stoploss
    stoploss = -0.07

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Parameters
    buy_bb_dev = DecimalParameter(2.5, 4.0, default=3.388, space="buy")
    buy_volume_spike = DecimalParameter(1.5, 3.0, default=2.783, space="buy")
    buy_rsi_max = IntParameter(15, 35, default=15, space="buy")
    
    # Filter parameter: BTC crash confirmation (Intraday)
    buy_btc_z_score_max = DecimalParameter(-3.0, -1.0, default=-2.874, space="buy")

    # Time-based exit parameter
    exit_max_candles = IntParameter(4, 24, default=12, space="sell")

    def informative_pairs(self):
        return [
            ("BTC/USDT", self.timeframe),
            ("BTC/USDT", "1d"),
        ]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Own pair indicators
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['std_50'] = ta.STDDEV(dataframe, timeperiod=50)
        dataframe['z_score'] = (dataframe['close'] - dataframe['sma_50']) / dataframe['std_50'].replace(0, 1e-9)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # BTC Informative
        if self.dp:
            # 15m BTC (Intraday confirmation)
            informative_15m = self.dp.get_pair_dataframe(pair="BTC/USDT", timeframe=self.timeframe)
            informative_15m['btc_z_score'] = (informative_15m['close'] - ta.SMA(informative_15m, 50)) / ta.STDDEV(informative_15m, 50).replace(0, 1e-9)
            dataframe = merge_informative_pair(dataframe, informative_15m, self.timeframe, self.timeframe, ffill=True)

            # Daily BTC (Macro filter)
            informative_1d = self.dp.get_pair_dataframe(pair="BTC/USDT", timeframe="1d")
            informative_1d['btc_sma_200'] = ta.SMA(informative_1d, timeperiod=200)
            dataframe = merge_informative_pair(dataframe, informative_1d, self.timeframe, "1d", ffill=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = [
            (dataframe['z_score'] < -self.buy_bb_dev.value),
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_spike.value)),
            (dataframe['rsi'] < self.buy_rsi_max.value),
            (dataframe['volume'] > 0)
        ]
        
        # NOTE: If we are trading e.g. ETH/USDT, the BTC columns will be prefixed with 'BTC_USDT_'
        # Suffixes are also added for timeframes != self.timeframe
        
        # Intraday BTC confirmation (Self or BTC prefix)
        btc_z_col = 'BTC_USDT_btc_z_score'
        if btc_z_col in dataframe.columns:
            conditions.append(dataframe[btc_z_col] < self.buy_btc_z_score_max.value)
        elif 'btc_z_score' in dataframe.columns:
            conditions.append(dataframe['btc_z_score'] < self.buy_btc_z_score_max.value)

        # Macro Bull filter (BTC_USDT + _1d)
        macro_sma_col = 'BTC_USDT_btc_sma_200_1d'
        macro_close_col = 'BTC_USDT_close_1d'
        if macro_sma_col in dataframe.columns and macro_close_col in dataframe.columns:
            conditions.append(dataframe[macro_close_col] > dataframe[macro_sma_col])

        if conditions:
            dataframe.loc[pd.concat(conditions, axis=1).all(axis=1), 'enter_long'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            qtpylib.crossed_above(dataframe['close'], dataframe['sma_50']) |
            (dataframe['rsi'] > 70)
        )
        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str:
        
        # Time-based bailout
        if (current_time - trade.open_date_utc).total_seconds() > self.exit_max_candles.value * 15 * 60:
            return "time_exit"
            
        return None
