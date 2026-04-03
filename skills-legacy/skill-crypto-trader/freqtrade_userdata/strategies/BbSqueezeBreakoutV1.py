"""Bollinger Band Squeeze Breakout V1

Detects volatility compression (BB width below its own SMA = squeeze),
then enters when price breaks above upper BB on volume surge.
MACD histogram positive confirms upward momentum.

Regime: ranging -> trending transition
Timeframe: 1h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
import talib.abstract as ta
from technical import qtpylib


class BbSqueezeBreakoutV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    # Breakout can run — wider ROI
    minimal_roi = {
        "0": 0.10,      # 10% immediate
        "240": 0.05,    # 5% after 4h
        "480": 0.025,   # 2.5% after 8h
        "720": 0.01,    # 1% after 12h
    }

    stoploss = -0.05  # -5%

    trailing_stop = True
    trailing_stop_positive = 0.02
    trailing_stop_positive_offset = 0.04
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_bb_period = IntParameter(15, 25, default=20, space="buy")
    buy_squeeze_window = IntParameter(20, 50, default=30, space="buy")  # how long to measure avg width
    buy_squeeze_threshold = DecimalParameter(0.5, 0.9, default=0.7, decimals=2, space="buy")  # BB width < X * its SMA
    buy_vol_factor = DecimalParameter(1.2, 2.5, default=1.5, decimals=1, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Bollinger Bands
        for period in range(15, 26):
            bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=period, stds=2)
            dataframe[f"bb_upper_{period}"] = bollinger["upper"]
            dataframe[f"bb_lower_{period}"] = bollinger["lower"]
            dataframe[f"bb_mid_{period}"] = bollinger["mid"]
            dataframe[f"bb_width_{period}"] = (bollinger["upper"] - bollinger["lower"]) / bollinger["mid"]

        # BB width SMA — squeeze when width is below its own average
        for period in [15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]:
            for sq in [20, 30, 40, 50]:
                dataframe[f"bb_width_sma_{period}_{sq}"] = ta.SMA(dataframe[f"bb_width_{period}"], timeperiod=sq)

        # MACD — momentum confirmation
        macd = ta.MACD(dataframe, fastperiod=12, slowperiod=26, signalperiod=9)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # Volume SMA
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p = self.buy_bb_period.value
        sq = self.buy_squeeze_window.value

        bb_width = f"bb_width_{p}"
        bb_width_sma = f"bb_width_sma_{p}_{sq}"
        bb_upper = f"bb_upper_{p}"

        conditions = (
            # Squeeze: BB width below its rolling average (compression phase)
            (dataframe[bb_width].shift(1) < dataframe[bb_width_sma].shift(1) * self.buy_squeeze_threshold.value)
            &
            # Breakout: close crosses above upper BB
            qtpylib.crossed_above(dataframe["close"], dataframe[bb_upper])
            &
            # MACD histogram positive (upward momentum)
            (dataframe["macd_hist"] > 0)
            &
            # Volume confirms
            (dataframe["volume"] > dataframe["volume_sma_20"] * self.buy_vol_factor.value)
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "bb_squeeze_breakout"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        p = self.buy_bb_period.value

        conditions = (
            # Price falls back below BB mid (momentum lost)
            (dataframe["close"] < dataframe[f"bb_mid_{p}"])
            |
            # MACD histogram turns negative
            (dataframe["macd_hist"] < 0)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "bb_squeeze_exit"

        return dataframe
