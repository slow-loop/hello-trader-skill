from datetime import date, datetime
from unittest.mock import patch

from backend.core.market_calendar import (
    get_twse_holidays,
    is_twse_holiday,
    get_twse_market_session,
    get_twse_market_status,
)

def test_get_twse_holidays_empty_if_file_missing():
    with patch("backend.core.market_calendar.CALENDAR_FILE") as mock_file:
        mock_file.exists.return_value = False
        assert get_twse_holidays(2025) == set()

def test_is_twse_holiday():
    holidays = {"2025": {"2025-01-01", "2025-01-25"}}
    with patch("backend.core.market_calendar._load_twse_holidays", return_value=holidays):
        assert is_twse_holiday(date(2025, 1, 1)) is True
        assert is_twse_holiday(date(2025, 1, 2)) is False

def test_get_twse_market_session():
    # Mocking holiday check
    with patch("backend.core.market_calendar.is_twse_holiday", return_value=False):
        # Weekday scenarios
        # Early morning
        dt_pre = datetime(2025, 3, 3, 8, 30) # Monday
        assert get_twse_market_session(dt_pre) == "pre_market"

        # Trading hours
        dt_open = datetime(2025, 3, 3, 10, 0)
        assert get_twse_market_session(dt_open) == "market_open"

        # Post market
        dt_post = datetime(2025, 3, 3, 14, 0)
        assert get_twse_market_session(dt_post) == "post_market"

    # Weekend
    dt_sat = datetime(2025, 3, 1, 10, 0) # Saturday
    assert get_twse_market_session(dt_sat) == "closed"

    # Holiday
    with patch("backend.core.market_calendar.is_twse_holiday", return_value=True):
        dt_holiday = datetime(2025, 3, 3, 10, 0)
        assert get_twse_market_session(dt_holiday) == "closed"

def test_get_twse_market_status():
    with patch("backend.core.market_calendar.is_twse_holiday", return_value=False):
        # Saturday
        dt_sat = datetime(2025, 3, 1, 10, 0)
        status = get_twse_market_status(dt_sat)
        assert status["is_open"] is False
        assert status["reason"] == "週末"

        # Pre-market
        dt_pre = datetime(2025, 3, 3, 8, 30)
        status = get_twse_market_status(dt_pre)
        assert status["is_open"] is False
        assert status["reason"] == "盤前"

        # Open
        dt_open = datetime(2025, 3, 3, 10, 0)
        status = get_twse_market_status(dt_open)
        assert status["is_open"] is True
        assert status["reason"] == "交易日"
