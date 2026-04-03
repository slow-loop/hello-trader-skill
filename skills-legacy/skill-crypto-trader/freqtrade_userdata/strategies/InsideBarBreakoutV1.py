"""Inside Bar Breakout V1

Inside bar = current candle's high/low entirely within previous candle's range.
Signals volatility compression. Enter on breakout above the mother bar high.
ADX confirms trend context; volume confirms breakout is real.

Regime: trending (breakout from consolidation)
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class InsideBarBreakoutV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 30
    can_short: bool = False

    minimal_roi = {
        "0": 0.08,
        "240": 0.04,
        "720": 0.02,
        "1440": 0.01,
    }

    stoploss = -0.05

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_adx_min = IntParameter(15, 35, default=20, space="buy")
    buy_vol_factor = DecimalParameter(1.0, 2.5, default=1.3, decimals=1, space="buy")
    buy_rsi_min = IntParameter(40, 60, default=50, space="buy")

    sell_rsi_max = IntParameter(65, 85, default=75, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ADX — trend strength
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # Volume SMA
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        # EMA 50 — trend direction
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)

        # Inside bar detection
        # Inside bar: high < prev high AND low > prev low
        dataframe["inside_bar"] = (
            (dataframe["high"] < dataframe["high"].shift(1))
            & (dataframe["low"] > dataframe["low"].shift(1))
        ).astype(int)

        # Mother bar high (previous candle's high = breakout level)
        dataframe["mother_high"] = dataframe["high"].shift(1)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Entry: candle AFTER inside bar closes above mother bar high
        conditions = (
            # Previous candle was an inside bar
            (dataframe["inside_bar"].shift(1) == 1)
            &
            # Breakout above mother bar's high
            (dataframe["close"] > dataframe["mother_high"].shift(1))
            &
            # Trend context
            (dataframe["close"] > dataframe["ema_50"])
            &
            (dataframe["adx"] > self.buy_adx_min.value)
            &
            # RSI confirms momentum
            (dataframe["rsi"] > self.buy_rsi_min.value)
            &
            # Volume surge
            (dataframe["volume"] > dataframe["volume_sma_20"] * self.buy_vol_factor.value)
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "inside_bar_breakout"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # RSI overbought
            (dataframe["rsi"] > self.sell_rsi_max.value)
            |
            # Price drops back below EMA 50
            (dataframe["close"] < dataframe["ema_50"])
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "inside_bar_exit"

        return dataframe
