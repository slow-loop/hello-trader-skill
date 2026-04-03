"""Bollinger Band + RSI Mean Reversion for Bear Market (4h)

Based on the BbandRsi strategy from freqtrade-strategies by Gert Wohlgemuth,
adapted for bear market 2026 context:
  - 4h timeframe: eliminates 15m noise (lessons: "15m MACD is highly noisy")
  - RSI < 28 on 4h: genuine extreme oversold — rare, high conviction signal
  - Price below BB lower (2.0 std): confirmed multi-period oversell
  - Exit at BB middle: faster exit, doesn't wait for SMA 50 (bear market fix)
  - Volume filter: confirms real panic, not thin-market drift
  - Tight stoploss: -7% appropriate for 4h candle range

Hypothesis: On 4h, extreme oversold conditions (RSI < 28 + price below 2σ band)
have higher predictive power for short-term recovery than 15m signals, because:
1. 4h RSI < 28 is a rare event (high selectivity → less noise)
2. 4h BB lower break requires sustained selling pressure — elastic recovery more likely

Regime: bear/any
Timeframe: 4h
"""
from pandas import DataFrame

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
import talib.abstract as ta
from technical import qtpylib


class BbandRsiBearV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 100
    can_short: bool = False

    # Iter 2: High flat ROI — defer exit to BB-middle signal, not time-based decay.
    # Time-decay ROI (0.5% at 480m) was cutting winners short while losers ran to -6%.
    # At 66% win rate, we need natural BB-middle exits to increase avg win.
    minimal_roi = {
        "0": 0.10
    }

    # 6% stop on 1h: absorbs 1h candle range without excessive whipsaw
    stoploss = -0.06

    trailing_stop = False  # Don't trail: bear market bounces are fast and then reverse

    # Hyperoptable parameters
    buy_rsi_max = IntParameter(18, 35, default=28, space="buy")
    buy_bb_std = DecimalParameter(1.5, 3.0, default=2.0, space="buy")
    buy_volume_factor = DecimalParameter(1.0, 2.5, default=1.2, space="buy")

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)

        # Bollinger bands (main entry and exit reference)
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=20, stds=self.buy_bb_std.value
        )
        dataframe['bb_lower'] = bollinger['lower']
        dataframe['bb_middle'] = bollinger['mid']
        dataframe['bb_upper'] = bollinger['upper']

        # Volume filter
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = (
            # Extreme oversold on 4h (rare, high conviction)
            (dataframe['rsi'] < self.buy_rsi_max.value)
            &
            # Price below lower Bollinger Band
            (dataframe['close'] < dataframe['bb_lower'])
            &
            # Volume confirms panic selling (not thin-market drift)
            (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_factor.value))
            &
            (dataframe['volume'] > 0)
        )

        dataframe.loc[conditions, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Iter 3: Remove RSI > 65 exit — it was cutting winners short before reaching BB middle.
        # Math: avg win was 2.15% vs avg loss 4.21% (R:R = 0.51). Waiting for BB middle
        # should increase avg win toward 3-5% (full mean reversion distance).
        # Only losers (never reach BB middle) are handled by the -6% stoploss.
        conditions = (
            # Exit only at BB middle — let mean reversion play out fully
            qtpylib.crossed_above(dataframe['close'], dataframe['bb_middle'])
        )
        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe
