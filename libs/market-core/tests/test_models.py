from datetime import datetime

from market_core.models import AnalysisReport, MarketConfig, MarketRuntimeConfig, Quote, utc_now_iso


def test_utc_now_iso() -> None:
    ts = utc_now_iso()
    assert ts.endswith("Z")
    assert "T" in ts
    dt = datetime.fromisoformat(ts[:-1])
    assert dt.year >= 2024


def test_quote_model() -> None:
    quote = Quote(
        symbol="AAPL",
        market_profile="us_equity",
        price=150.0,
        source="yfinance",
    )
    assert quote.symbol == "AAPL"
    assert quote.price == 150.0
    assert quote.timestamp.endswith("Z")


def test_runtime_config_defaults() -> None:
    config = MarketRuntimeConfig(market=MarketConfig(profile="us_equity"))
    assert config.market.profile == "us_equity"
    assert config.analysis.timeframe == "1d"
    assert config.news.enabled is False


def test_analysis_report_defaults() -> None:
    report = AnalysisReport(
        symbol="AAPL",
        quote=Quote(symbol="AAPL", market_profile="us_equity", price=150.0, source="test"),
    )
    assert report.metrics == {}
    assert report.triggers == {}
    assert report.warnings == []
    assert report.news == []
