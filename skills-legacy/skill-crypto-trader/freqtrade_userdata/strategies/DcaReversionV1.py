"""DCA Reversion V1

Dollar Cost Averaging adapted for Freqtrade: systematic re-entry on dips.
Initial entry on RSI oversold + BB lower. If price drops further N%,
custom_entry_price signals a lower re-entry (Freqtrade handles via adjust_trade_position).

Uses adjust_trade_position to add to position on each dip level.
Max 3 DCA levels, each adding 1x the initial stake.

Regime: ranging / bull pullback
Timeframe: 1h
"""

from typing import Optional
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, DecimalParameter
from freqtrade.persistence import Trade
import talib.abstract as ta
from technical import qtpylib


class DcaReversionV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    # Allow position adjustment (DCA)
    position_adjustment_enable = True
    max_dca_multiplier = 4.0  # max total position = 4x initial stake

    minimal_roi = {"0": 0.04, "60": 0.02, "180": 0.01, "360": 0.005}
    stoploss = -0.12  # Wide — DCA needs room before averaging down
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.025
    trailing_only_offset_is_reached = True

    buy_rsi_max = IntParameter(25, 40, default=32, space="buy")
    buy_dca_drop = DecimalParameter(0.02, 0.06, default=0.03, decimals=2, space="buy")
    buy_adx_max = IntParameter(20, 35, default=25, space="buy")
    sell_rsi_min = IntParameter(55, 75, default=65, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=20, stds=2)
        dataframe["bb_lower"] = bollinger["lower"]
        dataframe["bb_mid"] = bollinger["mid"]
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Initial entry: RSI oversold + price at BB lower
        conditions = (
            (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["close"] <= dataframe["bb_lower"] * 1.005)
            & (dataframe["adx"] < self.buy_adx_max.value)
            & (dataframe["volume"] > 0)
        )
        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "dca_initial_entry"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["close"] >= dataframe["bb_mid"])
            | (dataframe["rsi"] > self.sell_rsi_min.value)
        )
        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "dca_exit_target"
        return dataframe

    def adjust_trade_position(
        self,
        trade: Trade,
        current_time,
        current_rate: float,
        current_profit: float,
        min_stake: Optional[float],
        max_stake: float,
        current_entry_rate: float,
        current_exit_rate: float,
        current_entry_profit: float,
        current_exit_profit: float,
        **kwargs,
    ) -> Optional[float]:
        """Add to position on each DCA drop level (max 3 additions)."""
        if current_profit > -self.buy_dca_drop.value:
            return None  # Not dropped enough yet

        filled_entries = trade.select_filled_orders(trade.entry_side)
        dca_count = len(filled_entries) - 1  # subtract initial entry

        # Max 3 DCA levels
        if dca_count >= 3:
            return None

        # Each DCA level requires an additional drop
        required_drop = self.buy_dca_drop.value * (dca_count + 1)
        if current_profit > -required_drop:
            return None

        # Add 1x initial stake at each level
        initial_stake = filled_entries[0].cost
        return min(initial_stake, max_stake)
