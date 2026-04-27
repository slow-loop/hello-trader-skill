"""Seed factors for us-momentum strategy.

Each factor takes a feature panel (DataFrame) or single row (Series) and returns
FactorOutput with signed score in [-1, +1].

Convention: positive score = bullish (long bias), negative = bearish (short /
avoid). Score magnitude reflects strength. `triggered` is a bool for whether the
factor is firing in any meaningful way (score magnitude > ~0.2 depending on
factor).

Keep this file single for now. Split by category once > 500 lines or > 20
factors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from market_core.factors.registry import FactorOutput, register


def _clip(x, lo=-1.0, hi=1.0):
    return np.clip(x, lo, hi)


# ---------------------------------------------------------------------------
# Trend / momentum
# ---------------------------------------------------------------------------


@register(
    "trend_strength",
    category="indicator",
    bias_default="long",
    confidence_base=0.6,
    description="Price above SMA50 + SMA200 + ADX > 20. Classic O'Neil trend filter.",
    requires=["close", "sma_50", "sma_200", "adx_14"],
    ic={"sp500_5d": 0.021, "sp500_20d": 0.041},
    ic_sample_size=17300,
    ic_updated_at="2026-04-24",
)
def trend_strength(f):
    """Strong uptrend: price above both MAs + ADX confirms trending regime."""
    above_50 = f["close"] > f["sma_50"]
    above_200 = f["close"] > f["sma_200"]
    adx = f["adx_14"].fillna(0)

    # Score: scale ADX (20-40) to (0-1), boost if both MAs hold, penalty if broken
    adx_score = _clip((adx - 20.0) / 20.0, 0.0, 1.0)
    ma_score = above_50.astype(float) * 0.4 + above_200.astype(float) * 0.6
    score = adx_score * ma_score * np.sign(ma_score)
    # Negative case: below both MAs with ADX trending down
    bear = (~above_50 & ~above_200) & (adx > 20)
    score = np.where(bear, -adx_score, score)

    triggered = (np.abs(score) > 0.3)
    return FactorOutput(
        triggered=triggered,
        score=score,
        bias="long",
        confidence=0.6,
        notes="trend_strength",
    )


@register(
    "breakout_20d",
    category="pattern",
    bias_default="long",
    confidence_base=0.65,
    description="New 20-day high on above-average volume.",
    requires=["is_new_20d_high", "volume_ratio_20", "close", "sma_20"],
)
def breakout_20d(f):
    """New 20-day high + volume ratio ≥ 1.5x avg + price above 20SMA."""
    is_high = f["is_new_20d_high"].astype(bool)
    vol_ok = f["volume_ratio_20"].fillna(0) >= 1.5
    above = f["close"] > f["sma_20"]
    firing = is_high & vol_ok & above
    # Score scales with volume surge intensity, cap 1.0
    vol_intensity = _clip((f["volume_ratio_20"].fillna(0) - 1.0) / 2.0, 0.0, 1.0)
    score = np.where(firing, 0.4 + 0.6 * vol_intensity, 0.0)
    return FactorOutput(
        triggered=firing,
        score=score,
        bias="long",
        confidence=0.65,
        notes="breakout_20d",
    )


@register(
    "pullback_to_20ma",
    category="pattern",
    bias_default="long",
    confidence_base=0.55,
    description="Strong prior uptrend + retest of 20SMA on declining volume.",
    requires=["ret_20d", "close", "sma_20", "volume_ratio_20", "sma_50"],
)
def pullback_to_20ma(f):
    """Trailing +10% 20d return, price within ±2% of 20SMA, volume < avg."""
    strong_prior = f["ret_20d"].fillna(0) > 0.10
    dist_pct = (f["close"] / f["sma_20"] - 1.0).abs() * 100
    near_ma = dist_pct < 2.0
    dry_vol = f["volume_ratio_20"].fillna(0) < 1.0
    above_50 = f["close"] > f["sma_50"]
    firing = strong_prior & near_ma & dry_vol & above_50

    # Score higher when prior run was bigger
    momentum_bonus = _clip(f["ret_20d"].fillna(0) / 0.3, 0.0, 1.0)
    score = np.where(firing, 0.4 + 0.4 * momentum_bonus, 0.0)
    return FactorOutput(
        triggered=firing,
        score=score,
        bias="long",
        confidence=0.55,
        notes="pullback_to_20ma",
    )


@register(
    "volume_surge",
    category="volume",
    bias_default="neutral",
    confidence_base=0.45,
    description="Volume ratio > 2x 20-day average. Direction-agnostic attention signal.",
    requires=["volume_ratio_20", "ret_1d"],
)
def volume_surge(f):
    """Unusual volume. Sign follows today's return direction."""
    vol_ratio = f["volume_ratio_20"].fillna(0)
    surging = vol_ratio >= 2.0
    direction = np.sign(f["ret_1d"].fillna(0))
    intensity = _clip((vol_ratio - 1.0) / 3.0, 0.0, 1.0)
    score = np.where(surging, intensity * direction, 0.0)
    return FactorOutput(
        triggered=surging,
        score=score,
        bias="neutral",
        confidence=0.45,
        notes="volume_surge",
    )


