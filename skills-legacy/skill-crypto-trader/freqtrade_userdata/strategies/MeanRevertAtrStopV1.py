"""Mean Reversion ATR Stop V1

Statistical Mean Reversion (Liquidation Hunting) with dynamic ATR-based 
stop losses to prevent altcoin wicks from prematurely triggering exits.

Regime: any
Timeframe: 15m
"""
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
)
import talib.abstract as ta
from technical import qtpylib


class MeanRevertAtrStopV1(IStrategy):

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

    # Instead of static 7% stoploss, we use custom
    use_custom_stoploss = True
    stoploss = -0.99  # Let custom stoploss manage it

    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    # Use hyperopted values from Cycle 3 for major entry logic
    buy_bb_dev = DecimalParameter(2.5, 4.0, default=3.822, space="buy")
    buy_volume_spike = DecimalParameter(1.5, 3.0, default=2.746, space="buy")
    buy_rsi_max = IntParameter(15, 35, default=17, space="buy")

    # ATR multiplier for stoploss
    sl_atr_multiplier = 3.0

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Z-Score
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['std_50'] = ta.STDDEV(dataframe, timeperiod=50)
        dataframe['z_score'] = (dataframe['close'] - dataframe['sma_50']) / dataframe['std_50'].replace(0, 1e-9)

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        
        # ATR for dynamic stoploss
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe['z_score'] < -self.buy_bb_dev.value) &
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_spike.value)) &
            (dataframe['rsi'] < self.buy_rsi_max.value) &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[conditions, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            qtpylib.crossed_above(dataframe['close'], dataframe['sma_50']) |
            (dataframe['rsi'] > 70)
        )
        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        # Retrieve the analyzed dataframe
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return -0.15 # fallback 15% stoploss

        last_candle = dataframe.iloc[-1].squeeze()
        
        try:
            # We want an initial stoploss of 3 * ATR
            # For wide altcoin wicks, maybe it's -12% on high-beta and -5% on BTC
            atr_pct = last_candle['atr'] / trade.open_rate
            safe_sl = max(atr_pct * self.sl_atr_multiplier, 0.05)
            # Freqtrade expects relative stoploss value (e.g. -0.10)
            return -safe_sl
        except Exception:
            return -0.15
