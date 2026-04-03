import os
import pytest
from backend.core.market_data.providers.finmind import fetch_chips
from backend.core.market_data.providers.fugle import fetch_quote as fetch_fugle_quote

# Skip if keys are not set
@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("FINMIND_API_KEY"), reason="FINMIND_API_KEY not set")
def test_finmind_fetch_chips_real():
    """
    Real integration test for FinMind.
    Requires a valid FINMIND_API_KEY in .env.
    """
    symbol = "2330.TW"
    chips = fetch_chips(symbol, lookback_days=30)
    
    assert len(chips) > 0
    assert chips[0].symbol == symbol
    assert hasattr(chips[0], "foreign_net")
    print(f"[FinMind] Success: Fetched {len(chips)} data points for {symbol}")

@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("FUGLE_API_KEY"), reason="FUGLE_API_KEY not set")
def test_fugle_fetch_quote_real():
    """
    Real integration test for Fugle.
    Requires a valid FUGLE_API_KEY in .env.
    Note: Market must be open or have recent data.
    """
    symbol = "2330.TW"
    quote = fetch_fugle_quote(symbol)
    
    assert quote is not None
    assert quote.symbol == symbol
    assert quote.price > 0
    assert quote.source == "fugle"
    print(f"[Fugle] Success: Fetched price {quote.price} for {symbol}")
