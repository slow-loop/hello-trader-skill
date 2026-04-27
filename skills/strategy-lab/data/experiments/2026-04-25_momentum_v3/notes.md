# v3 Research Notes — 2026-04-25

## Change from v2

Bug fix: `rsi_overbought` had `min_score: 0.3` in v2. The factor's score is always
in `[-0.5, 0]`, so the gate `score >= 0.3` was never satisfied → factor was a dead
weight. Fixed by removing `min_score` and lowering weight to 0.8. Now it correctly
drags composite downward when RSI > 75 (filtering over-extended entries and
triggering earlier exits when combined with weakening trend).

## Results

| Test | Universe | Period | Sharpe | MaxDD | Trades |
|------|----------|--------|--------|-------|--------|
| IS | megacap_tech (15) | 2020-2024 | **0.67** | -55.6% | 39 |
| OOS | sp500_top100 (98) | 2024-06–2026-04 | **0.495** | -24.6% | 169 |

v2 OOS for comparison: Sharpe=0.524, MaxDD=25.5%, 97 trades.

## Key findings

1. **Bug fix is neutral on OOS Sharpe** (0.495 vs 0.524). The rsi_overbought drag
   triggers more exits when RSI is high AND trend weakens (169 trades vs 97), but
   Sharpe doesn't improve — the earlier exits re-enter with additional friction.

2. **IS MaxDD -55.6% is alarming.** megacap_tech 2022 bear caused deep drawdowns
   because the exit condition (`composite < 0`) requires BOTH MAs broken AND ADX
   trending — a very lagging signal. A stock can fall 40%+ before this fires.
   The risk section mentions ATR stops but the backtest engine doesn't implement them.

3. **OOS MaxDD is better** (-24.6% on sp100 vs -55.6% on megacap_tech IS) because
   diversification across 98 names smooths individual blow-ups.

4. **Trade count inflation**: rsi_overbought now triggers composite < 0 exits on
   overbought dips, causing exit-reentry cycles. This isn't always bad (prevents
   holding through full pullbacks) but adds friction.

## Root cause of weak Sharpe

The strategy has only one real alpha factor (`trend_strength`, IC20=0.041). That IC
is marginal — we're just riding buy-and-hold beta with a trend filter. To improve:

a) **Better exit**: implement ATR-based trailing stop in the backtest engine
   (config already defines `initial_stop_formula`). This would cut the IS MaxDD
   dramatically and potentially improve risk-adjusted returns.

b) **New alpha factor**: need a factor with IC20 > 0.05 on sp500 with large sample
   (n > 2000). Candidates to explore:
   - RSI momentum-continuation (RSI crossing 55 from below, not overbought screen)
   - PEAD (post-earnings announcement drift): earnings beat + gap + volume
   - Relative strength (52W return vs index, not absolute price level)

## Next steps

- PRIORITY: explore `rs_vs_spy` factor (relative strength: stock 20D return minus
  SPY 20D return > 0, scaled) — this is a pure momentum alpha not correlated with
  the existing trend filter.
- Also: check if ATR-stop implementation in strategy_bt makes the IS MaxDD < 25%.
  If yes, that alone may be worth a v4 config without new factors.
- Do NOT promote v3: Sharpe < 1.0 on OOS, MaxDD > 20%. Still in research phase.
