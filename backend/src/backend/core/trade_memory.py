"""
Trade memory: snapshot, recall similar trades, and performance analytics.

Provides:
  - build_trade_snapshot(): normalized numeric vector for a symbol's current state
  - recall_similar_trades(): find past trades with similar market context
  - compute_performance(): aggregate stats by strategy/tags
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Any

import pandas as pd

from backend.core.market_data import get_bars, get_chips
from backend.core.market_data.symbols import normalize_symbol
from backend.core.market_service import build_overview
from backend.core.screener import _net_buy_streak, _margin_trend
from backend.core.technical_engine import (
    build_technical_analysis,
    get_expression_definitions,
    get_indicator_definitions,
    load_analysis_config,
)

logger = logging.getLogger(__name__)

# Keys stored in the snapshot vector — all numeric, normalized, cross-stock comparable
SNAPSHOT_KEYS = [
    # Market environment
    "taiex_above_ma20",
    "taiex_change_pct_5d",
    # Technical (0-100 or ratio scale)
    "rsi_14",
    "adx_14",
    "bb_position_ratio",
    "stoch_k",
    "volume_ratio_20",
    "price_vs_sma20_pct",
    "price_vs_sma50_pct",
    "atr_pct",
    "macd_histogram_sign",
    # Chips
    "foreign_net_days",
    "trust_net_days",
    "margin_change_pct",
]


def build_trade_snapshot(symbol: str) -> dict[str, float]:
    """
    Build a normalized numeric snapshot of a symbol's current market state.

    All values are numeric and cross-stock comparable, suitable for
    similarity search via Euclidean distance.
    """
    normalized = normalize_symbol(symbol)
    snapshot: dict[str, float] = {}

    # -- Market environment --
    try:
        overview = build_overview()
        market = overview.get("market", {})
        snapshot["taiex_above_ma20"] = 1.0 if market.get("trend") == "ABOVE_MA20" else 0.0
        snapshot["taiex_change_pct_5d"] = market.get("change_pct", 0.0) or 0.0
    except Exception:
        snapshot["taiex_above_ma20"] = 0.0
        snapshot["taiex_change_pct_5d"] = 0.0

    # -- Technical indicators --
    try:
        bars = get_bars(normalized, lookback_days=120)
        if bars and len(bars) >= 20:
            df = pd.DataFrame(
                [
                    {
                        "date": b.bar_time,
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "volume": b.volume,
                    }
                    for b in bars
                ]
            ).sort_values("date").reset_index(drop=True)
            if "volume" in df.columns:
                df["volume"] = df["volume"].fillna(0)

            config = load_analysis_config()
            analysis = build_technical_analysis(
                df,
                indicators=get_indicator_definitions(config),
                expressions=get_expression_definitions(config),
            )
            vals = analysis.values
            snapshot["rsi_14"] = _safe_float(vals.get("rsi_14"), 50.0)
            snapshot["adx_14"] = _safe_float(vals.get("adx_14"), 0.0)
            snapshot["bb_position_ratio"] = _safe_float(vals.get("bb_position_ratio"), 0.5)
            snapshot["stoch_k"] = _safe_float(vals.get("stoch_k"), 50.0)
            snapshot["volume_ratio_20"] = _safe_float(vals.get("volume_ratio_20"), 1.0)
            snapshot["atr_pct"] = _safe_float(vals.get("atr_14_pct"), 0.0)

            # Price vs moving averages (percentage)
            close = _safe_float(vals.get("close"), 0)
            sma20 = _safe_float(vals.get("sma_20"), 0)
            sma50 = _safe_float(vals.get("sma_50"), 0)
            snapshot["price_vs_sma20_pct"] = (
                round((close - sma20) / sma20 * 100, 2) if sma20 > 0 else 0.0
            )
            snapshot["price_vs_sma50_pct"] = (
                round((close - sma50) / sma50 * 100, 2) if sma50 > 0 else 0.0
            )

            # MACD histogram sign: +1, -1, 0
            macd_hist = vals.get("macd_histogram")
            if macd_hist is not None and isinstance(macd_hist, (int, float)):
                snapshot["macd_histogram_sign"] = 1.0 if macd_hist > 0 else (-1.0 if macd_hist < 0 else 0.0)
            else:
                snapshot["macd_histogram_sign"] = 0.0
    except Exception as e:
        logger.debug("Technical snapshot failed for %s: %s", symbol, e)

    # -- Chips --
    try:
        chips = get_chips(normalized, lookback_days=20)
        if chips:
            snapshot["foreign_net_days"] = float(_net_buy_streak(chips, "foreign_net"))
            snapshot["trust_net_days"] = float(_net_buy_streak(chips, "trust_net"))
            # Margin change %
            balances = [r.margin_balance for r in chips if r.margin_balance is not None]
            if len(balances) >= 2:
                baseline = balances[-6] if len(balances) >= 6 else balances[0]
                if baseline > 0:
                    snapshot["margin_change_pct"] = round(
                        (balances[-1] - baseline) / baseline * 100, 2
                    )
    except Exception as e:
        logger.debug("Chips snapshot failed for %s: %s", symbol, e)

    # Fill missing keys with defaults
    defaults = {
        "rsi_14": 50.0, "adx_14": 0.0, "bb_position_ratio": 0.5,
        "stoch_k": 50.0, "volume_ratio_20": 1.0, "price_vs_sma20_pct": 0.0,
        "price_vs_sma50_pct": 0.0, "atr_pct": 0.0, "macd_histogram_sign": 0.0,
        "foreign_net_days": 0.0, "trust_net_days": 0.0, "margin_change_pct": 0.0,
        "taiex_above_ma20": 0.0, "taiex_change_pct_5d": 0.0,
    }
    for k, default in defaults.items():
        snapshot.setdefault(k, default)

    return snapshot


# -- Normalization weights for distance calculation --
# Fields with larger natural ranges get scaled down so they contribute equally.
_WEIGHTS: dict[str, float] = {
    "rsi_14": 1.0 / 100,       # 0-100
    "adx_14": 1.0 / 100,       # 0-100
    "bb_position_ratio": 1.0,   # 0-1
    "stoch_k": 1.0 / 100,      # 0-100
    "volume_ratio_20": 1.0 / 5, # typically 0-5
    "price_vs_sma20_pct": 1.0 / 20,  # typically -20 to +20
    "price_vs_sma50_pct": 1.0 / 30,
    "atr_pct": 1.0 / 10,       # typically 0-10
    "macd_histogram_sign": 1.0, # -1, 0, 1
    "foreign_net_days": 1.0 / 10,  # typically -10 to +10
    "trust_net_days": 1.0 / 10,
    "margin_change_pct": 1.0 / 20,
    "taiex_above_ma20": 1.0,    # 0 or 1
    "taiex_change_pct_5d": 1.0 / 10,
}


def _weighted_distance(a: dict[str, float], b: dict[str, float]) -> float:
    """Weighted Euclidean distance between two snapshot vectors."""
    total = 0.0
    for key in SNAPSHOT_KEYS:
        va = a.get(key, 0.0)
        vb = b.get(key, 0.0)
        w = _WEIGHTS.get(key, 1.0)
        total += (w * (va - vb)) ** 2
    return math.sqrt(total)


def recall_similar_trades(
    current_snapshot: dict[str, float],
    trade_history: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """
    Find past trades whose market_snapshot is most similar to current_snapshot.

    Returns top_k trades sorted by similarity (closest first), each augmented with
    a 'similarity_distance' field.
    """
    scored = []
    for trade in trade_history:
        past_snapshot = trade.get("market_snapshot")
        if not past_snapshot or not isinstance(past_snapshot, dict):
            continue
        dist = _weighted_distance(current_snapshot, past_snapshot)
        scored.append((dist, trade))

    scored.sort(key=lambda x: x[0])
    results = []
    for dist, trade in scored[:top_k]:
        entry = dict(trade)
        entry["similarity_distance"] = round(dist, 4)
        results.append(entry)
    return results


def compute_performance(
    trade_history: list[dict[str, Any]],
    group_by: str = "strategy",
) -> dict[str, dict[str, Any]]:
    """
    Compute performance stats grouped by strategy or tag.

    Args:
        trade_history: list of trade records from ledger
        group_by: "strategy" or "tags"

    Returns dict like:
        {
            "momentum": {"trades": 10, "wins": 7, "win_rate": 0.7, "avg_pnl_r": 1.3, ...},
            "satellite": {...},
        }
    """
    groups: dict[str, list[dict]] = defaultdict(list)

    for trade in trade_history:
        if trade.get("action") != "SELL":
            continue
        if "pnl" not in trade:
            continue

        if group_by == "tags":
            tags = trade.get("tags", [])
            if not tags:
                tags = ["untagged"]
            for tag in tags:
                groups[tag].append(trade)
        else:
            strategy = trade.get("strategy", "unknown")
            groups[strategy].append(trade)

    result = {}
    for key, trades in groups.items():
        pnls = [t["pnl"] for t in trades]
        pnl_rs = [t["pnl_r"] for t in trades if "pnl_r" in t]
        wins = sum(1 for p in pnls if p > 0)
        losses = sum(1 for p in pnls if p <= 0)
        total = len(pnls)

        result[key] = {
            "trades": total,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / total, 2) if total > 0 else 0,
            "total_pnl": round(sum(pnls), 0),
            "avg_pnl": round(sum(pnls) / total, 0) if total > 0 else 0,
            "avg_pnl_r": round(sum(pnl_rs) / len(pnl_rs), 2) if pnl_rs else None,
            "best_trade": round(max(pnls), 0) if pnls else 0,
            "worst_trade": round(min(pnls), 0) if pnls else 0,
        }

    return result


def _safe_float(value: Any, default: float) -> float:
    if value is None:
        return default
    try:
        v = float(value)
        return default if math.isnan(v) else v
    except (TypeError, ValueError):
        return default
