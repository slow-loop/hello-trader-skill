---
name: tw-trader-agno
description: Read-only Taiwan trader workflow skill for this repository. Use it to validate the TW trader process with repo files, CLI tools, and news scanning, then produce paper-trading recommendations and blockers.
---

# TW Trader Agno Skill

Use this skill when the task is to run or validate the Taiwan trader workflow inside this repository.

## Goals

- Reconstruct the current market and account context from repo files and CLI tools.
- Follow the trader prompt in `skills/tw-trader/prompts/TRADING.TW.md`.
- Keep the entire run read-only.
- Produce candidate actions for paper trading only.

## Required workflow

1. Read `skills/tw-trader/prompts/TRADING.TW.md` before taking action.
2. If the prompt references other prompt files, read those too.
3. Read the account context files:
   - `skills/tw-trader/data/account/lessons.md`
   - `skills/tw-trader/data/account/watchlist.yaml`
   - recent files under `skills/tw-trader/data/account/journals/`
4. Run the read-only workflow tools:
   - market overview
   - account snapshot
   - watchlist evaluation
   - trigger summary
   - news scan
5. If there are relevant symbols, inspect them with the market tool.
6. Read `skills/tw-trader/prompts/TRADING_TW_REFLECT.md` to understand the follow-up loop, but do not write reflections in this PoC.

## Operating rules

- This PoC is read-only. Never place or modify orders, watchlist items, journals, lessons, prompts, or code.
- If the workflow would normally execute a mutation, explain the hypothetical action instead of doing it.
- Prefer repo evidence over assumptions. Read files and use tools before concluding.
- If a CLI step fails, report the exact blocker and continue only with evidence you already have.

## Expected output

- Execution summary
- Market / portfolio state used
- Watchlist trigger and invalidation summary
- Candidate actions for paper trading only
- Blockers, tool failures, or prompt mismatches
