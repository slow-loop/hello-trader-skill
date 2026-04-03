"""Grid Range V1

Grid trading adapted for Freqtrade: define a price range, divide into N levels.
Buy when price drops to next grid level. Exit at next grid level above.
Choppiness Index confirms ranging market before entering.

Note: Freqtrade runs one position per pair; this simulates grid by re-entering
after each exit at the next lower grid level.

Regime: ranging
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta


class GridRangeV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    # Grid profit per level
    minimal_roi = {"0": 0.02, "120": 0.01, "360": 0.005}
    stoploss = -0.08  # Wide stop — grid needs room

    trailing_stop = False  # Fixed grid exits

    # Hyperopt parameters
    buy_grid_levels = IntParameter(5, 20, default=10, space="buy")
    buy_grid_range_pct = DecimalParameter(0.05, 0.20, default=0.10, decimals=2, space="buy")
    buy_chop_min = DecimalParameter(45.0, 65.0, default=55.0, decimals=1, space="buy")
    buy_chop_period = IntParameter(10, 20, default=14, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Choppiness Index
        atr_1 = ta.ATR(dataframe, timeperiod=1)
        for period in range(10, 21):
            atr_sum = ta.SMA(atr_1, timeperiod=period) * period
            high_n = ta.MAX(dataframe["high"], timeperiod=period)
            low_n = ta.MIN(dataframe["low"], timeperiod=period)
            hl_range = high_n - low_n
            dataframe[f"chop_{period}"] = np.where(
                hl_range > 0,
                100 * np.log10(atr_sum / hl_range) / np.log10(period),
                50.0
            )

        # Rolling 50-period high/low to define current grid range
        dataframe["range_high"] = dataframe["high"].rolling(50).max()
        dataframe["range_low"] = dataframe["low"].rolling(50).min()

        # Grid levels: divide range into N equal parts
        levels = self.buy_grid_levels.value
        grid_size = (dataframe["range_high"] - dataframe["range_low"]) / levels

        # Current grid band: which grid level is price in
        dataframe["grid_size"] = grid_size
        safe_grid_size = grid_size.replace(0, np.nan)
        grid_band_idx = ((dataframe["close"] - dataframe["range_low"]) / safe_grid_size).fillna(0).clip(lower=0).astype(int)
        dataframe["grid_lower"] = (
            dataframe["range_low"] + grid_band_idx * grid_size.fillna(0)
        )
        dataframe["grid_upper"] = dataframe["grid_lower"] + grid_size

        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        chop_col = f"chop_{self.buy_chop_period.value}"

        conditions = (
            # Ranging market confirmed
            (dataframe[chop_col] > self.buy_chop_min.value)
            # Price near lower grid boundary (drops to grid support)
            & (dataframe["close"] <= dataframe["grid_lower"] * 1.005)
            # Price within defined range (not breaking out)
            & (dataframe["close"] > dataframe["range_low"])
            & (dataframe["close"] < dataframe["range_high"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "grid_level_entry"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Price reaches upper grid boundary
            (dataframe["close"] >= dataframe["grid_upper"] * 0.995)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "grid_level_exit"
        return dataframe
