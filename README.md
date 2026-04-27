# nano-trader-skills

Local-first toolkit for running an autonomous Taiwan-stock trading agent with Claude. No server, no database — everything is plain YAML and Markdown on disk.

Three loosely-coupled pieces:

| Folder | What it is |
|---|---|
| [`skills/tw-trader/`](skills/tw-trader) | Claude skill: SKILL.md prompts + Python CLI for paper trading, journals, watchlist, research docs |
| [`libs/market-core/`](libs/market-core) | Quotes, OHLCV bars, technical indicators, symbol snapshots ([README](libs/market-core/README.md)) |
| [`libs/web-reader/`](libs/web-reader) | Async URL → clean text (web/RSS/Reddit/YouTube/PTT/GNews/email + optional MCP) ([README](libs/web-reader/README.md)) |
| [`frontend-nano/`](frontend-nano) | Minimal Vite + React viewer for the trader's local YAML/Markdown store |

## Architecture

```
┌──────────────────┐  reads YAML  ┌──────────────────────┐
│  frontend-nano   │ ───────────► │  skills/tw-trader    │
│  (Vite + React)  │              │  data/account/*      │
└──────────────────┘              └──────────┬───────────┘
                                             │ depends on
                                  ┌──────────┴──────────┐
                                  ▼                     ▼
                          ┌──────────────┐      ┌──────────────┐
                          │ market-core  │      │ web-reader   │
                          │ quotes / TA  │      │ URL → text   │
                          └──────────────┘      └──────────────┘
```

## Quickstart

Requires **Python 3.13**, [**uv**](https://docs.astral.sh/uv/), and **Node 20+**.

```bash
git clone https://github.com/<you>/nano-trader-skills.git
cd nano-trader-skills/skills/tw-trader

uv sync                         # installs tw-trader + market-core + web-reader
cp .env.example .env            # add FUGLE_API_KEY, FINMIND_API_KEY

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
uv run tw-trader publish                       # render daily poster.png
```

State lives in `data/account/`:

```
data/account/
├── state/         # account, positions, orders, trades
├── journals/      # daily YAML journals
├── research/      # per-symbol Markdown research docs
├── screener/      # daily screener snapshots
├── watchlist.yaml
└── lessons.md
```

Templates for new research docs / trading cards live under `data/account/*/template/`.

## Standalone use

`market-core` and `web-reader` are general-purpose and have no Taiwan-specific assumptions in their core. Use them on their own:

```bash
# Read any URL as clean text
uv run --with web-reader web-reader "https://example.com"

# In Python
python -c "from market_core import analyze_symbol, MarketRuntimeConfig, MarketConfig; \
  print(analyze_symbol('AAPL', MarketRuntimeConfig(market=MarketConfig(profile='us_equity'))).quote.price)"
```

See each lib's README for details.

## Repo layout

```
.
├── skills/tw-trader/      Trading skill (prompts + Python CLI)
├── libs/
│   ├── market-core/       Market data + technical analysis
│   └── web-reader/        Async URL reader
├── frontend-nano/         React viewer
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
