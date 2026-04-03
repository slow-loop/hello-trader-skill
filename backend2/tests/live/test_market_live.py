import pytest
from backend2.market import get_quote, get_bars, get_news
from backend2.policies import MARKET_PROFILES
from backend2.models import WorkspaceRuntimeConfig, MarketConfig, NewsConfig, NewsSourceConfig

@pytest.fixture
def tw_equity_profile():
    return MARKET_PROFILES["tw_equity"]

@pytest.fixture
def us_equity_profile():
    return MARKET_PROFILES["us_equity"]

@pytest.mark.live
def test_get_quote_tw(tw_equity_profile):
    # Test a common TW stock
    quote = get_quote("2330", tw_equity_profile)
    assert quote.symbol == "2330.TW"
    assert quote.price > 0
    assert quote.source in ("yfinance", "fugle")

@pytest.mark.live
def test_get_quote_us(us_equity_profile):
    # Test a common US stock
    quote = get_quote("AAPL", us_equity_profile)
    assert quote.symbol == "AAPL"
    assert quote.price > 0
    assert quote.source == "yfinance"

@pytest.mark.live
def test_get_bars_live(us_equity_profile):
    bars = get_bars("AAPL", us_equity_profile, timeframe="1d", lookback_days=30)
    assert len(bars) > 0
    assert bars[0].symbol == "AAPL"
    assert bars[0].close > 0

@pytest.mark.live
def test_get_news_live():
    config = WorkspaceRuntimeConfig(
        name="Test",
        market=MarketConfig(profile="us_equity"),
        news=NewsConfig(
            enabled=True,
            sources=[
                NewsSourceConfig(name="Yahoo Finance", kind="rss", url="https://finance.yahoo.com/news/rssindex")
            ]
        )
    )
    news = get_news(config)
    assert len(news) > 0
    assert news[0].title != ""
    assert news[0].url.startswith("http")
