# lana-copycat

Crypto futures trading agent. Strategy copied from
[@lanaaielsa](https://x.com/lanaaielsa): long-only, one position at a time,
fixed-amount stop loss, AI-judged partial take-profit. Currently runs on
**Binance Futures testnet only** — no real funds are at risk.

## Two independent pipelines

| | Square pipeline | Cattrade pipeline |
|---|---|---|
| Signal | Retail chatter (Binance Square) + open-interest divergence + gainers | 11 quant leaderboards from a shared Google Sheet |
| Noise | High — needs judgment to filter junk/hype | Low — already scored |
| Agent's role | High — decide what's real vs. noise | None in the loop — pure code |
| Runs as | Agent wakes up and scans manually | `cron` every 5 min, no agent involved |

The two pipelines don't filter each other; a symbol hit by both has the
strongest signal, but either alone is enough to act on.

## CLI

**Square pipeline (agent-driven / manual)**
```bash
lana scan                  # combined Square + OI + gainers signal (60min cache)
lana square / lana signals / lana trending   # sub-signal debugging
lana trade <SYM>           # manually open LONG with 200 USDT stop
lana close <SYM> --pct N   # manually close N% of a position
```

**Cattrade pipeline (cron, pure code)**
```bash
lana cattrade scan     # view candidates (read-only)
lana cattrade run      # one tick — used by cron
lana cattrade journal  # view entry/exit history
```

**Shared**
```bash
lana positions   # current open positions
```

## Cron setup

```cron
*/5 * * * * cd /path/to/lana-copycat && uv run lana cattrade run --no-dry-run >> logs/cron.log 2>&1
```

`run` and `daemon` default to `--dry-run=True` (logs decisions, places no orders).
Pass `--no-dry-run` explicitly to trade for real (testnet, per current `config.yaml`).

## Config

`config.yaml` holds all knobs (risk limits, scoring weights, cattrade thresholds).
Secrets (Binance testnet API keys) go in `.env` — see `.env.example`.

To go live eventually: flip `binance.testnet: false`, swap in production API
keys, and start with a small `position_size_pct`.

## Design rationale

Full derivation of the strategy, the Pattern A–E classification used by the
cattrade pipeline, why conviction is computed as `current_score / entry_score`,
and known limitations/TODOs live in [`docs/STRATEGY.md`](docs/STRATEGY.md)
(Traditional Chinese).

## Agent instructions

The Claude agent's operating instructions are in
[`prompts/SKILL.md`](prompts/SKILL.md) (Traditional Chinese).

## Part of hello-trader-skill

This skill lives inside the [hello-trader-skill](../../README.md) monorepo —
see the root README for the full list of trading/research skills.
