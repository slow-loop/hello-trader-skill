# momentum_6m IC Notes — 2026-04-25

## Hypothesis

Stock with strong 5-month return (ret_120d - ret_20d > 8%, Jegadeesh-Titman) →
outperforms next 20 days. Excludes most-recent 1M to avoid short-term reversal.

## Results

| Horizon | IC | IC std | t-stat (correct) |
|---------|-----|--------|-----------------|
| 1D | +0.015 | 0.277 | ~1.87 |
| 5D | +0.019 | 0.265 | ~2.48 |
| 20D | +0.019 | 0.235 | ~2.80 |

N=117,709 (98 symbols × ~1200 days). Correct t-stat uses T=~1200 independent
cross-sections, not 117k total observations.

## Quantile returns (20D)

Non-monotonic: Q5=+40.6 bps, Q4=+4.5 bps, Q3=-39.4 bps, Q2=-13.4 bps, Q1=+7.3 bps.
Q1 and Q2 diverge from expected (Q1 should underperform). The U-shape indicates
the factor doesn't have a reliable linear relationship — it only separates the
very top quintile, which is noisy.

## Verdict: DROP

- IC20=0.019 < 0.03 threshold
- Non-monotonic quantile returns → no clean linear edge
- 5D IC narrowly passes t>2.0 but 20D doesn't with correct t-stat formula
- Removed from catalog.py

## Why it failed in sp500_top100

All 100 stocks are large-cap leaders. The within-universe spread on 6M momentum is
compressed — the range is narrower than on a full sp500 or small/mid-cap universe.
The Jegadeesh-Titman effect is strongest for the top-vs-bottom momentum spread
across a wide universe. In a top-100 pre-filtered universe the alpha is diluted.

## Next steps

Better candidate: a factor that works WITHIN a leadership universe. Options:
1. `macd_crossover`: MACD histogram turning positive (trend initiation signal).
   Uses existing macd/macd_signal features. Entry at trend start vs current
   trend_strength (which enters after trend is established).
2. `dist_sma200_acceleration`: d/dt(dist_sma200_pct) > 0 → stocks pulling away
   from their 200MA (institutional accumulation in progress).
3. Better path: fix the BACKTEST exit logic (ATR stops) — MaxDD is the primary
   bottleneck, not alpha discovery.
