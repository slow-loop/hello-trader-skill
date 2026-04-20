from datetime import datetime, timezone

from market_core.policies import get_market_profile, get_market_session, normalize_symbol


def test_normalize_symbol_tw() -> None:
    profile = get_market_profile("tw_equity")
    assert normalize_symbol("2330", profile) == "2330.TW"


def test_normalize_symbol_us() -> None:
    profile = get_market_profile("us_equity")
    assert normalize_symbol("aapl", profile) == "AAPL"


def test_market_session_weekend_is_closed() -> None:
    profile = get_market_profile("us_equity")
    now = datetime(2026, 4, 11, 15, 0, tzinfo=timezone.utc)
    session = get_market_session(profile, now=now)
    assert session["is_open"] is False
