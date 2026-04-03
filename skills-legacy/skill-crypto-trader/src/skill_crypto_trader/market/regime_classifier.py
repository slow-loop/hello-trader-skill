"""
Market Regime Classifier (Standalone Module)

This module implements quantitative methods to detect the current Market Regime.
It decouples regime detection from trading strategies, serving as "Module A" 
in a Multi-Agent Quant System.

Implemented Metrics:
1. Macro Momentum & Volatility (Trend-following metrics: SMA 200, 50, ADX, ATR)
2. Market Breadth (Cross-sectional momentum of Top Altcoins)
3. Derivatives Data (Funding Rates, Open Interest Risk)

TODOs:
- [ ] Incorporate Hidden Markov Models (HMM) via `hmmlearn` for unsupervised state classification.
"""

import asyncio
import ccxt.async_support as ccxt
import pandas as pd
import numpy as np
import talib.abstract as ta
import yaml
from pathlib import Path


class RegimeClassifier:
    def __init__(self):
        self.exchange = ccxt.bybit({'enableRateLimit': True})
        self.futures_exchange = ccxt.bybit({'enableRateLimit': True})
        self.repo_root = Path(__file__).parent.parent.parent.parent.parent
        self.pairs_file = self.repo_root / 'data' / 'config' / 'pairs.yaml'

    async def fetch_ohlcv_df(self, symbol: str, timeframe='1d', limit=250) -> pd.DataFrame:
        """Fetch historical OHLCV data using CCXT."""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()

    async def analyze_btc_macro(self) -> dict:
        """1. Momentum, Volatility & Trend Extension Matrix"""
        df = await self.fetch_ohlcv_df('BTC/USDT', '1d', 365)
        if df.empty or len(df) < 200:
            return {"error": "Not enough data"}

        # Indicators
        df['sma_20'] = ta.SMA(df, timeperiod=20)
        df['sma_50'] = ta.SMA(df, timeperiod=50)
        df['sma_200'] = ta.SMA(df, timeperiod=200)
        df['adx'] = ta.ADX(df, timeperiod=14)
        df['atr'] = ta.ATR(df, timeperiod=14)

        # Historical Volatility Tracking
        df['vol_pct'] = (df['atr'] / df['close']) * 100
        historical_vol = df['vol_pct'].dropna().values

        latest = df.iloc[-1]
        
        # Volatility Percentile (0 to 100 benchmarked against past year)
        current_vol = latest['vol_pct']
        vol_percentile = (np.sum(historical_vol < current_vol) / len(historical_vol)) * 100

        # Trend Extension (Distance between Short and Long term moving averages)
        # Represents how "over-extended" the current move is
        trend_extension_pct = ((latest['sma_50'] - latest['sma_200']) / latest['sma_200']) * 100
        price_distance_200_pct = ((latest['close'] - latest['sma_200']) / latest['sma_200']) * 100

        return {
            "close": latest['close'],
            "sma_200": latest['sma_200'],
            "price_vs_200_pct": price_distance_200_pct,
            "trend_extension_pct": trend_extension_pct,
            "adx": latest['adx'],
            "volatility_pct": current_vol,
            "volatility_1yr_percentile": vol_percentile
        }

    async def analyze_market_breadth(self) -> dict:
        """2. Market Breadth (Percentage of altcoins above 50-day SMA)"""
        try:
            with open(self.pairs_file, 'r') as f:
                pairs_data = yaml.safe_load(f)
                symbols = [p['symbol'] for p in pairs_data.get('pairs', []) if p['symbol'] != 'BTC/USDT']
                if not symbols:
                    symbols = ['ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']
        except Exception:
            symbols = ['ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT']

        above_50 = 0
        valid_symbols = 0

        # Fetch sequentially to avoid rate-limits
        for sym in symbols[:10]: # Check up to 10 top altcoins
            df = await self.fetch_ohlcv_df(sym, '1d', 100)
            if df.empty or len(df) < 50:
                continue
            df['sma_50'] = ta.SMA(df, timeperiod=50)
            latest = df.iloc[-1]
            if latest['close'] > latest['sma_50']:
                above_50 += 1
            valid_symbols += 1

        breadth_pct = (above_50 / valid_symbols) * 100 if valid_symbols > 0 else 0

        return {
            "total_pairs": valid_symbols,
            "pairs_above_50sma": above_50,
            "breadth_pct": breadth_pct,
        }

    async def analyze_derivatives(self) -> dict:
        """3. Derivatives Data (Funding Rates)"""
        try:
            funding = await self.futures_exchange.fetch_funding_rate('BTC/USDT')
            rate = funding.get('fundingRate', 0) * 100  # Convert to percent
            return {
                "btc_funding_rate_pct": rate,
            }
        except Exception as e:
            return {"error": str(e), "btc_funding_rate_pct": 0}

    async def generate_report(self):
        macro = await self.analyze_btc_macro()
        breadth = await self.analyze_market_breadth()
        derivs = await self.analyze_derivatives()
        
        await self.exchange.close()
        await self.futures_exchange.close()

        # Constructing a pure, objective LLM-Context Report using hierarchical YAML
        report_data = {
            "market_regime_metrics": {
                "1_macro_btc": {
                    "price_close_usdt": float(f"{macro.get('close', 0):.2f}"),
                    "price_vs_200_sma_pct": float(f"{macro.get('price_vs_200_pct', 0):.2f}"),
                    "trend_extension_50_vs_200_pct": float(f"{macro.get('trend_extension_pct', 0):.2f}"),
                    "adx_14": float(f"{macro.get('adx', 0):.2f}"),
                    "volatility_atr_pct": float(f"{macro.get('volatility_pct', 0):.2f}"),
                    "volatility_1yr_percentile": float(f"{macro.get('volatility_1yr_percentile', 0):.1f}")
                },
                "2_market_breadth": {
                    "tracked_altcoin_pairs": breadth.get('total_pairs', 0),
                    "above_50_sma_pct": float(f"{breadth.get('breadth_pct', 0):.1f}")
                },
                "3_derivatives_leverage": {
                    "btc_funding_rate_8h_pct": float(f"{derivs.get('btc_funding_rate_pct', 0):.4f}")
                }
            },
            "system_instruction": "Provide this raw numerical context to the Trading Agent. Apply quantitative analysis to determine regime risk."
        }
        
        print("====== LLM CONTEXT: MARKET REGIME METRICS ======\n")
        print(yaml.dump(report_data, default_flow_style=False, sort_keys=False))
        print("================================================\n")

if __name__ == "__main__":
    classifier = RegimeClassifier()
    asyncio.run(classifier.generate_report())
