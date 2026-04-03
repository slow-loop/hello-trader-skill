# Polymarket Paper Trader

Minimal MVP skill app for simulated Polymarket trading.

## What it does

- fetches current live Polymarket markets
- scans Polymarket events directly from the Gamma API
- keeps only markets that pass the basic filters
- returns event payloads and market snapshots for agent judgment
- records at most one paper trade per decision
- stores state in `data/ledger.json`
- stores one Markdown journal file per full trade/reflect cycle in `data/journals/`
- stores separate strategy-development state and journals in `data/strategy_dev/`

## CLI

```bash
uv run python -m skill_poly_trader_v2 init
uv run python -m skill_poly_trader_v2 sync-tags
uv run python -m skill_poly_trader_v2 markets
uv run python -m skill_poly_trader_v2 markets --profile geo --limit 60
uv run python -m skill_poly_trader_v2 markets --profile sports --limit 50
uv run python -m skill_poly_trader_v2 market --slug <slug>
uv run python -m skill_poly_trader_v2 buy --slug <slug> --outcome-index 0 --size 25 --probability 0.42 --reason "..."
uv run python -m skill_poly_trader_v2 sell --slug <slug>
uv run python -m skill_poly_trader_v2 status
```

## Notes

- current markets only
- market scan comes from the Polymarket API; the manual prompt workflow may use external research to form a thesis
- no backtesting
- no real-money trading
- default workflow is `sync-tags` then `markets --profile <name>` then `market` then `buy`
- production trade cycles should run `geo` first and `sports` second on every wake-up
- `geo` and `sports` are independent strategy passes; a trade in one does not justify skipping the other
- current production profiles are `geo` and `sports`
- `macro` is currently commented out of the production trade loop
- `ai` is disabled in the production trade loop for now
- `markets` is an initial screening step for the agent and returns a larger working set of binary markets
- the number of researched candidates should be criteria-driven, not fixed by quota
- `markets --profile <name>` is profile-first; each profile is defined as native `/events` query params plus minimal local post-processing
- `geo` now preserves three separate buckets in one scan: `endDate`, `updatedAt`, and `createdAt`, with up to `20` unique markets from each bucket
- open positions are excluded from `markets` output before the agent sees the candidate set
- the agent should judge from the market payload plus current event context
- for any market that is seriously evaluated, the agent should do WebSearch before buying
- trade execution and strategy development are now separate loops:
  - `prompts/TRADE.md` for paper trading cycles
  - `prompts/STRATEGY_DEV.md` for continuous profile / strategy / prompt iteration
- Anthropic-related code paths are still present in the repo but are not the primary documented workflow
