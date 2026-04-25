"""Feature engine: OHLC DataFrame -> feature panel (vectorized).

Inputs:
    df: DataFrame indexed by date, columns at minimum: open, high, low, close,
        volume. Single-symbol. For multi-symbol, call per-symbol and concat.

Outputs:
    Feature panel with original OHLCV + derived indicators + returns + levels.
    All columns are float; index preserved.

The feature set is opinionated to cover what seed factors in factors.py need.
Keep column names stable — factors and strategy YAML reference them directly.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta as ta

FEATURE_COLUMNS: list[str] = [
    # OHLCV
    "open", "high", "low", "close", "volume",
    # Returns
    "ret_1d", "ret_5d", "ret_20d", "ret_60d", "ret_120d",
    # Moving averages
    "sma_10", "sma_20", "sma_50", "sma_200",
    "ema_20", "ema_50",
    # Distance to SMA (as pct)
    "dist_sma20_pct", "dist_sma50_pct", "dist_sma200_pct",
    # Trend strength
    "adx_14", "di_plus_14", "di_minus_14",
    # Momentum oscillators
    "rsi_14",
    "macd", "macd_signal", "macd_hist",
    # Volatility
    "atr_14", "atr_14_pct",
    "bb_upper", "bb_mid", "bb_lower", "bb_width_pct",
    # Volume
    "vol_sma_20", "volume_ratio_20",
    # Levels
    "high_20d", "low_20d", "high_52w", "low_52w",
    "dist_to_52w_high_pct", "dist_to_52w_low_pct",
    # Breakout flags (as 0/1 floats for vectorized use)
    "is_new_20d_high", "is_new_52w_high",
]


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute the full feature set for a single-symbol OHLCV frame."""
    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"missing OHLCV columns: {missing}")
    if len(df) < 30:
        raise ValueError(f"need at least 30 bars, got {len(df)}")

    f = df.copy()
    close = f["close"]
    high = f["high"]
    low = f["low"]
    vol = f["volume"]

    # Returns
    f["ret_1d"] = close.pct_change(1)
    f["ret_5d"] = close.pct_change(5)
    f["ret_20d"] = close.pct_change(20)
    f["ret_60d"] = close.pct_change(60)
    f["ret_120d"] = close.pct_change(120)

    # Moving averages
    f["sma_10"] = ta.sma(close, length=10)
    f["sma_20"] = ta.sma(close, length=20)
    f["sma_50"] = ta.sma(close, length=50)
    f["sma_200"] = ta.sma(close, length=200)
    f["ema_20"] = ta.ema(close, length=20)
    f["ema_50"] = ta.ema(close, length=50)

    f["dist_sma20_pct"] = (close / f["sma_20"] - 1.0) * 100
    f["dist_sma50_pct"] = (close / f["sma_50"] - 1.0) * 100
    f["dist_sma200_pct"] = (close / f["sma_200"] - 1.0) * 100

    # Trend strength (ADX)
    adx = ta.adx(high, low, close, length=14)
    if adx is not None and not adx.empty:
        cols = list(adx.columns)
        f["adx_14"] = adx[cols[0]]
        f["di_plus_14"] = adx[cols[1]] if len(cols) > 1 else np.nan
        f["di_minus_14"] = adx[cols[2]] if len(cols) > 2 else np.nan
    else:
        f["adx_14"] = f["di_plus_14"] = f["di_minus_14"] = np.nan

    # Momentum
    f["rsi_14"] = ta.rsi(close, length=14)
    macd_df = ta.macd(close, fast=12, slow=26, signal=9)
    if macd_df is not None and not macd_df.empty:
        mcols = list(macd_df.columns)
        f["macd"] = macd_df[mcols[0]]
        f["macd_signal"] = macd_df[mcols[2]] if len(mcols) > 2 else macd_df[mcols[1]]
        f["macd_hist"] = macd_df[mcols[1]]
    else:
        f["macd"] = f["macd_signal"] = f["macd_hist"] = np.nan

    # Volatility
    atr = ta.atr(high, low, close, length=14)
    f["atr_14"] = atr if atr is not None else np.nan
    f["atr_14_pct"] = (f["atr_14"] / close) * 100

    bb = ta.bbands(close, length=20, std=2.0)
    if bb is not None and not bb.empty:
        lower_col = next((c for c in bb.columns if "BBL" in c), None)
        mid_col = next((c for c in bb.columns if "BBM" in c), None)
        upper_col = next((c for c in bb.columns if "BBU" in c), None)
        f["bb_upper"] = bb[upper_col] if upper_col else np.nan
        f["bb_mid"] = bb[mid_col] if mid_col else np.nan
        f["bb_lower"] = bb[lower_col] if lower_col else np.nan
        f["bb_width_pct"] = (f["bb_upper"] - f["bb_lower"]) / close * 100
    else:
        f["bb_upper"] = f["bb_mid"] = f["bb_lower"] = f["bb_width_pct"] = np.nan

    # Volume
    f["vol_sma_20"] = vol.rolling(20, min_periods=10).mean()
    f["volume_ratio_20"] = vol / f["vol_sma_20"]

    # Levels
    f["high_20d"] = high.rolling(20, min_periods=10).max()
    f["low_20d"] = low.rolling(20, min_periods=10).min()
    f["high_52w"] = high.rolling(252, min_periods=60).max()
    f["low_52w"] = low.rolling(252, min_periods=60).min()
    f["dist_to_52w_high_pct"] = (close / f["high_52w"] - 1.0) * 100
    f["dist_to_52w_low_pct"] = (close / f["low_52w"] - 1.0) * 100

    # Breakout flags
    # "new 20d high" = today's high strictly above prior 20d high
    prior_20d_high = high.shift(1).rolling(20, min_periods=10).max()
    prior_52w_high = high.shift(1).rolling(252, min_periods=60).max()
    f["is_new_20d_high"] = (high > prior_20d_high).astype(float)
    f["is_new_52w_high"] = (high > prior_52w_high).astype(float)

    return f


def compute_multi_symbol_panel(ohlc_by_symbol: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Compute features for many symbols → MultiIndex DataFrame (date, symbol)."""
    frames = []
    for sym, df in ohlc_by_symbol.items():
        if len(df) < 30:
            continue
        feat = compute_features(df)
        feat = feat.copy()
        feat["symbol"] = sym
        frames.append(feat)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, axis=0)
    out = out.reset_index().set_index(["date", "symbol"]) if "date" in out.columns else out.set_index("symbol", append=True)
    return out.sort_index()
