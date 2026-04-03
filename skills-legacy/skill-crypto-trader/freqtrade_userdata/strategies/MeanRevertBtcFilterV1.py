"""Mean Reversion BTC Filter V1

Statistical Mean Reversion strategy that uses BTC/USDT as an overarching 
market proxy. Altcoin entries are only allowed if BTC itself is also 
exhibiting a severe z-score drop (systemic capitulation).

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
    merge_informative_pair
)
import talib.abstract as ta
from technical import qtpylib


class MeanRevertBtcFilterV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    startup_candle_count: int = 200
    can_short: bool = False

    minimal_roi = {
        "0": 0.05,
        "30": 0.03,
        "120": 0.015,
        "240": 0.01
    }

    # Use standard stoploss here, expecting BTC filter to prevent catching falling knives
    stoploss = -0.07

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Use hyperopted values from Cycle 3 for base entry
    buy_bb_dev = DecimalParameter(2.5, 4.0, default=3.822, space="buy")
    buy_volume_spike = DecimalParameter(1.5, 3.0, default=2.746, space="buy")
    buy_rsi_max = IntParameter(15, 35, default=17, space="buy")
    
    # Filter parameter: How deep must BTC crash to allow altcoin entries?
    buy_btc_z_score_max = DecimalParameter(-3.0, -1.0, default=-2.0, space="buy")

    def informative_pairs(self):
        return [("BTC/USDT", self.timeframe)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Own pair indicators
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['std_50'] = ta.STDDEV(dataframe, timeperiod=50)
        dataframe['z_score'] = (dataframe['close'] - dataframe['sma_50']) / dataframe['std_50'].replace(0, 1e-9)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # BTC Informative
        if self.dp:
            inf_tf = self.timeframe
            informative = self.dp.get_pair_dataframe(pair="BTC/USDT", timeframe=inf_tf)
            informative['btc_sma_50'] = ta.SMA(informative, timeperiod=50)
            informative['btc_std_50'] = ta.STDDEV(informative, timeperiod=50)
            informative['btc_z_score'] = (informative['close'] - informative['btc_sma_50']) / informative['btc_std_50'].replace(0, 1e-9)
            
            dataframe = merge_informative_pair(dataframe, informative, self.timeframe, inf_tf, ffill=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        btc_z_col = f"btc_z_score_{self.timeframe}"
        
        conditions = [
            (dataframe['z_score'] < -self.buy_bb_dev.value),
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_spike.value)),
            (dataframe['rsi'] < self.buy_rsi_max.value),
            (dataframe['volume'] > 0)
        ]
        
        # Ensure we have informative BTC data merged before checking
        if btc_z_col in dataframe.columns:
            conditions.append(dataframe[btc_z_col] < self.buy_btc_z_score_max.value)

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
