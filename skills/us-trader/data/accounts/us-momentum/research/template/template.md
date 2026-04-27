# Stock Research Template

**date**: YYYY-MM-DD
**symbol**: TICKER
**basis_price**: 0.00
**entry_mode**: breakout | pullback | catalyst
**wave**: photonics | power_cooling | analog_semi | general

---

## What the Market Is Trading

- **Narrative**: (1 sentence — what theme is driving this stock right now)
- **Why this name**: (why this ticker vs. peers in the same theme)

## Fundamentals

- **Business / supply chain position**: (what they sell, where in the value chain)
- **Revenue / earnings momentum**: (recent quarters, guidance trend)
- **Key customers / capacity / catalyst**: (who buys from them, any announced deals or capacity expansion)
- **Earnings date**: YYYY-MM-DD (⚠️ flag if within 3 days)

## Technicals

| Metric | Value | Signal |
|--------|-------|--------|
| Close | 0.00 | |
| SMA_20 | 0.00 | above / below |
| SMA_50 | 0.00 | above / below |
| dist_sma20_pct | 0.0% | |
| ATR_14 | 0.00 | |
| composite_score | 0.000 | |
| trend_strength | 0.000 | |
| rsi_overbought | 0.000 | |
| firing_factors | [] | |

**Technical summary**: (one paragraph — trend structure, extension risk, entry quality)

## Institutional / Flow

- **Short interest**: (% float short, days to cover if available)
- **Institutional ownership**: (% held, recent 13F changes if notable)
- **Options flow**: (any unusual call/put activity? skew?)
- **Flow conclusion**: (is smart money accumulating or distributing?)

## Peer Comparison

Run: `uv run us-trader signal --universe "SYM,PEER1,PEER2,PEER3" --top 10`

| Symbol | Theme position | Composite | SMA20 dist | Strength | Conclusion |
|--------|---------------|-----------|------------|----------|------------|
| TARGET | | | | | |
| PEER1 | | | | | |
| PEER2 | | | | | |

**Best name in group**: (is target the strongest, or is a peer a better entry?)

## Catalyst Calendar

| Date | Event | Importance |
|------|-------|------------|
| YYYY-MM-DD | Earnings | HIGH |
| YYYY-MM-DD | FOMC / CPI / NFP | MEDIUM |
| YYYY-MM-DD | Sector event / conf | LOW |

## Thesis

**Core thesis**: (1-2 sentences — why this works from here)

**Entry mode**: breakout / pullback / catalyst
**A point** (entry sweet spot): price level or condition
**B point** (validation): what confirms the thesis is working

**Thesis valid if**:
-

**Thesis invalid if** (invalidation):
-

## Trade Plan

- **Entry**: price zone or trigger condition
- **Stop**: `close - 1.5 × ATR_14` = $0.00
- **Target 1R**: $0.00
- **Target 2R**: $0.00 (primary exit)
- **Sizing**: qty = floor($1,000 / risk_per_share) = N shares ($0 position, 0% of account)
- **PDT check**: N/A (account > $25k) | flag if < $25k

## Skip Rationale (if not entering)

- (why passing this setup despite entry_ok=true)
