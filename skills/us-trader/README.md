# us-trader

US equity trading skill. Agent-driven, consumes factor signals produced by
`market-core` (factors + strategy) + strategy YAML promoted from `strategy-lab`.

Prompts:
- `prompts/SKILL.md` — entry
- `prompts/RESEARCH_US.md` — daily research flow (regime + signals + watchlist)
- `prompts/TRADING_US.md` — trading flow (positions + new entries + journal)

CLI:
```bash
uv run us-trader signal            # top signals from ACTIVE strategy
uv run us-trader account           # current account state
uv run us-trader watchlist         # watchlist + latest quote
uv run us-trader buy AAPL --qty 10 --price 180 --stop-loss 170 --take-profit 200 --strategy momentum --reason "..."
uv run us-trader sell AAPL --qty 10 --price 190 --reason "..."
uv run us-trader journal-add --file tmp/journal_entry.yaml
```

Account data lives under `data/accounts/{account_name}/`. First account:
`us-momentum`.
