# hello-trader-skill

**English** | [繁體中文](README.zh-TW.md)

A monorepo of local-first, Claude-driven trading and research agents. No
server, no database by default — most skills keep all state as plain YAML and
Markdown on disk, and are driven by a Claude Code `SKILL.md` prompt.

## 👉 Start here: polymarket-scan

New to this repo? [`skills/polymarket-scan/`](skills/polymarket-scan) is the
easiest skill to try standalone — a read-only scanner that finds mispriced
Polymarket moneylines, no API key required. See its
[README](skills/polymarket-scan/README.md) (also in
[繁體中文](skills/polymarket-scan/README.zh-TW.md)) for setup and CLI usage.

## Skills in this repo

| Skill | What it does | Status |
|---|---|---|
| [`polymarket-scan`](skills/polymarket-scan) | Read-only scanner for mispriced Polymarket single-game moneylines | Active, no API key needed |
| [`tw-trader`](skills/tw-trader) | Taiwan stock paper-trading agent — daily Research + Trading routine | Primary skill |
| [`tw-trader-cloud`](skills/tw-trader-cloud) | Same as `tw-trader`, but state syncs to a cloud backend instead of local files | Experimental |
| [`us-trader`](skills/us-trader) | US equity trading agent, trades signals produced by `strategy-lab` | Active |
| [`strategy-lab`](skills/strategy-lab) | Offline factor research, backtesting, and strategy promotion for `us-trader` | Active |
| [`lana-copycat`](skills/lana-copycat) | Crypto futures copy-trading agent (Binance Futures testnet) | Testnet only |
| [`wallstreet-research`](skills/wallstreet-research) | Deep-dive research report generator for a single stock or theme | Active |

Each skill has its own README with setup and CLI details. Skills share two
common libraries:

| Folder | What it is |
|---|---|
| [`libs/market-core/`](libs/market-core) | Quotes, OHLCV bars, technical indicators, symbol snapshots |
| [`frontend-nano/`](frontend-nano) | Minimal Vite + React viewer for `tw-trader`'s local YAML/Markdown store |

[`hello-web-reader`](https://github.com/w121211/hello-web-reader) (async URL → clean text) is a separate
dependency pulled from GitHub, used by several skills (`tw-trader`, `wallstreet-research`).

## Architecture (tw-trader)

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
                          │ market-core  │   │ hello-web-reader       │
                          │ quotes / TA  │   │ URL → clean text    │
                          └──────────────┘   └─────────────────────┘
```

Other skills follow the same broad pattern (Claude-driven via `SKILL.md`,
runtime state separate from skill code) but each keeps its own `data/`
directory — see each skill's README for its specific layout.

## Prerequisites

- **Python 3.13** + [**uv**](https://docs.astral.sh/uv/)
- **Node 20+** (only needed for `frontend-nano`)
- **Claude Code** — most agents are driven by Claude via a `SKILL.md` prompt
- API keys vary by skill — see `.env.example` at repo root and each skill's README
  (`polymarket-scan` needs none; `tw-trader` needs Fugle + FinMind; `lana-copycat`
  needs Binance Futures testnet keys)

## Setup

```bash
git clone https://github.com/<you>/hello-trader-skill.git
cd hello-trader-skill
cp .env.example .env    # fill in keys for the skill(s) you plan to run

cd skills/<skill-name>  # e.g. skills/tw-trader, skills/polymarket-scan
uv sync                 # skills with a pyproject.toml; polymarket-scan is stdlib-only
```

Then open that skill's `prompts/SKILL.md` (or `SKILL.md`) in Claude Code and let
the agent run, or invoke its CLI/scripts directly per its README.

## Repo layout

```
.
├── skills/
│   ├── polymarket-scan/   Polymarket moneyline scanner (read-only, stdlib)
│   ├── tw-trader/         Taiwan stock paper-trading agent (prompts + Python CLI)
│   ├── tw-trader-cloud/   Cloud-backend variant of tw-trader
│   ├── us-trader/         US equity trading agent
│   ├── strategy-lab/      Offline factor research + backtest + promote
│   ├── lana-copycat/      Crypto futures copy-trading agent (testnet)
│   └── wallstreet-research/  Single-stock/theme deep-dive research
├── libs/
│   └── market-core/       Market data + technical analysis (shared)
├── frontend-nano/         React viewer (tw-trader's data store)
├── data/                  Runtime state (gitignored)
├── .env.example
└── README.md
```

## License

MIT — see [LICENSE](LICENSE).
