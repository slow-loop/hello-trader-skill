"""Harmonic XABCD V1

Uses pyharmonics library to detect XABCD patterns (Gartley, Bat, Butterfly, Crab).
Enters at D completion zone with RSI confirmation.
Each pattern has distinct Fibonacci ratios defining the PRZ (Potential Reversal Zone).

Patterns:
  Gartley:   B=0.618, C=0.382-0.886, D=0.786
  Bat:       B=0.382-0.5, C=0.382-0.886, D=0.886
  Butterfly: B=0.786, C=0.382-0.886, D=1.27-1.618
  Crab:      B=0.382-0.618, C=0.382-0.886, D=1.618

Regime: any (pattern-based)
Timeframe: 4h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta

try:
    from pyharmonics.technicals import Technicals
    from pyharmonics.search import HarmonicSearch
    PYHARMONICS_AVAILABLE = True
except ImportError:
    PYHARMONICS_AVAILABLE = False


class HarmonicXabcdV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 200
    can_short: bool = False

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02, "1440": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    buy_rsi_max = IntParameter(25, 50, default=45, space="buy")
    buy_rsi_min = IntParameter(20, 40, default=25, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def _detect_harmonic_signal(self, dataframe: DataFrame) -> np.ndarray:
        """Run pyharmonics and return signal array (1 = pattern D zone active)."""
        signal = np.zeros(len(dataframe), dtype=int)
        if not PYHARMONICS_AVAILABLE or len(dataframe) < 100:
            return signal

        try:
            chart = Technicals(dataframe.copy(), "CRYPTO", "4h")
            search = HarmonicSearch(chart)
            search.search()

            # Get all XABCD bullish patterns
            patterns = search.get_patterns(family=search.XABCD)
            if not patterns:
                return signal

            for pattern in patterns:
                # pattern.x is the index positions of X,A,B,C,D
                # pattern.bullish = True for bullish (buy) setups
                if not getattr(pattern, "bullish", True):
                    continue
                try:
                    d_idx = int(pattern.x[-1])  # D point index
                    # Mark window of 3 candles around D as signal zone
                    for i in range(max(0, d_idx - 1), min(len(signal), d_idx + 3)):
                        signal[i] = 1
                except (IndexError, TypeError):
                    continue
        except Exception:
            pass

        return signal

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["harmonic_signal"] = self._detect_harmonic_signal(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["harmonic_signal"] == 1)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "harmonic_xabcd_d_zone"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (dataframe["rsi"] > self.sell_rsi_min.value)
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "harmonic_rsi_exit"
        return dataframe
