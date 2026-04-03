"""ROC Momentum V1

Rate of Change (ROC) momentum: enter when ROC crosses above 0 (positive momentum)
confirmed by price above EMA-50 and volume surge.
Exit when ROC turns negative or RSI overbought.

Regime: trending
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class RocMomentumV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 30
    can_short: bool = False

    minimal_roi = {"0": 0.08, "240": 0.04, "720": 0.02, "1440": 0.01}
    stoploss = -0.05
    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    buy_roc_period = IntParameter(10, 20, default=14, space="buy")
    buy_roc_min = DecimalParameter(0.0, 2.0, default=0.5, decimals=1, space="buy")
    buy_rsi_min = IntParameter(40, 60, default=50, space="buy")
    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        for period in range(10, 21):
            dataframe[f"roc_{period}"] = ta.ROC(dataframe, timeperiod=period)
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        roc = f"roc_{self.buy_roc_period.value}"
        conditions = (
            # ROC crosses above threshold (positive momentum)
            qtpylib.crossed_above(dataframe[roc], self.buy_roc_min.value)
            & (dataframe["close"] > dataframe["ema_50"])
            & (dataframe["rsi"] > self.buy_rsi_min.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"])
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "roc_momentum_up"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        roc = f"roc_{self.buy_roc_period.value}"
        conditions = (
            (dataframe[roc] < 0)
            | (dataframe["rsi"] > self.sell_rsi_max.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "roc_negative"
        return dataframe
