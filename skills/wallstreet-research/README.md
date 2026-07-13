# wallstreet-research

A deep-dive research skill for a single stock or theme. Runs multiple rounds
of sourced data-gathering and produces a fundamentals + trading research
report that follows a Wall-Street-style framework — every material fact
(number, event, guidance) is tagged with its source URL.

## What it does

1. Reads the research framework at [`references/wall-street-framework.md`](references/wall-street-framework.md)
2. Gathers data in a bounded number of rounds: a quick news scan (`gnews://`),
   optionally a config-driven source sweep (`sources.tw.yaml` tags), then deep
   reads of the 3–6 most relevant URLs
3. Writes the report directly in Markdown once enough sources are collected
   (target: 6+ directly relevant sources, minimum 4, spanning company/industry,
   macro/market, and sentiment/trading angles)

It deliberately stops after a bounded number of search rounds rather than
searching indefinitely — an incomplete data gap gets called out in the report
instead of triggering unlimited follow-up searches.

## CLI

Uses the shared `web-reader` CLI (from `hello-web-reader`, run from the
`tw-trader` skill root):

```bash
# Single URL or pseudo-URL
uv run web-reader "<url_or_pseudo_url>" --format=md

# Examples of supported sources:
#   https://example.com/news/article-1        (standard web)
#   gnews://NVDA?period=30d&max=10             (Google News)
#   https://www.ptt.cc/bbs/Stock/M.123...html  (PTT)
#   https://news.cnyes.com/news/id/54321       (CNYES)
#   https://example.com/feed.xml               (RSS/Atom/JSON)

# Config-driven sweep, filtered by tag
uv run web-reader <path/to/sources.yaml> --tags=research
```

**Known limitation**: Reddit sources currently return 403 — Reddit blocks the
anonymous `.json` API. There's no zero-config fix yet; use OpenCLI
(`opencli reddit ...`, reusing an already-logged-in Chrome session) when a
logged-in session is required. Substack and single YouTube video transcripts
aren't in this CLI's source list either — use `WebFetch` to fill those gaps.

## Agent instructions

The full task definition, rules, and step-by-step process are in
[`SKILL.md`](SKILL.md) (Traditional Chinese).

## Part of hello-trader-skill

This skill lives inside the [hello-trader-skill](../../README.md) monorepo —
see the root README for the full list of trading/research skills.
