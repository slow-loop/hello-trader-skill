"""MA Fan V1

Moving average fan: multiple EMAs (10/20/50/100/200) all aligned in order
(ema10 > ema20 > ema50 > ema100 > ema200) = strong bull trend.
Enter when fan just aligns after a period of disorder.
Exit when any two adjacent MAs cross (fan collapses).

Regime: strong trending
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta


class MaFanV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 210
    can_short: bool = False

    minimal_roi = {"0": 0.15, "480": 0.08, "1440": 0.04, "2880": 0.02}
    stoploss = -0.07
    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.07
    trailing_only_offset_is_reached = True

    buy_rsi_min = IntParameter(40, 60, default=50, space="buy")
    buy_rsi_max = IntParameter(60, 80, default=70, space="buy")
    sell_rsi_max = IntParameter(70, 90, default=80, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for p in [10, 20, 50, 100, 200]:
            dataframe[f"ema_{p}"] = ta.EMA(dataframe, timeperiod=p)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Fan alignment: all EMAs in bullish order
        dataframe["fan_bullish"] = (
            (dataframe["ema_10"] > dataframe["ema_20"])
            & (dataframe["ema_20"] > dataframe["ema_50"])
            & (dataframe["ema_50"] > dataframe["ema_100"])
            & (dataframe["ema_100"] > dataframe["ema_200"])
        ).astype(int)

        # Fan just aligned: current bar is aligned, previous was not
        dataframe["fan_just_aligned"] = (
            (dataframe["fan_bullish"] == 1)
            & (dataframe["fan_bullish"].shift(1) == 0)
        ).astype(int)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["fan_just_aligned"] == 1)
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "ma_fan_aligned"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit when fan breaks: ema10 drops below ema20
        conditions = (
            (dataframe["ema_10"] < dataframe["ema_20"])
            | (dataframe["rsi"] > self.sell_rsi_max.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "ma_fan_collapse"
        return dataframe
