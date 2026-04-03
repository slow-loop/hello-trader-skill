"""MACD Volume V1

Classic momentum strategy: MACD line crosses above signal line (golden cross),
confirmed by volume surge above 20-period SMA. RSI guards against overbought entries.

Regime: trending
Timeframe: 1h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class MacdVolumeV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    minimal_roi = {
        "0": 0.08,
        "120": 0.04,
        "360": 0.02,
        "720": 0.01,
    }

    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_rsi_max = IntParameter(55, 75, default=65, space="buy")
    buy_rsi_min = IntParameter(30, 50, default=40, space="buy")
    buy_vol_factor = DecimalParameter(1.0, 2.0, default=1.2, decimals=1, space="buy")
    buy_macd_hist_min = DecimalParameter(0.0, 100.0, default=0.0, decimals=1, space="buy")

    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD (12, 26, 9)
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Volume SMA
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # EMA 50 — trend direction filter (only trade in direction of trend)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # MACD golden cross: MACD line crosses above signal line
            qtpylib.crossed_above(dataframe["macd"], dataframe["macd_signal"])
            &
            # MACD histogram positive and above minimum threshold
            (dataframe["macd_hist"] > self.buy_macd_hist_min.value)
            &
            # RSI in healthy momentum zone
            (dataframe["rsi"] > self.buy_rsi_min.value)
            &
            (dataframe["rsi"] < self.buy_rsi_max.value)
            &
            # Price above EMA 50 (trade with the trend)
            (dataframe["close"] > dataframe["ema_50"])
            &
            # Volume confirms
            (dataframe["volume"] > dataframe["volume_sma_20"] * self.buy_vol_factor.value)
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "macd_cross_volume"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # MACD death cross
            qtpylib.crossed_above(dataframe["macd_signal"], dataframe["macd"])
            |
            # RSI overbought
            (dataframe["rsi"] > self.sell_rsi_max.value)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "macd_cross_down_or_rsi_ob"

        return dataframe
