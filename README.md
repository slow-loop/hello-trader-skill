# hello-trader-skill

**English** | [繁體中文](README.zh-TW.md)

Local-first autonomous trading agent for Taiwan stocks, powered by Claude. No server, no database — all state lives as plain YAML and Markdown on disk.

## What it does

An AI agent runs a daily **Research + Trading** routine:

1. **Research** — fetches market data, reads news, updates the watchlist, generates per-symbol research docs
2. **Trading** — reviews open positions, evaluates watchlist entries, places or adjusts paper orders

Everything is stored in `data/account/` as human-readable files. The frontend viewer lets you browse the account state without touching the CLI.

## Three loosely-coupled pieces

| Folder | What it is |
|---|---|
| [`skills/tw-trader/`](skills/tw-trader) | The agent: `SKILL.md` prompts + Python CLI for paper trading, journals, watchlist, research docs |
| [`libs/market-core/`](libs/market-core) | Quotes, OHLCV bars, technical indicators, symbol snapshots |
| [`frontend-nano/`](frontend-nano) | Minimal Vite + React viewer for the local YAML/Markdown store |

[`web-reader`](https://github.com/w121211/web-reader) (async URL → clean text) is a separate dependency pulled from GitHub.

## Architecture

```
┌──────────────────┐  reads YAML  ┌──────────────────────┐
│  frontend-nano   │ ───────────► │  data/account/*      │
│  (Vite + React)  │              │  (runtime state)     │
└──────────────────┘              └──────────▲───────────┘
                                             │ writes
                                  ┌──────────┴──────────┐
                                  │  skills/tw-trader   │
                                  │  prompts + CLI      │
                                  └──────────┬──────────┘
                                             │ depends on
                                  ┌──────────┴──────────┐
                                  ▼                     ▼
                          ┌──────────────┐   ┌─────────────────────┐
                          │ market-core  │   │ web-reader (GitHub) │
                          │ quotes / TA  │   │ URL → clean text    │
                          └──────────────┘   └─────────────────────┘
```

Runtime state (account, journals, research docs) lives under `data/` — separated from skill code so the skill stays read-only and multiple skills can share one data directory.

## Prerequisites

- **Python 3.13** + [**uv**](https://docs.astral.sh/uv/)
- **Node 20+** (frontend only)
- **Claude Code** — the agent is driven by Claude via `SKILL.md`
- API keys: Fugle (Taiwan quotes), FinMind (historical data); others optional — see `.env.example`

## Setup

```bash
git clone https://github.com/<you>/hello-trader-skill.git
cd hello-trader-skill

cp .env.example .env          # fill in FUGLE_API_KEY, FINMIND_API_KEY at minimum
cd skills/tw-trader
uv sync                       # installs tw-trader + market-core + web-reader
```

Verify:

```bash
uv run tw-trader account      # should show empty paper account
uv run market overview        # should show market snapshot
```

## Running the daily routine

Open [`skills/tw-trader/prompts/SKILL.md`](skills/tw-trader/prompts/SKILL.md) in Claude Code and let the agent run. One session = one Research pass + one Trading pass.

For autonomous daily runs, use a foreground scheduler (reference: the `kol-watch` pattern from [hello-note](https://github.com/w121211/hello-note)) — no cron or launchd required.

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

```bash
cd frontend-nano
npm install && npm run dev    # http://localhost:5173
```

## Repo layout

```
.
├── skills/
│   └── tw-trader/        Trading agent (prompts + Python CLI)
├── libs/
│   └── market-core/      Market data + technical analysis
├── frontend-nano/        React viewer
├── data/                 Runtime state (gitignored)
├── .env.example
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
