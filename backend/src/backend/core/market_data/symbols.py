from __future__ import annotations

import re

from backend.core.market_data.models import MarketCode

_SAFE_FILE_CHARS = re.compile(r"[^a-z0-9._-]+")
_TW_INDEX_SYMBOLS = {"^TWII"}


def normalize_symbol(symbol: str) -> str:
    raw = symbol.strip().upper()
    if not raw:
        raise ValueError("symbol is required")
    if raw.startswith("^"):
        return raw
    if raw.endswith(".TW") or raw.endswith(".TWO"):
        return raw
    if raw.isdigit():
        return f"{raw}.TW"
    return raw


def detect_market(symbol: str) -> MarketCode:
    normalized = normalize_symbol(symbol)
    if normalized in _TW_INDEX_SYMBOLS:
        return "tw"
    if normalized.endswith(".TW") or normalized.endswith(".TWO"):
        return "tw"
    if normalized.isdigit():
        return "tw"
    return "us"


def strip_suffix(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    return normalized.removesuffix(".TW").removesuffix(".TWO")


def symbol_key(symbol: str) -> str:
    normalized = normalize_symbol(symbol).lower()
    normalized = normalized.lstrip("^")
    return _SAFE_FILE_CHARS.sub("_", normalized)


def is_tw_equity_symbol(symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    if not (normalized.endswith(".TW") or normalized.endswith(".TWO")):
        return False
    return strip_suffix(normalized).isdigit()
