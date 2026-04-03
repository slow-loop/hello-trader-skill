"""Volume Profile V1

Simplified volume profile: compute Point of Control (POC) — the price level
with the highest traded volume over the last N candles.
Buy when price pulls back to POC zone (high-volume support).
Sell when price reaches next resistance or RSI overbought.

Regime: ranging / trending (POC acts as support in uptrend)
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta


class VolumeProfileV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 100
    can_short: bool = False

    minimal_roi = {"0": 0.05, "60": 0.025, "180": 0.012, "360": 0.006}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_poc_period = IntParameter(50, 150, default=100, space="buy")
    buy_poc_tolerance = DecimalParameter(0.003, 0.015, default=0.008, decimals=3, space="buy")
    buy_rsi_max = IntParameter(30, 55, default=45, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def _compute_poc(self, dataframe: DataFrame, period: int) -> np.ndarray:
        """Point of Control: price level with max volume over rolling window."""
        poc = np.full(len(dataframe), np.nan)
        closes = dataframe["close"].values
        volumes = dataframe["volume"].values
        highs = dataframe["high"].values
        lows = dataframe["low"].values

        for i in range(period, len(dataframe)):
            window_high = highs[i - period:i].max()
            window_low = lows[i - period:i].min()
            if window_high == window_low:
                poc[i] = closes[i]
                continue

            # Bin prices into 20 levels
            bins = np.linspace(window_low, window_high, 21)
            vol_by_bin = np.zeros(20)

            for j in range(i - period, i):
                price_level = closes[j]
                bin_idx = np.searchsorted(bins[1:], price_level, side="right")
                bin_idx = min(bin_idx, 19)
                vol_by_bin[bin_idx] += volumes[j]

            poc_bin = np.argmax(vol_by_bin)
            poc[i] = (bins[poc_bin] + bins[poc_bin + 1]) / 2

        return poc

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["poc"] = self._compute_poc(dataframe, self.buy_poc_period.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        tol = self.buy_poc_tolerance.value
        conditions = (
            # Price in POC zone
            (dataframe["close"] >= dataframe["poc"] * (1 - tol))
            & (dataframe["close"] <= dataframe["poc"] * (1 + tol))
            # POC acting as support (price above it or at it in uptrend)
            & (dataframe["close"] >= dataframe["ema_50"])
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "volume_poc_support"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
            | (dataframe["close"] < dataframe["ema_50"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "poc_exit"
        return dataframe
