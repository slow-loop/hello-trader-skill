"""CombinedBinHAndCluc V1 — Bear Market Port

Direct port of CombinedBinHAndCluc (berlinguyinca, freqtrade-strategies),
updated for Freqtrade 2026.2 and adapted for bear market 2026:

Changes vs original:
  - Freqtrade v3 interface (enter_long instead of buy)
  - Tighter stoploss: -0.04 (vs -0.05) for bear market
  - exit_profit_only = True preserved: exit signal only fires when in profit
    → prevents cutting winning trades while letting stoploss handle losses
  - Volume limit in Cluc kept to filter manipulated candles

Signal logic (unchanged from original):
  [BinH] Bollinger band squeeze + close below lower band + wick structure
  [Cluc] Close below EMA-50 + well below BB lower + not on abnormal volume

Both signals target extreme oversold microstructure — designed to catch
liquidation wicks where price overshoots and quickly snaps back.

Regime: any (originally designed for multiple regimes)
Timeframe: 5m
"""
import numpy as np
from pandas import DataFrame

import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.strategy import IStrategy


def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - (rolling_std * num_of_std)
    return np.nan_to_num(rolling_mean), np.nan_to_num(lower_band)


class ClucBearV1(IStrategy):

    INTERFACE_VERSION: int = 3
    timeframe = "5m"
    startup_candle_count: int = 100
    can_short: bool = False

    # Original: 5% target. Kept — high enough to let trades run to BB middle.
    minimal_roi = {
        "0": 0.05
    }

    # Slightly tighter than original (-0.05) for bear market
    stoploss = -0.04

    # KEY: exit signal only fires when in profit → prevents premature exits
    use_exit_signal = True
    exit_profit_only = True
    ignore_roi_if_entry_signal = False

    trailing_stop = False

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # === BinHV45 indicators ===
        mid, lower = bollinger_bands(dataframe['close'], window_size=40, num_of_std=2)
        dataframe['lower'] = lower
        dataframe['bbdelta'] = (mid - dataframe['lower']).abs()
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()

        # === ClucMay72018 indicators ===
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=2
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=50)
        dataframe['volume_mean_slow'] = dataframe['volume'].rolling(window=30).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # === BinHV45 condition ===
                # BB is compressed (squeeze) and price drops below lower band with small wick
                dataframe['lower'].shift().gt(0)
                & dataframe['bbdelta'].gt(dataframe['close'] * 0.008)      # BB wide enough
                & dataframe['closedelta'].gt(dataframe['close'] * 0.0175)  # meaningful move
                & dataframe['tail'].lt(dataframe['bbdelta'] * 0.25)        # small lower wick
                & dataframe['close'].lt(dataframe['lower'].shift())         # below BB lower
                & dataframe['close'].le(dataframe['close'].shift())         # closing down
            )
            |
            (
                # === ClucMay72018 condition ===
                # Price below EMA slow + well below BB lower + not on spike volume
                (dataframe['close'] < dataframe['ema_slow'])
                & (dataframe['close'] < 0.985 * dataframe['bb_lowerband'])  # 1.5% below lower band
                & (dataframe['volume'] < (dataframe['volume_mean_slow'].shift(1) * 20))  # not volume spike
            ),
            'enter_long'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (dataframe['close'] > dataframe['bb_middleband']),
            'exit_long'
        ] = 1
        return dataframe
