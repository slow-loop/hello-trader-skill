"""VWAP Reversion V1

Price deviation from VWAP: enter when price is significantly below VWAP (> X% deviation)
with RSI oversold. Exit when price returns to VWAP.
VWAP here is rolling 24-period (1 day on 1h chart).

Regime: ranging / intraday
Timeframe: 1h
"""

import numpy as np
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta


class VwapReversionV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {"0": 0.03, "60": 0.015, "180": 0.008, "360": 0.004}
    stoploss = -0.025
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    buy_vwap_period = IntParameter(12, 48, default=24, space="buy")
    buy_deviation = DecimalParameter(0.005, 0.03, default=0.015, decimals=3, space="buy")
    buy_rsi_max = IntParameter(25, 45, default=35, space="buy")
    sell_rsi_min = IntParameter(55, 75, default=65, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Rolling VWAP = sum(typical_price * volume) / sum(volume)
        for period in [12, 24, 36, 48]:
            tp = (dataframe["high"] + dataframe["low"] + dataframe["close"]) / 3
            dataframe[f"vwap_{period}"] = (
                (tp * dataframe["volume"]).rolling(period).sum()
                / dataframe["volume"].rolling(period).sum()
            )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p = self.buy_vwap_period.value
        vwap = f"vwap_{p}"
        deviation_pct = self.buy_deviation.value

        conditions = (
            # Price significantly below VWAP
            (dataframe["close"] < dataframe[vwap] * (1 - deviation_pct))
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "vwap_reversion_entry"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p = self.buy_vwap_period.value
        vwap = f"vwap_{p}"
        conditions = (
            (dataframe["close"] >= dataframe[vwap])
            | (dataframe["rsi"] > self.sell_rsi_min.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "vwap_return"
        return dataframe
