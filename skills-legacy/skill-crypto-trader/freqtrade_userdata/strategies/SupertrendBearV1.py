"""Supertrend Trend-Following for Bear Market Context (1h)

Fundamentally different from all previous mean-reversion attempts.
Uses a single Supertrend indicator on 1h to catch LOCAL trend reversals
(brief bullish phases within an overall bear market).

Why this might work in bear market:
- Mean reversion failed because bear market has no stable "mean" to revert to
- Supertrend adapts to local price action — it can be bullish even in bear market
  during genuine short-term relief rallies
- We enter only on the TRANSITION (down→up flip) to avoid entering mid-rally
- We exit on the REVERSE TRANSITION (up→down flip) to cut losses when rally ends

Signal logic:
- ATR-based upper/lower bands around midpoint
- Supertrend: price above final_lb → bullish; price below final_ub → bearish
- Entry: transition from bearish to bullish + volume > 1.5x avg
- Exit: transition from bullish to bearish

Session 2 iteration history (entry filter experiments):
- Iter 7: RSI > 50 — no effect (all 58 baseline entries naturally have RSI>50 at flip time)
- Iter 7b: RSI > 60 — hurt (49 trades, WR 28.6%, PF 0.83; RSI 50-60 entries had WR 44%)
- Iter 8: 2-candle confirm — hurt (55 trades, PF 0.62; 1-candle delay misses rally onset)
- Iter 9: ADX < 25 — hurt (41 trades, WR 29.3%; high-ADX entries actually had better WR 35%)
- Iter 10: 1d Supertrend gate — hurt (26 trades, WR 23.1%; 1d mostly bearish in bear market)

Conclusion: Supertrend flip + volume is already the optimal entry filter for this regime.
Every additional filter removes the better trades. No improvement possible through entry filtering.

Next direction: IS/OOS temporal split to assess robustness.

Stoploss: -5% safety net for rapid reversals
Timeframe: 1h
"""
import numpy as np
import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
import talib.abstract as ta


class SupertrendBearV1(IStrategy):

    INTERFACE_VERSION = 3
    timeframe = "1h"
    startup_candle_count: int = 50
    can_short: bool = False

    # High flat ROI: let Supertrend exit signal handle position management
    minimal_roi = {
        "0": 0.10
    }

    # Safety net for gap-downs / overnight crashes (Supertrend won't catch instantaneous drops)
    stoploss = -0.05

    # Trailing stop proven harmful (iter 6): cut winners short, WR 31→22%, PF 1.04→0.60
    trailing_stop = False

    # Best confirmed params: period=7, mult=3.0, volume=1.5x
    atr_period = IntParameter(5, 21, default=7, space="buy")
    atr_multiplier = DecimalParameter(1.5, 5.0, default=3.0, space="buy")
    buy_volume_factor = DecimalParameter(1.0, 3.0, default=1.5, space="buy")

    @staticmethod
    def supertrend(dataframe: pd.DataFrame, multiplier: float, period: int) -> pd.DataFrame:
        """Compute Supertrend direction without lookahead bias."""
        df = dataframe.copy()
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        length = len(df)

        # ATR using simple rolling mean of TR
        tr = ta.TRANGE(df['high'], df['low'], df['close'])
        atr = pd.Series(tr).rolling(period).mean().to_numpy()

        # Basic bands
        midpoint = (high + low) / 2.0
        basic_ub = midpoint + multiplier * atr
        basic_lb = midpoint - multiplier * atr

        # Final bands — use zeros so first iteration resets correctly
        # (np.nan causes NaN comparisons to return False, breaking initialization)
        final_ub = np.zeros(length)
        final_lb = np.zeros(length)

        for i in range(period, length):
            final_ub[i] = (
                basic_ub[i]
                if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]
                else final_ub[i - 1]
            )
            final_lb[i] = (
                basic_lb[i]
                if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]
                else final_lb[i - 1]
            )

        # Supertrend state machine
        st = np.zeros(length)
        for i in range(period, length):
            if st[i - 1] == final_ub[i - 1]:
                st[i] = final_ub[i] if close[i] <= final_ub[i] else final_lb[i]
            elif st[i - 1] == final_lb[i - 1]:
                st[i] = final_lb[i] if close[i] >= final_lb[i] else final_ub[i]

        # Direction: 'up' when price above ST line (bullish), 'down' otherwise
        direction = np.where(
            st > 0,
            np.where(close < st, 'down', 'up'),
            None
        )

        return pd.DataFrame({'ST': st, 'STX': direction}, index=df.index)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        st_result = self.supertrend(
            dataframe,
            multiplier=self.atr_multiplier.value,
            period=self.atr_period.value,
        )
        dataframe['supertrend'] = st_result['STX']
        dataframe['supertrend_line'] = st_result['ST']
        dataframe['vol_sma_20'] = ta.SMA(dataframe['volume'], timeperiod=20)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Enter on Supertrend transition (down→up flip) with volume confirmation
        conditions = (
            (dataframe['supertrend'] == 'up')
            & (dataframe['supertrend'].shift(1) == 'down')
            & (dataframe['volume'] > (dataframe['vol_sma_20'] * self.buy_volume_factor.value))
        )
        dataframe.loc[conditions, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # Exit on the reverse transition: bullish→bearish flip
        conditions = (
            (dataframe['supertrend'] == 'down')
            & (dataframe['supertrend'].shift(1) == 'up')
        )
        dataframe.loc[conditions, 'exit_long'] = 1
        return dataframe
