"""ICT Liquidity Sweep V1

Liquidity sweep: price spikes above/below a swing high/low (sweeping stop orders),
then immediately reverses. Signals institutional stop-hunt followed by reversal.

Uses smartmoneyconcepts for swing high/low detection.
Bullish sweep: price wicks below swing low then closes back above it.
Entry: candle after sweep, with RSI oversold confirmation.

Regime: reversal
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta

try:
    import smartmoneyconcepts as smc
    SMC_AVAILABLE = True
except ImportError:
    SMC_AVAILABLE = False


class IctLiquiditySweepV1(IStrategy):

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

    buy_rsi_max = IntParameter(30, 50, default=40, space="buy")
    buy_swing_length = IntParameter(5, 15, default=10, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def _compute_sweep_signal(self, dataframe: DataFrame, swing_length: int) -> np.ndarray:
        """Detect bullish liquidity sweep: wick below swing low, close back above."""
        signal = np.zeros(len(dataframe), dtype=int)
        if not SMC_AVAILABLE or len(dataframe) < swing_length + 5:
            return signal

        try:
            swing = smc.smc.swing_highs_lows(dataframe, swing_length=swing_length)
            # Swing lows = liquidity below
            swing_low_idx = swing[swing["HighLow"] == -1].index

            high = dataframe["high"].values
            low = dataframe["low"].values
            close = dataframe["close"].values

            for idx in swing_low_idx:
                pos = dataframe.index.get_loc(idx)
                if pos + 3 >= len(dataframe):
                    continue
                swing_low_price = low[pos]

                # Look for sweep in next 3 candles
                for j in range(pos + 1, min(pos + 4, len(dataframe))):
                    if low[j] < swing_low_price and close[j] > swing_low_price:
                        # Sweep confirmed: wick below, close above
                        signal[j] = 1
        except Exception:
            pass

        return signal

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        dataframe["sweep_signal"] = self._compute_sweep_signal(
            dataframe, self.buy_swing_length.value
        )
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["sweep_signal"] == 1)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "liquidity_sweep_bullish"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
            | (dataframe["close"] < dataframe["ema_50"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "sweep_exit"
        return dataframe
