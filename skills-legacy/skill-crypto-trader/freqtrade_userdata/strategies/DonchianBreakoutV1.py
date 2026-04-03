"""Donchian Breakout V1 (Turtle Trading)

Classic Donchian Channel breakout: enter when price closes above 20-period high,
exit when price closes below 10-period low. Volume spike confirms real breakout.
ATR-based stoploss for volatility-adjusted risk.

Regime: trending
Timeframe: 4h
"""

from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter
import talib.abstract as ta
from technical import qtpylib


class DonchianBreakoutV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "4h"
    startup_candle_count: int = 50
    can_short: bool = False

    # Trend breakout — let profits run
    minimal_roi = {
        "0": 0.15,      # 15% immediate
        "480": 0.08,    # 8% after 2d
        "1440": 0.04,   # 4% after 6d
        "2880": 0.02,   # 2% after 12d
    }

    stoploss = -0.06  # -6%

    trailing_stop = True
    trailing_stop_positive = 0.03
    trailing_stop_positive_offset = 0.06
    trailing_only_offset_is_reached = True

    # Hyperopt parameters
    buy_period_high = IntParameter(15, 30, default=20, space="buy")
    buy_period_low = IntParameter(5, 15, default=10, space="buy")
    buy_vol_factor = IntParameter(1, 3, default=2, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Donchian Channel — upper (entry) and lower (exit)
        for p in range(5, 31):
            dataframe[f"dc_high_{p}"] = ta.MAX(dataframe["high"], timeperiod=p)
            dataframe[f"dc_low_{p}"] = ta.MIN(dataframe["low"], timeperiod=p)

        # ATR for volatility reference
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # Volume SMA
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dc_high = f"dc_high_{self.buy_period_high.value}"

        # Close breaks above the Donchian upper channel (previous N-period high)
        # Use shift(1) to avoid lookahead: compare current close vs previous high
        conditions = (
            (dataframe["close"] > dataframe[dc_high].shift(1))
            &
            # Volume confirms breakout
            (dataframe["volume"] > dataframe["volume_sma_20"] * self.buy_vol_factor.value)
            &
            (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "donchian_breakout_up"

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dc_low = f"dc_low_{self.buy_period_low.value}"

        # Close breaks below Donchian lower channel (previous N-period low)
        conditions = (
            dataframe["close"] < dataframe[dc_low].shift(1)
        )

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "donchian_breakdown"

        return dataframe
