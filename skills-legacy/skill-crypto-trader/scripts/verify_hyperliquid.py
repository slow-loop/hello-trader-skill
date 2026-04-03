import ccxt

def check_hl_markets():
    print("Initiating connection to Hyperliquid via CCXT...")
    exchange = ccxt.hyperliquid()
    
    # Load all markets
    markets = exchange.load_markets()
    
    target_pairs = ['SPY/USDC', 'QQQ/USDC', 'AAPL/USDC', 'TSLA/USDC', 'NVDA/USDC']
    
    for pair in target_pairs:
        try:
            # Check if pair is in loaded markets
            if pair in exchange.markets:
                print(f"\n[OK] {pair} exists in Hyperliquid markets.")
                # Fetch recent ticker to prove it's actively trading
                ticker = exchange.fetch_ticker(pair)
                last_price = ticker.get('last')
                volume = ticker.get('baseVolume')
                print(f"     => Last Price: {last_price}")
                print(f"     => 24h Base Volume: {volume}")
            else:
                print(f"\n[FAIL] {pair} not found in Hyperliquid markets!")
        except Exception as e:
            print(f"\n[ERROR] Attempting to fetch data for {pair}: {e}")

if __name__ == "__main__":
    check_hl_markets()
