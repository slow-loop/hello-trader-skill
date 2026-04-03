import pytest
from backend.core.market_data.providers.yfinance import fetch_quote

@pytest.mark.integration
def test_yfinance_fetch_quote_real():
    """
    Real integration test that calls Yahoo Finance API.
    Requires internet connection.
    """
    symbol = "2330.TW" # TSMC
    quote = fetch_quote(symbol)
    
    # Assertions on real data
    assert quote is not None
    assert quote.symbol == symbol
    assert quote.name == "Taiwan Semiconductor Manufacturing Company Limited"
    assert quote.price > 0
    assert hasattr(quote, "change_pct")
    assert isinstance(quote.change_pct, float)

@pytest.mark.integration
def test_yfinance_fetch_invalid_symbol():
    """
    Integration test for a non-existent symbol.
    Should raise ValueError according to its implementation.
    """
    symbol = "INVALID_SYMBOL_123456789"
    with pytest.raises(ValueError):
        fetch_quote(symbol)
