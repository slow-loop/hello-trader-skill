import ccxt

exchange = ccxt.hyperliquid()
markets = exchange.load_markets()

# search for anything containing NVDA
print("Searching for NVDA in Hyperliquid markets...\n")
for sym in markets.keys():
    if 'NVDA' in sym:
        print(f"Symbol: {sym}")
        try:
            ticker = exchange.fetch_ticker(sym)
            print(f"  => Last Price: {ticker.get('last')}\n")
        except Exception as e:
            print(f"  => Error fetching price: {e}\n")
