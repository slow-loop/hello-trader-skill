from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from pydantic import BaseModel


class MarketProfile(BaseModel):
    id: str
    label: str
    timezone: str
    benchmark_symbol: str
    session_kind: str
    open_time: str | None = None
    close_time: str | None = None
    currency: str
    buy_fee_rate: float = 0.0
    sell_fee_rate: float = 0.0
    sell_tax_rate: float = 0.0
    supports_fractional: bool = True


MARKET_PROFILES: dict[str, MarketProfile] = {
    "tw_equity": MarketProfile(
        id="tw_equity",
        label="Taiwan Equity",
        timezone="Asia/Taipei",
        benchmark_symbol="^TWII",
        session_kind="weekday_hours",
        open_time="09:00",
        close_time="13:30",
        currency="TWD",
        buy_fee_rate=0.001425,
        sell_fee_rate=0.001425,
        sell_tax_rate=0.003,
        supports_fractional=False,
    ),
    "us_equity": MarketProfile(
        id="us_equity",
        label="US Equity",
        timezone="America/New_York",
        benchmark_symbol="^GSPC",
        session_kind="weekday_hours",
        open_time="09:30",
        close_time="16:00",
        currency="USD",
        supports_fractional=True,
    ),
    "xstocks": MarketProfile(
        id="xstocks",
        label="Tokenized Stocks",
        timezone="UTC",
        benchmark_symbol="SPY",
        session_kind="always_open",
        currency="USDC",
        buy_fee_rate=0.0005,
        sell_fee_rate=0.0005,
        supports_fractional=True,
    ),
    "crypto": MarketProfile(
        id="crypto",
        label="Crypto",
        timezone="UTC",
        benchmark_symbol="BTC-USD",
        session_kind="always_open",
        currency="USD",
        buy_fee_rate=0.001,
        sell_fee_rate=0.001,
        supports_fractional=True,
    ),
}


def get_market_profile(profile_id: str) -> MarketProfile:
    try:
        return MARKET_PROFILES[profile_id]
    except KeyError as exc:
        supported = ", ".join(sorted(MARKET_PROFILES))
        raise ValueError(f"unknown market profile '{profile_id}', supported: {supported}") from exc


def normalize_symbol(symbol: str, profile: MarketProfile) -> str:
    raw = symbol.strip().upper()
    if not raw:
        raise ValueError("symbol is required")

    if profile.id == "tw_equity":
        if raw.startswith("^") or raw.endswith(".TW") or raw.endswith(".TWO"):
            return raw
        if raw.isdigit():
            return f"{raw}.TW"
    return raw


def market_data_symbol(symbol: str, profile: MarketProfile) -> str:
    normalized = normalize_symbol(symbol, profile)
    if profile.id == "xstocks" and "/" in normalized:
        return normalized.split("/", 1)[0]
    return normalized


def room_now(profile: MarketProfile, now: datetime | None = None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(ZoneInfo(profile.timezone))


def get_market_session(profile: MarketProfile, now: datetime | None = None) -> dict[str, str | bool]:
    current = room_now(profile, now)
    date_str = current.date().isoformat()

    if profile.session_kind == "always_open":
        return {
            "date": date_str,
            "phase": "market_open",
            "is_open": True,
            "reason": "24/7 market",
            "timezone": profile.timezone,
        }

    if current.weekday() >= 5:
        return {
            "date": date_str,
            "phase": "closed",
            "is_open": False,
            "reason": "weekend",
            "timezone": profile.timezone,
        }

    open_hour, open_minute = _parse_hm(profile.open_time)
    close_hour, close_minute = _parse_hm(profile.close_time)
    hm = current.hour * 100 + current.minute
    open_hm = open_hour * 100 + open_minute
    close_hm = close_hour * 100 + close_minute

    if hm < open_hm:
        return {
            "date": date_str,
            "phase": "pre_market",
            "is_open": False,
            "reason": "pre-market",
            "timezone": profile.timezone,
        }
    if hm <= close_hm:
        return {
            "date": date_str,
            "phase": "market_open",
            "is_open": True,
            "reason": "trading day",
            "timezone": profile.timezone,
        }
    return {
        "date": date_str,
        "phase": "post_market",
        "is_open": False,
        "reason": "post-market",
        "timezone": profile.timezone,
    }


def _parse_hm(value: str | None) -> tuple[int, int]:
    if not value:
        return 0, 0
    hour_str, minute_str = value.split(":", 1)
    return int(hour_str), int(minute_str)
