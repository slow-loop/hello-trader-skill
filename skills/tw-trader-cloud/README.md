# tw-trader-cloud

Cloud-backend variant of [`tw-trader`](../tw-trader): the same daily
**Research + Trading** routine for Taiwan stocks, but state (watchlist,
journals, docs, operations, trades) is stored in a backend service
(`backend3`) instead of local YAML/Markdown files. Structured data is always
written through the `tw` CLI — the agent never POSTs to the backend directly
and never hand-edits the cached YAML files.

## How it differs from tw-trader

- **Storage**: backend-synced, not local-only. Local files under `data/` are a
  read-only projection of backend state (except `docs`, which the agent writes
  locally then pushes).
- **Memory model**: short-term memory = `journals` (time-indexed, thin,
  inline body); long-term knowledge = `docs` (path-based, versioned).
- Everything else — the Research → Trading flow, the strategy logic — lives in
  prompts, same as `tw-trader`.

## CLI

```bash
# One-time setup
uv run tw init --name <agent-name>
uv run tw me

# Watchlist / journals (read = GET + refresh local cache)
uv run tw watchlist
uv run tw watchlist-update 2330 --thesis "..." --status active --trigger-price 950 --stop 895 --target 1050
uv run tw journal --from-date 2026-04-17
uv run tw journal-add --date 2026-04-19 --entry-type research --body "..."

# Operations / trades
uv run tw buy 2330 --qty 100 --price 950 --stop 895 --target 1050 --reason "..."
uv run tw sell 2330 --qty 100 --price 980 --reason "..." --pnl 3000
uv run tw propose --symbol 2330 --side buy --qty 100 --price 950 --reason "..."
uv run tw fill 12 --fill-price 950
uv run tw reject 12 --reason "..."
uv run tw cancel 12 --reason "..."

# Views
uv run tw account
uv run tw events --limit 20

# Docs: agent writes the file, then pushes it
uv run tw docs-add data/account/lessons.md
uv run tw docs-add data/account/research/2026-04-19-tw-2330.md
uv run tw research --from-date 2026-04-19
uv run tw lessons
```

## Agent instructions

The wake-up sequence, storage rules, and CLI conventions are in
[`prompts/SKILL.md`](prompts/SKILL.md) (Traditional Chinese); the Research and
Trading flows themselves are in `prompts/RESEARCH.md` and `prompts/TRADING.md`.

## Part of hello-trader-skill

This skill lives inside the [hello-trader-skill](../../README.md) monorepo —
see the root README for the full list of trading/research skills.
