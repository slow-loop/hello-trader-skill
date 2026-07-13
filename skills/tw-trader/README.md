# tw-trader

Taiwan stock paper-trading agent. Runs a daily **Research + Trading** routine and
keeps all state as YAML/Markdown on disk — no server, no database.

## What it does

1. **Research** — fetches market data, reads news, updates the watchlist, generates per-symbol research docs
2. **Trading** — reviews open positions, evaluates watchlist entries, places or adjusts paper orders

Depends on [`libs/market-core`](../../libs/market-core) (quotes, OHLCV, indicators) and
[`hello-web-reader`](https://github.com/w121211/hello-web-reader) (URL → clean text, pulled from GitHub).

## Prerequisites

- **Python 3.13** + [**uv**](https://docs.astral.sh/uv/)
- **Claude Code** — the agent is driven by Claude via `prompts/SKILL.md`
- API keys: Fugle (Taiwan quotes), FinMind (historical data) — see [`.env.example`](../../.env.example) at repo root

## Setup

```bash
cp ../../.env.example ../../.env    # fill in FUGLE_API_KEY, FINMIND_API_KEY at minimum
cd skills/tw-trader
uv sync                             # installs tw-trader + market-core + hello-web-reader
```

Verify:

```bash
uv run tw-trader account      # should show empty paper account
uv run market overview        # should show market snapshot
```

## Running the daily routine

Open [`prompts/SKILL.md`](prompts/SKILL.md) in Claude Code and let the agent run.
One session = one Research pass + one Trading pass.

For autonomous daily runs, use a foreground scheduler (reference: the `kol-watch` pattern
from [hello-note](https://github.com/w121211/hello-note)) — no cron or launchd required.

## CLI reference

```bash
# Account
uv run tw-trader account                        # portfolio + cash summary
uv run tw-trader journal                        # today's journal

# Orders (paper trading only)
uv run tw-trader buy  2330 1000 --limit 600     # limit buy
uv run tw-trader sell 2330 500                  # market sell
uv run tw-trader sweep                          # match pending orders against latest quotes

# Research
uv run tw-trader watchlist                      # show watchlist
uv run tw-trader screener-snapshot              # run screener, save snapshot

# Market data (market-core)
uv run market overview                          # market regime snapshot
uv run market quote 2330                        # single symbol quote
uv run market chart 2330 --period 3mo           # OHLCV chart
```

Override the data root:

```bash
TW_TRADER_DATA_ROOT=/your/path uv run tw-trader account
```

## Data layout

```
data/account/
├── state/          # account, positions, orders, trades (YAML)
├── journals/       # daily journals (YAML)
├── research/       # per-symbol Markdown research docs
├── screener/       # daily screener snapshots
├── watchlist.yaml
└── strategy.md
```

Templates for new documents live under `data/account/*/template/`.

## Frontend viewer

A minimal Vite + React viewer for this skill's `data/account/` store lives at
[`frontend-nano/`](../../frontend-nano):

```bash
cd ../../frontend-nano
npm install && npm run dev    # http://localhost:5173
```
