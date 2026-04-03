"""Mean Reversion Hypothesis B: ADX Ranging Filter

Hypothesis: Z-Score mean reversion should ONLY be applied in RANGING markets
(ADX < 30). In bear markets, high ADX (>30) signals a strong directional
downtrend — entering mean reversion during those conditions catches falling
knives. Waiting for ADX < 30 forces entries only during consolidation phases
where statistical mean reversion is geometrically plausible.

Changes vs AnyMeanRevertZScoreV1 (two variables):
  1. [Primary] ADX < buy_adx_max filter (new)
  2. [Fix] Exit at BB middle cross instead of SMA 50 cross (SMA 50 is too far
     above price in sustained bear markets, causing endless holding)

Regime: bear/ranging (consolidation phases only)
Timeframe: 15m
"""
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    DecimalParameter,
    IntParameter,
)
import talib.abstract as ta
from technical import qtpylib


class MeanRevertHypoB(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "15m"
    startup_candle_count: int = 200
    can_short: bool = False

    # Iter 2: Raise ROI to create positive R:R vs -3% stoploss
    # Math: 3% target / 3% stop = 1.0 R:R; at 55% win rate → profit factor ~1.22
    minimal_roi = {
        "0": 0.03,
        "30": 0.02,
        "60": 0.01,
        "120": 0.005
    }

    # Iter 2: Tighter stoploss to reduce loss size (was -0.05)
    stoploss = -0.03

    # No trailing stop: bear market reversals are sharp and brief
    trailing_stop = False

    # Hyperoptable parameters
    buy_zscore_thresh = DecimalParameter(2.0, 3.5, default=2.5, space="buy")
    buy_volume_spike = DecimalParameter(1.2, 2.5, default=1.5, space="buy")
    buy_rsi_max = IntParameter(20, 35, default=28, space="buy")
    buy_adx_max = IntParameter(20, 40, default=30, space="buy")  # PRIMARY: ADX filter

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Z-Score: price deviation from rolling mean
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['std_50'] = ta.STDDEV(dataframe, timeperiod=50)
        dataframe['z_score'] = (
            (dataframe['close'] - dataframe['sma_50'])
            / dataframe['std_50'].replace(0, 1e-9)
        )

        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)

        # ADX: trend strength — low ADX = ranging market
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=14)

        # BB middle for exit (faster than SMA 50 in bear markets)
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_middle'] = bollinger['mid']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Extreme statistical deviation from mean (capitulation wick)
            (dataframe['z_score'] < -self.buy_zscore_thresh.value)
            &
            # Volume spike: panic selling / liquidations
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_spike.value))
            &
            # Oversold momentum
            (dataframe['rsi'] < self.buy_rsi_max.value)
            &
            # PRIMARY HYPOTHESIS: Only enter in ranging markets (not strong downtrends)
            (dataframe['adx'] < self.buy_adx_max.value)
            &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[conditions, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # BB middle cross: mean partially recovered (faster than SMA 50 in bear market)
            qtpylib.crossed_above(dataframe['close'], dataframe['bb_middle'])
            |
            # Momentum exhausted (slightly tighter than 70 to lock in gains faster)
            (dataframe['rsi'] > 65)
        )
        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe
