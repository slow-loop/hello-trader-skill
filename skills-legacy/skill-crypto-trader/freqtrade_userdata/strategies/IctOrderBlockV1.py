"""ICT Order Block V1

Order block: last bearish candle before a strong bullish impulse (institutional supply/demand zone).
Price returning to order block zone = re-test of institutional interest.

Uses smartmoneyconcepts for OB detection.
Bullish OB: last down candle before strong up move. Price retraces to OB = long entry.

Regime: trending (pullback entry)
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta

try:
    import smartmoneyconcepts as smc
    SMC_AVAILABLE = True
except ImportError:
    SMC_AVAILABLE = False


class IctOrderBlockV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {"0": 0.06, "60": 0.03, "180": 0.015, "360": 0.008}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_rsi_max = IntParameter(30, 60, default=50, space="buy")
    buy_swing_length = IntParameter(5, 15, default=10, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def _compute_ob_signal(self, dataframe: DataFrame, swing_length: int) -> np.ndarray:
        """Detect when price retraces into a bullish order block."""
        signal = np.zeros(len(dataframe), dtype=int)
        if not SMC_AVAILABLE or len(dataframe) < swing_length + 5:
            return signal

        try:
            ob_df = smc.smc.ob(dataframe, swing_length=swing_length)
            # OB > 0 = bullish order block active
            bullish_ob = ob_df["OB"] > 0
            signal[bullish_ob.values] = 1
        except Exception:
            pass

        return signal

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["ob_signal"] = self._compute_ob_signal(
            dataframe, self.buy_swing_length.value
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["ob_signal"] == 1)
            & (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "ict_order_block"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
            | (dataframe["close"] < dataframe["ema_50"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "ob_exit"
        return dataframe
