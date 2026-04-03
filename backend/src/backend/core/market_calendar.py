from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CALENDAR_FILE = PROJECT_ROOT / "data" / "config" / "twse_holidays.yaml"

MARKET_OPEN_HM = 900
MARKET_CLOSE_HM = 1330
CHIPS_UPDATE_HM = 1630


@lru_cache(maxsize=1)
def _load_twse_holidays() -> dict[str, set[str]]:
    if not CALENDAR_FILE.exists():
        return {}

    raw = yaml.safe_load(CALENDAR_FILE.read_text(encoding="utf-8")) or {}
    holidays: dict[str, set[str]] = {}
    for year, values in raw.items():
        holidays[str(year)] = {str(item) for item in (values or [])}
    return holidays


def get_twse_holidays(year: int | str) -> set[str]:
    return _load_twse_holidays().get(str(year), set())


def is_twse_holiday(target_date: date | None = None) -> bool:
    d = target_date or date.today()
    return d.isoformat() in get_twse_holidays(d.year)


def get_twse_market_session(now: datetime | None = None) -> str:
    current = now or datetime.now()
    d = current.date()
    if d.weekday() >= 5 or is_twse_holiday(d):
        return "closed"

    hm = current.hour * 100 + current.minute
    if hm < MARKET_OPEN_HM:
        return "pre_market"
    if hm <= MARKET_CLOSE_HM:
        return "market_open"
    return "post_market"


def get_last_trading_day(from_date: date | None = None, market_close_hm: int = MARKET_CLOSE_HM) -> date:
    """Return the most recent completed trading day (weekday, non-holiday).

    If called during market hours, returns the previous trading day since
    today's session is not yet complete.
    """
    d = from_date or date.today()
    # If market is still open today, look at yesterday
    now = datetime.now()
    if d == now.date():
        hm = now.hour * 100 + now.minute
        if hm <= market_close_hm:
            d -= timedelta(days=1)

    for _ in range(10):
        if d.weekday() < 5 and not is_twse_holiday(d):
            return d
        d -= timedelta(days=1)
    return d  # fallback


def get_twse_market_status(now: datetime | None = None) -> dict[str, str | bool]:
    current = now or datetime.now()
    d = current.date()
    d_str = d.isoformat()

    if d.weekday() >= 5:
        return {"date": d_str, "is_open": False, "reason": "週末"}
    if is_twse_holiday(d):
        return {"date": d_str, "is_open": False, "reason": "國定假日"}

    hm = current.hour * 100 + current.minute
    if hm < MARKET_OPEN_HM:
        return {"date": d_str, "is_open": False, "reason": "盤前"}
    if hm > MARKET_CLOSE_HM:
        return {"date": d_str, "is_open": False, "reason": "盤後"}
    return {"date": d_str, "is_open": True, "reason": "交易日"}
