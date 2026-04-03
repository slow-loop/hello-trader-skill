---
name: polymarket-paper-trader
description: Run a minimal Polymarket paper-trading cycle against current live markets. Use this skill whenever the user wants Polymarket mock trading, simulated bets, shadow trading, paper trades, or a lean prediction workflow without risking real money. This skill fetches current Polymarket events, keeps only markets that pass basic filters, updates a paper ledger, and reports what it would have done.
---

# Polymarket Paper Trader

Run a single MVP paper-trading cycle on current Polymarket markets.

This skill is intentionally narrow:
- Use current live markets as the base universe
- Keep the workflow lean and manual
- Use a simulated ledger only
- Never place real-money trades

## When To Use

Use this skill when the user asks to:
- run a Polymarket paper trader
- simulate trades on current Polymarket markets
- shadow trade or mock trade prediction markets
- see what a simple Polymarket agent would buy right now
- inspect the current paper ledger or portfolio status
- manage existing paper positions

Do not use this skill for:
- real-money execution
- historical backtesting
- standalone external-news research
- long-form market analysis

## Agent Prompt

完整的 agent 流程在 `prompts/TRADE.md`，順序固定：
- 先做持倉管理（thesis re-evaluation）
- 再做新交易
- 每次 wake-up 固定先跑 `geo`，再跑 `sports`
- `geo` 與 `sports` 是獨立 strategy pass；其中一邊有 trade，不構成跳過另一邊的理由
- `macro` 目前先註解掉，`ai` 目前停用
- 最後做 reflect，而且每輪都必須至少改一個東西，再進下一輪
- journal 格式直接參考 `data/journals/example.md`

另外還有一個獨立的 strategy-development prompt：`prompts/STRATEGY_DEV.md`
- 這個 prompt 不負責下單
- 它專門迭代 profile、strategy docs、screening 規則、agent burden 與相關 prompt
- 它使用自己的長期 state 與 journal：
  - `data/strategy_dev/state.md`
  - `data/strategy_dev/journals/{YYYY-MM-DD-HHMM}.md`

## Workflow

### 1. Initialize the ledger if needed

```bash
uv run python -m skill_poly_trader_v2 init
uv run python -m skill_poly_trader_v2 sync-tags
```

### 2. Check current positions

```bash
uv run python -m skill_poly_trader_v2 status
```

`status` will auto-reconcile any resolvable closed markets before reporting the remaining open positions.
Only sell when thesis changes:

```bash
# Manual exit at current market price (thesis changed)
uv run python -m skill_poly_trader_v2 sell --slug <slug>
```

### 3. Scan current candidates

```bash
uv run python -m skill_poly_trader_v2 markets
uv run python -m skill_poly_trader_v2 markets --profile geo --limit 60
uv run python -m skill_poly_trader_v2 markets --profile sports --limit 50
uv run python -m skill_poly_trader_v2 market --slug <slug>
```

Review the returned markets. `markets` is only the screening step: it should return a larger working set, exclude already-open positions, and reduce agent burden before deeper review. A production cycle should always run `geo` first and `sports` second. Do not hardcode a fixed number of candidates to research; any market that meets the shortlist criteria should move forward, and the agent should then work through that shortlist by priority. For any market that is seriously evaluated, the agent should do WebSearch, then assign its own probability for the chosen outcome.

### 4. Buy the selected outcome

```bash
uv run python -m skill_poly_trader_v2 buy --slug <slug> --outcome-index 0 --size 25 --probability 0.42 --reason "Agent judged from research"
uv run python -m skill_poly_trader_v2 buy --slug <slug> --outcome-index 0 --size 25 --probability 0.42 --reason "Agent judged from research" --dry-run
```

For binary markets:
- `outcomes[0]` maps to `--outcome-index 0`
- `outcomes[1]` maps to `--outcome-index 1`
- Current Polymarket binary markets usually return `["Yes", "No"]`, but the agent should always check the `market --slug` response before buying

## Profiles

### `geo`
- Uses native `/events` params around `tag_slug=politics`
- Meant for geopolitics, policy, elections, and other clear event markets
- Uses three buckets in one scan: `endDate`, `updatedAt`, and `createdAt`, with a target of `20` unique markets from each bucket

### `macro`
- Uses native `/events` params around `tag_slug=economy` and `tag_slug=fed`
- Meant for rates, inflation, recession, and policy timing markets
- Currently commented out of the production trade loop

### `ai`
- Uses native `/events` params around `tag_slug=ai`
- Meant for AI release, ship, and milestone markets
- Disabled in the production trade loop for now

### `sports`
- Uses native `/events` params around `tag_slug=sports`
- Returns one market per event to avoid overloading the agent with the same game family
- Current production working-set target is larger than the other profiles; use `--limit 50` as the default starting point

## Data Files

- `data/ledger_v2.json` — v2 paper trading ledger (positions, cash, history)
- `data/equity_curve_v2.json` — historical equity snapshots
- `data/lessons.md` — reusable trading rules and retrospectives
- `data/journals/{YYYY-MM-DD-HHMM}.md` — one Markdown file per full trading cycle
- `data/strategy_dev/state.md` — long-lived strategy development state
- `data/strategy_dev/journals/{YYYY-MM-DD-HHMM}.md` — one Markdown file per strategy-development cycle

## Response Style

Keep the response compact. Report:
- how many markets were scanned
- which market the agent selected, if any
- whether a paper trade was placed
- the chosen market, outcome index, outcome name, market price, model probability, edge, and paper size
- the updated cash and open-position count

If the agent decides `NO_TRADE`, say that plainly and explain the gating reason in one sentence.

## Safety

- Never place real-money orders
- Never ask for wallet keys
- Never treat this as investment advice
- If the user asks for backtesting or real trading, say this MVP skill does not do that yet
