"""Mean Reversion BTC Filter V2

Implements Time-Based Bailout and tighter stop losses to combat the 
"Bull Market wide stoploss trap" identified in Cycle 8. 

Regime: any
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


class MeanRevertBtcFilterV2(IStrategy):

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

    # Tightened stoploss from -27% down to -8% to mitigate bear market death spirals
    stoploss = -0.08

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Use hyperopted values from V1 as baseline but we will re-evaluate
    buy_bb_dev = DecimalParameter(2.5, 4.0, default=3.388, space="buy")
    buy_volume_spike = DecimalParameter(1.5, 3.0, default=2.783, space="buy")
    buy_rsi_max = IntParameter(15, 35, default=15, space="buy")
    
    # Filter parameter: BTC crash confirmation
    buy_btc_z_score_max = DecimalParameter(-3.0, -1.0, default=-2.874, space="buy")

    # Time-based exit parameter
    exit_max_candles = IntParameter(4, 24, default=12, space="sell")

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

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs) -> str:
        
        # Time-based bailout: if the price hasn't mean-reverted within N candles, exit.
        # This prevents holding "falling knives" in a secular downward trend.
        if (current_time - trade.open_date_utc).total_seconds() > self.exit_max_candles.value * 15 * 60:
            return "time_exit"
            
        return None
