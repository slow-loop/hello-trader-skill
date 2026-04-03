import argparse
import json
import os
import yfinance as yf
from pathlib import Path

def convert_to_freqtrade_format(df):
    """
    Freqtrade format: list of lists
    [
        [ timestamp (int, ms), open, high, low, close, volume ],
        ...
    ]
    """
    freqtrade_data = []
    
    # Ensure datetime index
    df.index = df.index.tz_convert('UTC') if df.index.tz is not None else df.index.tz_localize('UTC')

    for index, row in df.iterrows():
        # Yahoo finance might have NaN for some missing data, skip or fill
        if row.isna().any():
            continue
            
        timestamp_ms = int(index.timestamp() * 1000)
        
        freqtrade_data.append([
            timestamp_ms,
            round(float(row['Open']), 4),
            round(float(row['High']), 4),
            round(float(row['Low']), 4),
            round(float(row['Close']), 4),
            float(row['Volume'])
        ])
    return freqtrade_data

def main():
    parser = argparse.ArgumentParser(description="Download Yahoo Finance data to Freqtrade JSON format.")
    parser.add_argument("--symbols", nargs="+", default=["AAPL", "TSLA", "NVDA", "SPY", "QQQ"],
                        help="List of Yahoo Finance symbols to download")
    parser.add_argument("--timeframe", default="1d", choices=["1d", "1h", "15m", "5m"],
                        help="Timeframe to download")
    parser.add_argument("--quote", default="USD", help="Quote currency for freqtrade filename (e.g. USD, USDC)")
    parser.add_argument("--exchange", default="hyperliquid", help="Target exchange data folder")
    parser.add_argument("--period", default="10y", help="Download period for yfinance (e.g., 10y, max, 730d)")
    
    args = parser.parse_args()
    
    # Define output directory based on absolute path relative to this script
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent
    
    data_dir = repo_root / "freqtrade_userdata" / "data" / args.exchange
    data_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Target directory: {data_dir}")
    print(f"Downloading data for: {', '.join(args.symbols)} (Timeframe: {args.timeframe})")
    
    yfinance_tf_map = {
        "1d": "1d",
        "1h": "60m",
        "15m": "15m",
        "5m": "5m"
    }
    
    yf_tf = yfinance_tf_map.get(args.timeframe, "1d")
    
    for sym in args.symbols:
        print(f"Fetching {sym}...")
        try:
            ticker = yf.Ticker(sym)
            # Use prepost=True to fetch pre-market and after-hours data
            df = ticker.history(period=args.period, interval=yf_tf, prepost=True)
            
            if df.empty:
                print(f"  Warning: No data for {sym}.")
                continue
                
            # Convert index to timezone-aware UTC
            df.index = df.index.tz_convert('UTC') if df.index.tz is not None else df.index.tz_localize('UTC')

            # --- Forward Fill to create a continuous 24/7 timeframe ---
            # Remove duplicate indices if any
            df = df[~df.index.duplicated(keep='first')]
            
            # Create a complete date range spanning 24/7
            freq_map = {
                "1d": "d",
                "1h": "h",
                "15m": "15min",
                "5m": "5min",
                "60m": "h"
            }
            pd_freq = freq_map.get(yf_tf, "d")
            
            # Make sure we import pandas at the top (added dynamically if missing)
            import pandas as pd
            full_index = pd.date_range(start=df.index.min(), end=df.index.max(), freq=pd_freq, tz='UTC')
            
            # Reindex and forward fill prices. Volume becomes 0 for missing candles.
            df = df.reindex(full_index)
            df['Close'] = df['Close'].ffill()
            df['Open'] = df['Open'].ffill()
            df['High'] = df['High'].ffill()
            df['Low'] = df['Low'].ffill()
            df['Volume'] = df['Volume'].fillna(0)
            # -----------------------------------------------------------
                
            ft_data = convert_to_freqtrade_format(df)
            
            # Save format: AAPL_USDC-1d.json
            filename = f"{sym}_{args.quote}-{args.timeframe}.json"
            filepath = data_dir / filename
            
            with open(filepath, "w") as f:
                json.dump(ft_data, f)
                
            print(f"  Saved {len(ft_data)} candles to {filename}")
            
        except Exception as e:
            print(f"  Error processing {sym}: {e}")

if __name__ == "__main__":
    main()