# ---------------------------------------------------------------------------
# Mean-reversion / risk flags
# ---------------------------------------------------------------------------


@register(
    "rsi_overbought",
    category="indicator",
    bias_default="short",
    confidence_base=0.4,
    description="RSI14 > 75: exhaustion warning, weak short / scale-down signal.",
    requires=["rsi_14"],
)
def rsi_overbought(f):
    """RSI bloated. Weak negative score, used as caution flag in momentum."""
    rsi = f["rsi_14"].fillna(50)
    triggered = rsi > 75
    # Scale (75-90) to (0 - -0.5)
    score = np.where(triggered, -((rsi - 75.0) / 15.0 * 0.5), 0.0)
    score = _clip(score, -0.5, 0.0)
    return FactorOutput(
        triggered=triggered,
        score=score,
        bias="short",
        confidence=0.4,
        notes="rsi_overbought",
    )


@register(
    "near_52w_high",
    category="pattern",
    bias_default="long",
    confidence_base=0.55,
    description="Within 3% of 52-week high. Leadership proxy.",
    requires=["dist_to_52w_high_pct"],
)
def near_52w_high(f):
    """Classic leadership screen — stocks near all-time/52-week highs."""
    dist = f["dist_to_52w_high_pct"].fillna(-100)
    triggered = dist >= -3.0
    score = np.where(triggered, _clip((dist + 3.0) / 3.0 * 0.5 + 0.3, 0.0, 0.8), 0.0)
    return FactorOutput(
        triggered=triggered,
        score=score,
        bias="long",
        confidence=0.55,
        notes="near_52w_high",
    )


# ---------------------------------------------------------------------------
# Regime (runs on benchmark series, not per-stock)
# ---------------------------------------------------------------------------


@register(
    "regime_risk_on",
    category="regime",
    bias_default="long",
    confidence_base=0.7,
    description="Benchmark above 20SMA and rising. Applied to SPX/QQQ series.",
    requires=["close", "sma_20", "sma_50", "dist_sma20_pct"],
)
def regime_risk_on(f):
    """Risk-on = benchmark price above SMA20, SMA20 rising, and above SMA50."""
    above_20 = f["close"] > f["sma_20"]
    above_50 = f["close"] > f["sma_50"]
    sma20_rising = f["sma_20"] > f["sma_20"].shift(5)
    firing = above_20 & above_50 & sma20_rising
    dist = f["dist_sma20_pct"].fillna(0)
    score = np.where(firing, _clip(dist / 10.0 + 0.3, 0.3, 1.0), _clip(dist / 10.0, -1.0, 0.0))
    return FactorOutput(
        triggered=firing,
        score=score,
        bias="long",
        confidence=0.7,
        notes="regime_risk_on",
    )
