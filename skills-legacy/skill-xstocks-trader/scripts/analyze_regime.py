import yfinance as yf
import pandas as pd
import numpy as np
import talib

def analyze_ticker(symbol):
    print(f"\nAnalyzing {symbol}...")
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        if df.empty:
            print("  No data found.")
            return

        close = df['Close'].iloc[-1]
        
        # Calculate indicators
        sma50 = talib.SMA(df['Close'].values, timeperiod=50)[-1]
        sma200 = talib.SMA(df['Close'].values, timeperiod=200)[-1]
        rsi = talib.RSI(df['Close'].values, timeperiod=14)[-1]
        atr = talib.ATR(df['High'].values, df['Low'].values, df['Close'].values, timeperiod=14)[-1]
        
        # volatility pct
        vol_pct = (atr / close) * 100
        
        distance_from_200 = ((close - sma200) / sma200) * 100
        distance_from_50 = ((close - sma50) / sma50) * 100
        
        print(f"  Current Price: ${close:.2f}")
        print(f"  SMA50: ${sma50:.2f} ({distance_from_50:+.2f}%)")
        print(f"  SMA200: ${sma200:.2f} ({distance_from_200:+.2f}%)")
        print(f"  RSI(14): {rsi:.2f}")
        print(f"  ATR Volatility: {vol_pct:.2f}%")
        
        if close > sma200 and close > sma50:
            regime = "Strong Bull (Uptrend)"
        elif close > sma200 and close < sma50:
            regime = "Bull Market Pullback (Correction)"
        elif close < sma200 and close < sma50:
            regime = "Strong Bear (Downtrend)"
        else:
            regime = "Choppy / Transition"
            
        print(f"  => Regime: {regime}")
        
    except Exception as e:
        print(f"  Error: {e}")

if __name__ == "__main__":
    symbols = ['SPY', 'QQQ', 'AAPL', 'TSLA', 'NVDA']
    print("Fetching current market data (1-year lookback)...\n")
    for s in symbols:
        analyze_ticker(s)
