"""Tests for Square scraper — all offline using mock vos data."""

import pytest

from lana_copycat.scrapers.square import (
    _is_likely_bot,
    _clean_ticker,
    _count_tickers,
    _parse_vos,
    Post,
    SquareSnapshot,
)


# ── _is_likely_bot ────────────────────────────────────────────────────────────

def test_bot_detection_default_names():
    assert _is_likely_bot("Square-Creator-26cf1311d9fe") is True
    assert _is_likely_bot("Square-Creator-6a6aee6cf86e") is True
    assert _is_likely_bot("Square-Creator-f02973224") is True

def test_bot_detection_real_users():
    assert _is_likely_bot("Alice") is False
    assert _is_likely_bot("CryptoWhale99") is False
    assert _is_likely_bot("Lana") is False
    assert _is_likely_bot("mmx_qq") is False

def test_bot_detection_edge_cases():
    assert _is_likely_bot("") is False
    assert _is_likely_bot(None) is False
    # Square-Creator with uppercase hex should NOT match (pattern is lowercase a-f)
    assert _is_likely_bot("Square-Creator-AABBCC") is False


# ── _clean_ticker ─────────────────────────────────────────────────────────────

def test_clean_ticker_strips_dollar():
    assert _clean_ticker("$ETH") == "ETH"
    assert _clean_ticker("$btc") == "BTC"

def test_clean_ticker_strips_whitespace():
    assert _clean_ticker("  SOL  ") == "SOL"


# ── _parse_vos ────────────────────────────────────────────────────────────────

SAMPLE_VOS = [
    {
        "id": "111",
        "authorName": "Alice",
        "username": "alice_trader",
        "content": "Bullish on ETH",
        "coinPairList": ["ETH", "BTC"],
        "likeCount": 50,
        "viewCount": 1000,
        "authorVerificationType": 1,
    },
    {
        "id": "222",
        "authorName": "Bot",
        "username": "Square-Creator-aabbccdd1234",
        "content": "SOL to the moon",
        "coinPairList": ["SOL"],
        "likeCount": 0,
        "viewCount": 10,
        "authorVerificationType": 0,
    },
    {
        "id": "333",
        "authorName": "Bob",
        "username": "bob99",
        "content": "ETH looking great",
        "coinPairList": ["ETH", "USDT"],  # USDT should be filtered
        "likeCount": 20,
        "viewCount": 500,
        "authorVerificationType": 0,
    },
]


def test_parse_vos_fields():
    posts = _parse_vos(SAMPLE_VOS)
    assert len(posts) == 3
    alice = posts[0]
    assert alice.post_id == "111"
    assert alice.username == "alice_trader"
    assert "ETH" in alice.tickers
    assert "BTC" in alice.tickers
    assert alice.verified is True
    assert alice.like_count == 50

def test_parse_vos_stablecoins_filtered():
    posts = _parse_vos(SAMPLE_VOS)
    bob = posts[2]
    assert "USDT" not in bob.tickers
    assert "ETH" in bob.tickers


# ── _count_tickers ────────────────────────────────────────────────────────────

def test_count_tickers_filters_bots():
    posts = _parse_vos(SAMPLE_VOS)
    counts = _count_tickers(posts)
    # ETH appears in alice + bob (both real) = 2
    assert counts.get("ETH") == 2
    # SOL only in bot post → should be excluded
    assert "SOL" not in counts

def test_count_tickers_sorted_descending():
    posts = _parse_vos(SAMPLE_VOS)
    counts = _count_tickers(posts)
    values = list(counts.values())
    assert values == sorted(values, reverse=True)


# ── SquareSnapshot ────────────────────────────────────────────────────────────

def test_snapshot_builds_counts_automatically():
    posts = _parse_vos(SAMPLE_VOS)
    snap = SquareSnapshot(posts=posts)
    assert snap.ticker_counts.get("ETH") == 2
    assert "SOL" not in snap.ticker_counts
    assert "USDT" not in snap.ticker_counts

def test_snapshot_no_stablecoins():
    posts = _parse_vos(SAMPLE_VOS)
    snap = SquareSnapshot(posts=posts)
    stablecoins = {"USDT", "USDC", "BUSD", "DAI", "TUSD", "FDUSD", "USD", "USDD", "USDE"}
    assert not stablecoins.intersection(snap.ticker_counts.keys())
