"""Binance Square scraper via headed Playwright + response interception.

Strategy:
  1. headed Chromium opens Square (completing AWS WAF JS challenge automatically)
  2. Register response listener BEFORE navigation — captures feed API responses
  3. Scroll to trigger pagination; listener collects vos from each response
  4. Response has coinPairList already extracted by Binance — no regex needed

API: POST /bapi/composite/v9/friendly/pgc/feed/feed-recommend/list
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

STABLECOINS = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USD", "USDD", "USDE"}
SQUARE_URL = "https://www.binance.com/en/square"
FEED_API_PATH = "pgc/feed/feed-recommend/list"


@dataclass
class Post:
    post_id: str
    author: str
    username: str
    content: str
    tickers: list[str]
    like_count: int = 0
    view_count: int = 0
    verified: bool = False


@dataclass
class SquareSnapshot:
    posts: list[Post]
    ticker_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ticker_counts:
            self.ticker_counts = _count_tickers(self.posts)


def _is_likely_bot(username: str) -> bool:
    return bool(re.match(r"Square-Creator-[a-f0-9]+$", username or ""))


def _clean_ticker(raw: str) -> str:
    return raw.strip().lstrip("$").upper()


def _count_tickers(posts: list[Post]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for post in posts:
        if _is_likely_bot(post.username):
            continue
        for t in post.tickers:
            if t not in STABLECOINS:
                counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))


def _parse_vos(vos: list[dict]) -> list[Post]:
    posts = []
    for v in vos:
        coin_pair_list = v.get("coinPairList") or []
        tickers = [_clean_ticker(t) for t in coin_pair_list if t.strip()]
        tickers = [t for t in tickers if t and t not in STABLECOINS]
        posts.append(Post(
            post_id=str(v.get("id", "")),
            author=v.get("authorName", ""),
            username=v.get("username", ""),
            content=v.get("content", "") or "",
            tickers=tickers,
            like_count=v.get("likeCount", 0) or 0,
            view_count=v.get("viewCount", 0) or 0,
            verified=bool(v.get("authorVerificationType", 0)),
        ))
    return posts


async def scrape_square(
    max_posts: int = 200,
    headless: bool = False,
    profile_dir: Path | None = None,
    scroll_wait_seconds: float = 10.0,
    dump_dir: Path | None = None,
    html_dump_path: Path | None = None,
) -> SquareSnapshot:
    """
    Scrape Binance Square by intercepting the feed API responses the page makes
    naturally while scrolling. No manual API calls needed.

    Args:
        max_posts:           target post count (stop when reached)
        scroll_wait_seconds: pause between scrolls — slower = less likely to be banned
        dump_dir:            if set, write raw vos to
                             `{dump_dir}/{YYYY-MM-DD_HHMMSS}.jsonl` (one post per line)
    """
    from playwright.async_api import async_playwright

    all_posts: list[Post] = []
    seen_ids: set[str] = set()
    new_batch_event = asyncio.Event()
    pending_vos: list[list[dict]] = []
    raw_vos_all: list[dict] = []   # every post's raw API payload, for JSONL dump
    scrape_ts = datetime.utcnow().isoformat()

    async def _on_response(response):
        if FEED_API_PATH not in response.url:
            return
        try:
            body = await response.json()
        except Exception:
            return
        vos = None
        if isinstance(body, dict) and body.get("code") == "000000":
            data = body.get("data")
            if isinstance(data, dict):
                vos = data.get("vos")
        if vos:
            log.info("Intercepted feed response: %d posts", len(vos))
            pending_vos.append(vos)
            new_batch_event.set()

    launch_args = ["--disable-blink-features=AutomationControlled"]

    async with async_playwright() as p:
        if profile_dir:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=headless,
                args=launch_args,
            )
            page = await browser.new_page()
        else:
            browser = await p.chromium.launch(headless=headless, args=launch_args)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            await context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = await context.new_page()

        # Register BEFORE navigation so we don't miss the first load
        page.on("response", _on_response)

        log.info("Navigating to Binance Square...")
        await page.goto(SQUARE_URL, wait_until="load", timeout=60_000)
        await page.wait_for_timeout(3_000)

        # Scroll loop — each scroll triggers a new feed page load
        scroll_attempts = 0
        max_scroll_attempts = (max_posts // 20) + 5

        def _drain():
            while pending_vos:
                vos = pending_vos.pop(0)
                for raw in vos:
                    pid = str(raw.get("id", ""))
                    if pid and pid not in seen_ids:
                        seen_ids.add(pid)
                        raw_vos_all.append(raw)
                        parsed = _parse_vos([raw])
                        if parsed:
                            all_posts.append(parsed[0])

        while len(all_posts) < max_posts and scroll_attempts < max_scroll_attempts:
            _drain()
            if len(all_posts) >= max_posts:
                break

            new_batch_event.clear()
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            scroll_attempts += 1
            log.info("Scroll %d/%d, posts so far: %d",
                     scroll_attempts, max_scroll_attempts, len(all_posts))

            try:
                await asyncio.wait_for(new_batch_event.wait(), timeout=scroll_wait_seconds)
            except asyncio.TimeoutError:
                log.info("No new batch within %.1fs on scroll %d",
                         scroll_wait_seconds, scroll_attempts)
            # settle time so we don't scroll too aggressively
            await page.wait_for_timeout(int(scroll_wait_seconds * 1000))

        _drain()
        log.info("Total posts collected: %d", len(all_posts))
        await browser.close()

    if dump_dir and raw_vos_all:
        dump_dir.mkdir(parents=True, exist_ok=True)
        fname = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S") + ".jsonl"
        out = dump_dir / fname
        with out.open("w") as f:
            for raw in raw_vos_all:
                f.write(json.dumps({"_scrape_ts": scrape_ts, **raw}, ensure_ascii=False) + "\n")
        log.info("Dumped %d raw posts → %s", len(raw_vos_all), out)

    return SquareSnapshot(posts=all_posts[:max_posts])
