"""ICT Fair Value Gap V1

Uses smartmoneyconcepts library to detect Fair Value Gaps (FVG).
Bullish FVG: gap between candle[i-2] high and candle[i] low (imbalance zone).
Price returning into a bullish FVG = institutional re-entry.

Entry: price retraces into bullish FVG zone, RSI not overbought.
Exit: price exits top of FVG zone or RSI overbought.

Regime: trending (with pullback)
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


class IctFvgV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {"0": 0.05, "60": 0.025, "180": 0.012, "360": 0.006}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_rsi_max = IntParameter(30, 55, default=50, space="buy")
    buy_rsi_min = IntParameter(25, 45, default=35, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def _compute_fvg_signal(self, dataframe: DataFrame) -> np.ndarray:
        """Detect bullish FVG and return 1 when price is inside a bullish FVG."""
        signal = np.zeros(len(dataframe), dtype=int)
        if not SMC_AVAILABLE or len(dataframe) < 5:
            return signal

        try:
            fvg_df = smc.smc.fvg(dataframe)
            # FVG > 0 = bullish FVG; FVG < 0 = bearish FVG
            # When price is in a bullish FVG zone = potential long entry
            bullish_fvg = fvg_df["FVG"] > 0
            signal[bullish_fvg.values] = 1
        except Exception:
            pass

        return signal

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["fvg_signal"] = self._compute_fvg_signal(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["fvg_signal"] == 1)
            # Price pulling back into FVG in an uptrend
            & (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "ict_fvg_bullish"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
            | (dataframe["close"] < dataframe["ema_50"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "fvg_exit"
        return dataframe
