"""ABCD Harmonic V1

Simplest harmonic pattern: AB = CD in both price and time (symmetry).
Uses ZigZag swing points to identify A, B, C pivots, then projects D target.
Enter when price reaches the D completion zone with RSI confirmation.

Pattern: AB leg ≈ CD leg (Fibonacci ratio 1.0 for equal ABCD)
Entry: price hits D zone (C - AB_range) with RSI oversold
Exit: 61.8% Fibonacci retracement of CD leg or RSI overbought

Regime: any (pattern-based, regime-agnostic)
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
import zigzag


class AbcdHarmonicV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 100
    can_short: bool = False

    minimal_roi = {
        "0": 0.06,
        "120": 0.03,
        "360": 0.015,
        "720": 0.01,
    }

    stoploss = -0.04

    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_zigzag_pct = DecimalParameter(0.03, 0.08, default=0.05, decimals=2, space="buy")
    buy_rsi_max = IntParameter(25, 45, default=35, space="buy")
    buy_tolerance = DecimalParameter(0.01, 0.05, default=0.02, decimals=2, space="buy")  # D zone tolerance

    sell_rsi_min = IntParameter(55, 75, default=65, space="sell")

    def _compute_abcd_signal(self, dataframe: DataFrame, pct: float, tolerance: float) -> np.ndarray:
        """Detect bullish ABCD pattern: D completion zone = price near C - (B-A)."""
        signal = np.zeros(len(dataframe), dtype=int)
        close = dataframe["close"].values
        pct_neg = -pct

        try:
            pivots = zigzag.peak_valley_pivots(close, pct, pct_neg)
        except Exception:
            return signal

        pivot_indices = np.where(pivots != 0)[0]
        if len(pivot_indices) < 4:
            return signal

        # Walk through pivot sequence looking for ABCD
        for i in range(len(pivot_indices) - 3):
            ia, ib, ic, id_start = pivot_indices[i:i+4]
            pa, pb, pc = close[ia], close[ib], close[ic]

            # Bullish ABCD: A high, B low, C high, D low
            # A > B, C > B, C < A, D should be near C - (A-B)
            if not (pa > pb and pc > pb and pc < pa):
                continue

            ab = pa - pb
            cd_target = pc - ab  # D = C - AB range (equal legs)
            d_low = cd_target * (1 - tolerance)
            d_high = cd_target * (1 + tolerance)

            # Mark candles from id_start to next pivot as "in D zone"
            end = pivot_indices[i + 4] if i + 4 < len(pivot_indices) else len(close)
            for j in range(id_start, min(end, len(close))):
                if d_low <= close[j] <= d_high:
                    signal[j] = 1

        return signal

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # ABCD signal (computed once with default params for indicator cache)
        dataframe["abcd_signal"] = self._compute_abcd_signal(
            dataframe,
            pct=self.buy_zigzag_pct.value,
            tolerance=self.buy_tolerance.value,
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["abcd_signal"] == 1)
            &
            (dataframe["rsi"] < self.buy_rsi_max.value)
            &
            (dataframe["volume"] > dataframe["volume_sma_20"])
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "abcd_harmonic_d_zone"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "abcd_rsi_exit"

        return dataframe
