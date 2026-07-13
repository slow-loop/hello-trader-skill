# polymarket-scan

[English](README.md) | [繁體中文](README.zh-TW.md)

A read-only scanning agent for Polymarket single-game moneylines. It looks for
one specific shape of opportunity: a clearly stronger side whose price hasn't
caught up yet — not a coin-flip, a **lagging price**.

**Discovery only. It never places an order.** When it finds something, it hands
the opportunity off to a separate trading skill.

No API key required — the scanner is pure Python stdlib with its own DNS-over-HTTPS
resolver, so it works even if a local ISP blocks Polymarket's domain.

## How it works — a three-stage funnel (cheap filters first, expensive checks last)

```
1. Mechanical scan   scripts/polymarket_scan.py     → hundreds of markets   cheap
2. Gut check         "is one side obviously stronger?" → a handful          cheap (seconds, no browsing)
3. Verification      only for survivors: odds/rules/news → 0-1 candidates   expensive
```

Most days this produces **zero** candidates — that's expected, not a bug. The agent
is instructed to prefer over-including in step 2 (cheap) and only commit after
step 3 (expensive verification against real standings, polls, and settlement rules).

## CLI

```bash
# Sports: scan every sport for single-game moneylines opened since a given date
python3 scripts/polymarket_scan.py moneyline --since 2026-07-01

# Elections: uses the /events + tag_slug engine (moneyline doesn't cover politics)
python3 scripts/polymarket_scan.py tagged --mode fresh --tags elections,world-elections
```

`tagged` modes: `early` (single matchup, near 50/50), `fresh` (just opened, real
order book), `band` (traded, still mid-range price), `raw` (no filtering).
Full flag reference is in [`prompts/SKILL.md`](prompts/SKILL.md).

## Output

Every run produces a full two-round report — what was scanned, what was kept,
what was dropped and why, then the verification detail for each survivor — written
to `data/journals/{YYYY-MM-DD}.md`.

## Agent instructions

The operating logic for the Claude agent (mindset, funnel rules, report format) lives
in [`prompts/SKILL.md`](prompts/SKILL.md), written in Traditional Chinese. This
README is the human-facing "what is this / how do I run it" doc; `SKILL.md` is
the prompt Claude actually follows.

## Part of hello-trader-skill

This skill lives inside the [hello-trader-skill](../../README.md) monorepo — see the
root README for the full list of trading/research skills and shared components
(`libs/market-core`, `hello-web-reader`).
