"""Envelope RSI V1

Price channel: SMA ± N%. Buy when price dips below lower envelope (SMA - N%)
with RSI oversold. Exit when price returns to SMA or RSI overbought.

Regime: ranging
Timeframe: 1h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta


class EnvelopeRsiV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 30
    can_short: bool = False

    minimal_roi = {"0": 0.04, "60": 0.02, "180": 0.01, "360": 0.005}
    stoploss = -0.03
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.02
    trailing_only_offset_is_reached = True

    buy_sma_period = IntParameter(15, 30, default=20, space="buy")
    buy_env_pct = DecimalParameter(0.01, 0.05, default=0.02, decimals=2, space="buy")
    buy_rsi_max = IntParameter(25, 40, default=32, space="buy")
    sell_rsi_min = IntParameter(55, 75, default=65, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in range(15, 31):
            dataframe[f"sma_{period}"] = ta.SMA(dataframe["close"], timeperiod=period)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sma = f"sma_{self.buy_sma_period.value}"
        lower_env = dataframe[sma] * (1 - self.buy_env_pct.value)
        conditions = (
            (dataframe["close"] < lower_env)
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "envelope_lower_rsi"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        sma = f"sma_{self.buy_sma_period.value}"
        conditions = (
            (dataframe["close"] >= dataframe[sma])
            | (dataframe["rsi"] > self.sell_rsi_min.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "envelope_sma_exit"
        return dataframe
