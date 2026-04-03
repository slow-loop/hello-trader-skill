import pandas as pd
import numpy as np
import pandas_ta as ta
from pyharmonics import Technicals
import smartmoneyconcepts as smc
import zigzag

def test_indicators():
    print("--- Starting Indicator Tests ---")
    
    # 1. Generate Dummy Data (OHLCV)
    np.random.seed(42)
    dates = pd.date_range(start="2024-01-01", periods=100, freq="D")
    df = pd.DataFrame({
        "open": np.random.uniform(40000, 45000, 100),
        "high": np.random.uniform(45000, 50000, 100),
        "low": np.random.uniform(35000, 40000, 100),
        "close": np.random.uniform(40000, 45000, 100),
        "volume": np.random.uniform(100, 1000, 100)
    }, index=dates)
    
    # Ensure high > low and high > open/close
    df['high'] = df[['open', 'close', 'high']].max(axis=1) + 100
    df['low'] = df[['open', 'close', 'low']].min(axis=1) - 100

    # 2. Test pandas-ta
    print("\n[1/3] Testing pandas-ta-classic...")
    df.ta.rsi(append=True)
    df.ta.macd(append=True)
    print(f"Computed RSI (last 5 values):\n{df['RSI_14'].tail(5).tolist()}")
    print("✅ pandas-ta SUCCESS")

    # 3. Test smartmoneyconcepts (requires zigzag)
    print("\n[2/3] Testing smartmoneyconcepts & zigzag...")
    # smc requires specific column names but we already have them
    df_smc = df.copy()
    
    try:
        # Test zigzag directly
        pivots = zigzag.peak_valley_pivots(df_smc['close'].values, 0.05, -0.05)
        print(f"ZigZag pivots found: {np.count_nonzero(pivots)}")
        
        # Test smc library functions (Order Blocks / FVG etc)
        # The class is smc.smc
        fvg = smc.smc.fvg(df_smc)
        print(f"Fair Value Gaps (FVG) detected: {len(fvg[fvg['FVG'] != 0])}")
        print("✅ smartmoneyconcepts & zigzag SUCCESS")
    except Exception as e:
        print(f"❌ smartmoneyconcepts/zigzag FAILED: {e}")

    # 4. Test pyharmonics
    print("\n[3/3] Testing pyharmonics...")
    try:
        from pyharmonics.search import HarmonicSearch
        # pyharmonics requires a Technicals object for data with symbol and interval
        chart = Technicals(df, 'BTCUSDT', '1d')
        search = HarmonicSearch(chart)
        search.search()
        print(f"Pyharmonics search completed. Chart data points: {len(chart.df)}")
        print("✅ pyharmonics SUCCESS")
    except Exception as e:
        print(f"❌ pyharmonics FAILED: {e}")

    print("\n--- All Tests Completed ---")

if __name__ == "__main__":
    test_indicators()
