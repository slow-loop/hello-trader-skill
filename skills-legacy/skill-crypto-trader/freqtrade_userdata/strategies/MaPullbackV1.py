"""MA Pullback V1

In an established uptrend (price above EMA-200), wait for price to pull back
to EMA-50, then enter when it bounces with RSI recovering from oversold.

Classic "buy the dip in a bull trend" setup.

Regime: trending_up
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class MaPullbackV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 210
    can_short: bool = False

    minimal_roi = {"0": 0.10, "480": 0.05, "1440": 0.025, "2880": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.025
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    buy_ema_fast = IntParameter(30, 60, default=50, space="buy")
    buy_ema_slow = IntParameter(150, 210, default=200, space="buy")
    buy_pullback_pct = DecimalParameter(0.98, 1.01, default=1.005, decimals=3, space="buy")
    buy_rsi_max = IntParameter(35, 55, default=45, space="buy")
    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in list(range(30, 61)) + list(range(150, 211, 10)):
            dataframe[f"ema_{period}"] = ta.EMA(dataframe, timeperiod=period)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_fast = f"ema_{self.buy_ema_fast.value}"
        ema_slow = f"ema_{self.buy_ema_slow.value}"
        pullback = self.buy_pullback_pct.value

        conditions = (
            # Macro uptrend: price above EMA-200
            (dataframe["close"] > dataframe[ema_slow])
            # Price pulled back to EMA-50 zone
            & (dataframe["low"] <= dataframe[ema_fast] * pullback)
            & (dataframe["close"] > dataframe[ema_fast] * 0.99)
            # RSI recovered from oversold
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            # Bullish close (close > open)
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "ma_pullback_bounce"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ema_slow = f"ema_{self.buy_ema_slow.value}"
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_max.value)
            | (dataframe["close"] < dataframe[ema_slow])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "ma_pullback_exit"
        return dataframe
