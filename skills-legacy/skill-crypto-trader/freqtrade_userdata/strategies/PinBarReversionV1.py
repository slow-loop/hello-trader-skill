"""Pin Bar Reversion V1

Pin bar (hammer): long lower wick >= 2x body, close near top of candle.
Signals rejection of lower prices. Enter at close of pin bar.
ADX filter ensures non-trending (or early trend) context.

Regime: reversal / ranging
Timeframe: 4h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta


class PinBarReversionV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 30
    can_short: bool = False

    minimal_roi = {"0": 0.06, "120": 0.03, "360": 0.015, "720": 0.01}
    stoploss = -0.04
    trailing_stop = True
    trailing_stop_positive = 0.015
    trailing_stop_positive_offset = 0.03
    trailing_only_offset_is_reached = True

    buy_wick_ratio = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy")
    buy_rsi_max = IntParameter(30, 55, default=45, space="buy")
    buy_adx_max = IntParameter(20, 40, default=30, space="buy")
    sell_rsi_min = IntParameter(60, 80, default=70, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # Pin bar components
        body = abs(dataframe["close"] - dataframe["open"])
        lower_wick = dataframe[["open", "close"]].min(axis=1) - dataframe["low"]
        upper_wick = dataframe["high"] - dataframe[["open", "close"]].max(axis=1)
        candle_range = dataframe["high"] - dataframe["low"]

        dataframe["body"] = body
        dataframe["lower_wick"] = lower_wick
        dataframe["upper_wick"] = upper_wick
        dataframe["candle_range"] = candle_range

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ratio = self.buy_wick_ratio.value
        body = dataframe["body"].replace(0, 1e-8)  # avoid div by zero

        bullish_pin = (
            # Lower wick >= ratio * body (strong rejection of lows)
            (dataframe["lower_wick"] >= body * ratio)
            # Upper wick is small (clean close near top)
            & (dataframe["upper_wick"] <= dataframe["lower_wick"] * 0.5)
            # Body is not too large (it's a pin, not engulfing)
            & (dataframe["body"] <= dataframe["candle_range"] * 0.4)
        )

        conditions = (
            bullish_pin
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["adx"] < self.buy_adx_max.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "pin_bar_bullish"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["rsi"] > self.sell_rsi_min.value)
            | (dataframe["close"] < dataframe["ema_50"])
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "pin_bar_exit"
        return dataframe
