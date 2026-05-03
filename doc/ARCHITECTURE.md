# Architecture (v2)

Locked decisions for the hello-trader-skill repo. Written 2026-04-19.

---

## Positioning

**Agent-powered trading toolkit for Claude Code.**
Local-first. Git-native. No backend required.

Compose libs + skills to build your own agent-driven trading workflow. Open source.

Not a broker SaaS. Not a cloud backend. A **local agent toolkit**.

---

## Principles

1. **Local YAML is the source of truth.** Not a backend, not a database.
2. **Git is the sync / history / audit layer.** No custom event store needed.
3. **Libs are stateless, CLIs are thin, agent is the orchestrator.**
4. **Backend is optional.** Single-user needs none. Teams can opt in.
5. **Every external data source is its own lib/CLI the agent calls directly** (symmetric with `web-reader`, which lives in [its own repo](https://github.com/w121211/web-reader)).

---

## Architecture

```
hello-trader-skill/
├── libs/                        pip-installable, reusable (in-tree)
│   └── market-core/             market data + TA + screener + paper-trading runtime
│                                (web-reader: pulled from github.com/w121211/web-reader)
│
├── skills/                      Claude Code skills
│   ├── tw-trader/               TW equity, local YAML state, main skill
│   ├── lana-copycat/            signal copying
│   └── …                        (user extends)
│
├── frontend-nano/               local web dashboard (read-only view of local state)
│
├── (optional) backend3/         team / multi-device sync — NOT required for MVP
└── backend2/                    DEPRECATED — to be dismantled
```

### Layering rule

```
agent → skill CLI → libs → (external APIs)
                 ↓
           local YAML (data/account/*)
                 ↓
           git (history, sync, audit)
                 ↓
     (optional) backend3 push for teams / frontend
```

CLIs never hide logic from the agent. If an agent could in principle call the lib directly, it should. CLIs are there for ergonomics and shell composability, not to gate access.

---

## Components

### `libs/market-core`

Single source for anything about the market. Lib + `market` CLI.

- **Fetch**: quote, bars, news (yfinance / fugle / TWSE / FinMind)
- **Compute**: technical indicators, triggers, analysis (pure functions)
- **Screener**: momentum + future strategies (from backend2/screener.py)
- **Portfolio runtime**: paper-trading engine as pure functions
  - `engine.py`: `execute_buy(state, order, quote) -> (new_state, trade)` — pure
  - `store.py`: YAML load/save — side effects isolated here
- **CLI entry point**: `market` (short, ergonomic)

Stateful pieces are confined to `store.py`. Engine is testable without I/O.

### `web-reader` (external)

URL in, clean text out. Agent calls directly. Lives in its own repo at
[github.com/w121211/web-reader](https://github.com/w121211/web-reader); skills
depend on it via `git+https://...@v0.1.0` in their `pyproject.toml`.

### `skills/tw-trader`

The main skill. Local YAML under `data/account/`. Reabsorbs the useful parts of the deprecated `tw-trader-cloud` (flat-flag CLI design, doc/journal structure).

- `tw watchlist-update / journal-add / buy / sell` — writes local YAML
- `tw sync push/pull` — *optional* backend3 mirror (future, not MVP)
- Prompts drive the agent; CLI is the write interface; `market` CLI is the read-the-world interface.

### `frontend-nano`

Local web dashboard. Reads local YAML via a **thin read-only FastAPI daemon** (~100 lines, lives in `skills/tw-trader/src/tw_trader/daemon.py`).

Not a full backend. Just a file-to-JSON adapter so the browser can render.

Rationale: keeps frontend web-native (no Tauri/Electron build chain) while avoiding backend2/3's scope creep.

### `backend3` (optional)

Positioned as **team edition / multi-device sync layer**. Not required for single-user open-source use.

- Kept in-tree as experimental
- README updated to clarify optional status
- No further feature development until team-edition need is real

### `backend2` (deprecated)

To be dismantled. Code moves:
- `screener.py`, `runtime.py` → `market-core`
- `market.py` → delete (market-core already has equivalents)
- `workspace.py`, `watchlist.py`, `models.py` (relevant parts) → `skills/tw-trader` local state modules
- Tests migrate alongside their code

After migration: delete `backend2/` entirely.

---

## Naming

| Thing | Name | Why |
|---|---|---|
| Library (pip) | `market-core` | Broad scope (fetch + TA + runtime), not just reading |
| CLI entry point | `market` | Short, mirrors `web-reader`'s ergonomic CLI |
| Main skill | `tw-trader` | Existing, fold cloud back into it |
| Frontend | `frontend-nano` | Existing |
| Sync backend (optional) | `backend3` | Existing, no rename |

---

## Migration plan

Two PRs, sequential:

**PR 1 — Bring libs in-tree** ✅ done 2026-04-20
- `market-core` and `web-reader` copied from `hello-note/libs/` into `libs/`
- Consumers (`backend2`, `scripts`, `skills/tw-trader`) updated to local paths
- Canonical home is now this repo; external copies become stale

**PR 1b — Extract `web-reader` to its own repo** ✅ done 2026-05-02
- `web-reader` moved out to [github.com/w121211/web-reader](https://github.com/w121211/web-reader)
- Consumers depend on it via `git+...@v0.1.0` in `pyproject.toml`
- `libs/web-reader/` removed from this repo

**PR 2 — Absorb screener + paper-trading into `market-core`**
- Move `backend2/src/backend2/screener.py` → `libs/market-core/src/market_core/screener/`
- Move paper-trading parts of `backend2/src/backend2/runtime.py` → `libs/market-core/src/market_core/portfolio/`
- Move `ScreenerResult` / `ScreenerResponse` models to `market_core.models`
- Add `market` CLI entry point (quote / analysis / screener / news)
- Non-breaking: `backend2/screener.py` becomes re-export shim

**PR 3 — Dismantle backend2, fold `tw-trader-cloud` into `tw-trader`**
- Port tw-trader-cloud's flat-flag CLI design into tw-trader
- Delete `tw-trader-cloud/`
- Delete `backend2/`
- Update prompts (`RESEARCH.md`, `TRADING.md`) to use `market` CLI + local files
- Update `frontend-nano` to read from the new daemon

**Not in scope**: backend3 changes, team edition, sync push/pull.

---

## Non-goals

- Multi-agent coordination
- Real-money broker integration
- Cloud-hosted state
- Replacing Claude Code as the agent harness

If any of these become real requirements, revisit this doc.
