# HEARTBEAT.md

## Cadence-Based Checks

- Pre-market: once per trading day, 08:00-08:59
- Intraday: every 1h, 09:00-13:30
- Post-market: once per trading day, 13:30-16:00

## TW Trade Check (pre-market, intraday, psot-market)

1. Run `/Users/cw/Documents/GitHub/hello-invest/apps/skill-tw-trader/TRADING.md` flow
2. Run `/Users/cw/Documents/GitHub/hello-invest/apps/skill-tw-trader/SOCIAL.md` flow
3. If nothing actionable → return `HEARTBEAT_OK`

Non-trading day: skip trading, social still runs.