"""ICT Liquidity Sweep V3

V2 plus loss control:
- same OHLCV-only sweep/reclaim entry
- tighter stoploss
- time-based bailout for failed bounces

Regime: reversal / ranging
Timeframe: 1h
"""

from __future__ import annotations

from datetime import datetime

from pandas import DataFrame

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
import talib.abstract as ta


class IctLiquiditySweepV3(IStrategy):
    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 72
    can_short: bool = False

    minimal_roi = {
        "0": 0.03,
        "180": 0.018,
        "360": 0.01,
    }
    stoploss = -0.025
    trailing_stop = False

    buy_swing_period = IntParameter(8, 24, default=12, space="buy")
    buy_rsi_max = IntParameter(30, 50, default=45, space="buy")
    buy_volume_factor = DecimalParameter(1.0, 1.8, default=1.1, decimals=2, space="buy")
    buy_adx_max = IntParameter(18, 35, default=30, space="buy")
    sell_rsi_min = IntParameter(55, 70, default=60, space="sell")
    exit_bail_candles = IntParameter(3, 8, default=4, space="sell")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        period = int(self.buy_swing_period.value)

        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["volume_sma_20"] = ta.SMA(dataframe["volume"], timeperiod=20)

        dataframe["swing_low"] = dataframe["low"].rolling(period).min().shift(1)
        dataframe["range_mid"] = (
            dataframe["high"].rolling(period).max().shift(1)
            + dataframe["low"].rolling(period).min().shift(1)
        ) / 2.0

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            (dataframe["low"] < dataframe["swing_low"])
            & (dataframe["close"] > dataframe["swing_low"])
            & (dataframe["close"] > dataframe["open"])
            & (dataframe["rsi"] < self.buy_rsi_max.value)
            & (dataframe["volume"] > dataframe["volume_sma_20"] * self.buy_volume_factor.value)
            & (
                (dataframe["adx"] < self.buy_adx_max.value)
                | (dataframe["close"] >= dataframe["ema_50"])
            )
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[conditions, "enter_long"] = 1
        dataframe.loc[conditions, "enter_tag"] = "liquidity_sweep_reclaim"
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        crossed_range_mid = (
            (dataframe["close"] >= dataframe["range_mid"])
            & (dataframe["close"].shift(1) < dataframe["range_mid"].shift(1))
        )

        conditions = crossed_range_mid | (dataframe["rsi"] > self.sell_rsi_min.value)

        dataframe.loc[conditions, "exit_long"] = 1
        dataframe.loc[conditions, "exit_tag"] = "sweep_mean_revert_exit"
        return dataframe

    def custom_exit(
        self,
        pair: str,
        trade: Trade,
        current_time: datetime,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ) -> str | None:
        max_age_hours = self.exit_bail_candles.value
        age_hours = (current_time - trade.open_date_utc).total_seconds() / 3600

        if age_hours >= max_age_hours and current_profit < 0:
            return "time_bailout"

        return None
