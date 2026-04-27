# macd_crossover IC Notes — 2026-04-25

## Hypothesis
MACD histogram crosses zero from below → trend initiation signal.
Should fire earlier than trend_strength (which requires both MAs broken + ADX).

## Results
IC1=+0.013, IC5=-0.005, IC20=-0.006, N=18,786.
40% of entries dropped in binning (sparse signal).

## Verdict: DROP

IC5 and IC20 are negative — the factor is slightly mean-reverting at multi-day horizons.
The MACD crossover in a large-cap universe tends to resolve back to the mean, not
continue. It's not a trend filter at this time scale.

The scoring logic also had a dual-branch design (fresh cross + ongoing) that may
have introduced noise. Even with simpler scoring, the underlying phenomenon likely
doesn't have edge in top-100 large-cap.

## Removed from catalog.py

## Pivot decision

After two failed new factor attempts (momentum_6m, macd_crossover), the bottleneck
is NOT factor alpha — it's drawdown control. The strategy's IS MaxDD=-55.6% on
megacap_tech is a risk management problem (exit fires too late).

Next engineering task: implement ATR-based stop loss in strategy_bt.py.
The config already defines `initial_stop_formula: "close - 1.5 * atr_14"` but
the backtest engine ignores it. Implementing it would reduce the IS MaxDD and
likely improve the OOS Sharpe by cutting losses earlier in bear markets.
