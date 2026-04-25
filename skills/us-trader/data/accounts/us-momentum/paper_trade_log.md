# Paper Trade Log — mom_2f_2021-2024_r1

**Strategy:** `mom_2f_2021-2024_r1`
**Stage:** paper
**Start:** 2026-04-24
**Target end:** 2026-05-24 (30 calendar days, ~22 trading days)
**Decision point:** 2026-05-24 — promote to `live` iff exit criteria met.

---

## Purpose

Validate live behavior before committing real capital. Capture every signal
(entry_ok=True + regime=risk_on + composite_score ≥ 0.5) at close, simulate
entry/stop/target with real prices next day, and compare realized outcomes to
the 2024–2026 backtest (Sharpe 0.52, DD −25.5%, 97 trades).

**No real orders may be placed from this strategy until stage=live.**

---

## Daily workflow

Run once per trading day after the US close:

1. `us-trader regime` — capture SPX/QQQ/SOX/VIX/DJIA snapshot. Skip paper
   entries if `regime != risk_on`.
2. `us-trader signal --universe sp500_top100` — scan; log each row that
   meets entry criteria.
3. For every new paper entry: append a row to the **Trades** table below
   with entry price = next-day open, stop = close − 1.5·ATR14, target = 2R.
4. For every open paper trade: update status (hit_stop / hit_target / open),
   mark-to-market unrealized P&L.
5. `us-trader journal-add` — one-line note on regime + anything unusual.

---

## Exit criteria (to promote `paper` → `live`)

Promote **only if all four hold** on 2026-05-24:

| Criterion | Threshold | Actual |
|---|---|---|
| Trade count | ≥ 6 closed trades | — |
| Realized Sharpe | ≥ 0.3 | — |
| Realized max DD | ≥ −10% | — |
| Win rate × avg_R | consistent with backtest sign (positive) | — |

If any criterion fails → demote to `research`, write reflection, iterate.

---

## Trades

| # | Date open | Symbol | Entry | Stop | Target | Size% | Status | Close date | R realized | Note |
|---|-----------|--------|-------|------|--------|-------|--------|------------|------------|------|
|   |           |        |       |      |        |       |        |            |            |      |

---

## Daily regime log

| Date | Regime | SPX | VIX | Note |
|------|--------|-----|-----|------|
|      |        |     |     |      |

---

## End-of-period reflection

_Filled at 2026-05-24._
