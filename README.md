# nano-trader-skills

**English** | [繁體中文](README.zh-TW.md)

Local-first toolkit for running an autonomous Taiwan-stock trading agent with Claude. No server, no database — everything is plain YAML and Markdown on disk.

Three loosely-coupled pieces:

| Folder | What it is |
|---|---|
| [`skills/tw-trader/`](skills/tw-trader) | Claude skill: SKILL.md prompts + Python CLI for paper trading, journals, watchlist, research docs |
| [`libs/market-core/`](libs/market-core) | Quotes, OHLCV bars, technical indicators, symbol snapshots ([README](libs/market-core/README.md)) |
| [`frontend-nano/`](frontend-nano) | Minimal Vite + React viewer for the trader's local YAML/Markdown store |

`web-reader` (async URL → clean text, used by the skills) lives in its own repo: [w121211/web-reader](https://github.com/w121211/web-reader).

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
                          ┌──────────────┐      ┌──────────────────────┐
                          │ market-core  │      │ web-reader (github)  │
                          │ quotes / TA  │      │ URL → text           │
                          └──────────────┘      └──────────────────────┘
```

Runtime state (account, journals, research) lives at repo-root [`data/`](data) — separated from the skill code so the skill stays read-only and one repo can host multiple skills writing into the same data dir.

## Quickstart

Requires **Python 3.13**, [**uv**](https://docs.astral.sh/uv/), and **Node 20+**.

```bash
git clone https://github.com/<you>/nano-trader-skills.git
cd nano-trader-skills

cp .env.example .env            # add FUGLE_API_KEY, FINMIND_API_KEY, ...
cd skills/tw-trader && uv sync  # installs tw-trader + market-core (web-reader pulled from GitHub)

uv run tw-trader account        # show paper account
uv run tw-trader watchlist      # show watchlist
```

Frontend viewer:

```bash
cd frontend-nano
npm install && npm run dev      # http://localhost:5173
```

Drive the agent from Claude Code by pointing it at [`skills/tw-trader/prompts/SKILL.md`](skills/tw-trader/prompts/SKILL.md). Each turn runs one Research pass and one Trading pass.

## tw-trader CLI

```bash
uv run tw-trader account                       # portfolio status
uv run tw-trader buy 2330 1000 --limit 600     # paper buy
uv run tw-trader sell 2330 1000                # paper sell (market)
uv run tw-trader sweep                         # match pending orders to quotes
uv run tw-trader journal                       # today's journal
uv run tw-trader doc-add data/account/research/2026-04-26-tw-2330.md
```

State lives in `data/account/` at repo root:

```
data/account/
├── state/         # account, positions, orders, trades
├── journals/      # daily YAML journals
├── research/      # per-symbol Markdown research docs
├── screener/      # daily screener snapshots
├── watchlist.yaml
└── strategy.md
```

Templates for new research docs / trading cards live under `data/account/*/template/`. Override the data location with `TW_TRADER_DATA_ROOT=/path/to/dir`.

## Standalone use

`market-core` has no Taiwan-specific assumptions in its core; use it on its own:

```bash
python -c "from market_core import analyze_symbol, MarketRuntimeConfig, MarketConfig; \
  print(analyze_symbol('AAPL', MarketRuntimeConfig(market=MarketConfig(profile='us_equity'))).quote.price)"
```

`web-reader` is its own repo — see [github.com/w121211/web-reader](https://github.com/w121211/web-reader).

## Repo layout

```
.
├── skills/tw-trader/      Trading skill (prompts + Python CLI)
├── libs/
│   └── market-core/       Market data + technical analysis
├── frontend-nano/         React viewer
├── data/                  Runtime state (account, journals, posts)
├── .env.example           Single shared env file for the whole monorepo
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
