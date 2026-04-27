# momentum_v4_atr_stop Notes — 2026-04-25

## Hypothesis
Implement ATR-based stop loss in strategy_bt.py to reduce IS MaxDD (-55.6% in v3).
The config already defines `initial_stop_formula: "close - 1.5 * atr_14"` but
the engine was ignoring it.

## What we tested
Three stop variants in strategy_bt.py:
1. Fixed entry-price ATR stop (sl_stop=1.5*atr/close, sl_trail=False)
2. Trailing ATR stop (sl_stop=1.5*atr/close, sl_trail=True)

## Results

| Version | Test | Sharpe | MaxDD | Trades | Notes |
|---------|------|--------|-------|--------|-------|
| v3 (no stop) | IS megacap_tech 2020-24 | 0.67 | -55.6% | 39 | baseline |
| v3 (no stop) | OOS sp100 2024-26 | 0.495 | -24.6% | 169 | baseline |
| v4 fixed stop | IS megacap_tech 2020-24 | 0.61 | -39.4% | 100 | MaxDD improved |
| v4 fixed stop | OOS sp100 2024-26 | -0.016 | -19.1% | 334 | Sharpe collapsed |
| v4 trailing stop | IS megacap_tech 2020-24 | 0.39 | -26.5% | 367 | Whipsaw |
| v4 trailing stop | OOS sp100 2024-26 | -0.046 | -14.6% | 639 | Extreme whipsaw |

## Finding: stop-loss is incompatible with signal-based exits

Price-based ATR stops cause:
1. Frequent stop-outs on normal pullbacks (tight 1.5x ATR = 2-4% stop on large-cap)
2. Re-entry after recovery → exit-reentry cycles → high friction (fees + slippage)
3. OOS Sharpe collapses even as MaxDD improves

The fundamental conflict: the current exit logic (composite_score < 0) waits for
the SIGNAL to weaken, not price to drop. Adding a price stop creates two competing
exit mechanisms that both fire independently. In volatile but trending markets,
the price stop fires on pullbacks before the signal weakens → exits winners early.

## Design conclusion

Per BACKTEST.md design philosophy: regime-based drawdown control is the agent's
responsibility, not encoded in the backtest. The IS MaxDD of -55.6% represents
the "no regime filter" upper bound. Real agent performance will be better because:
- Agent avoids long entries during risk-off (VIX spike, SPX below SMA)
- Agent manages ATR stops per-position as trailing stops (not implemented in BT)

**Do NOT add price stops to strategy_bt.py.** The signal-only exit is the correct
design for measuring factor alpha. Reverted to original exit logic.

## v4 experiment dir purpose

Kept as a research artifact documenting this stop-loss experiment.
DO NOT PROMOTE — this was an infrastructure test, not a strategy improvement.
