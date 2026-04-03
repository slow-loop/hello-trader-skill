"""Evaluate watchlist trigger_conditions and invalidation_conditions against live data."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from skill_tw_trader.core.account_paths import WATCHLIST_FILE
from skill_tw_trader.core.market_calendar import get_twse_market_status
from skill_tw_trader.core.market_data import get_bars, get_chips, get_quote
from skill_tw_trader.core.market_data.symbols import normalize_symbol
from skill_tw_trader.core.technical_engine import (
    ExpressionContext,
    ScalarValue,
    build_technical_analysis,
    get_expression_definitions,
    get_indicator_definitions,
    load_analysis_config,
    _evaluate_expression,
)
from skill_tw_trader.core.screener import _net_buy_streak, _margin_trend

import pandas as pd

logger = logging.getLogger(__name__)


def _build_eval_context(symbol: str) -> ExpressionContext:
    """Build a full expression context for a symbol (technical + chips)."""
    normalized = normalize_symbol(symbol)
    bars = get_bars(normalized, lookback_days=120)
    if not bars or len(bars) < 20:
        raise ValueError(f"Insufficient bar data for {symbol}")

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
    context = dict(analysis.values)

    # Add chips-derived values
    try:
        chips = get_chips(normalized, lookback_days=20)
        if chips:
            context["foreign_net_days"] = _net_buy_streak(chips, "foreign_net")
            context["trust_net_days"] = _net_buy_streak(chips, "trust_net")
            margin = _margin_trend(chips)
            context["margin_increasing"] = margin == "INCREASING"
            context["margin_decreasing"] = margin == "DECREASING"
    except Exception as e:
        logger.debug("Chips fetch failed for %s: %s", symbol, e)

    return context


def _eval_conditions(conditions: list[str], context: ExpressionContext) -> list[dict]:
    """Evaluate a list of expression strings and return results."""
    results = []
    for expr in conditions:
        try:
            value = _evaluate_expression(expr, context)
            results.append({"expr": expr, "result": bool(value), "error": None})
        except Exception as e:
            results.append({"expr": expr, "result": None, "error": str(e)})
    return results


def check_watchlist_triggers(watchlist_path: Path | None = None) -> list[dict]:
    """
    Check all watchlist items with trigger_conditions / invalidation_conditions.

    Returns a list of dicts, one per watchlist item:
    {
        "symbol": "2313.TW",
        "status": "watch",
        "trigger_met": True/False,
        "trigger_results": [...],
        "invalidation_met": True/False,
        "invalidation_results": [...],
        "context_snapshot": {"close": 275, "rsi_14": 68, ...},
    }
    """
    path = watchlist_path or WATCHLIST_FILE
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        watchlist = yaml.safe_load(f) or []

    market_status = get_twse_market_status()
    results = []
    for item in watchlist:
        symbol = item.get("symbol", "")
        trigger_conds = item.get("trigger_conditions", [])
        invalidation_conds = item.get("invalidation_conditions", [])
        trigger_price = item.get("trigger_price")
        invalidation_price = item.get("invalidation_price")

        if not trigger_conds and not invalidation_conds and trigger_price is None and invalidation_price is None:
            continue

        entry: dict = {
            "symbol": symbol,
            "status": item.get("status", "watch"),
            "trigger_met": False,
            "trigger_results": [],
            "invalidation_met": False,
            "invalidation_results": [],
            "context_snapshot": {},
        }

        try:
            context = _build_eval_context(symbol)
            live_price = None
            if market_status["is_open"]:
                try:
                    quote = get_quote(symbol)
                    live_price = quote.price
                except Exception as e:
                    logger.debug("Quote fetch failed for %s: %s", symbol, e)

            trigger_price_value = live_price if live_price is not None else context.get("close")
            close_price = context.get("close")
            # Only expose key values for snapshot
            snapshot_keys = [
                "close", "change_pct", "rsi_14", "adx_14", "volume_ratio_20",
                "bb_position_ratio", "stoch_k", "atr_14_pct",
                "foreign_net_days", "trust_net_days",
            ]
            entry["context_snapshot"] = {
                k: round(v, 2) if isinstance(v, float) else v
                for k, v in context.items()
                if k in snapshot_keys and v is not None
            }
            if live_price is not None:
                entry["context_snapshot"]["live_price"] = round(live_price, 2)

            if trigger_conds:
                trig_results = _eval_conditions(trigger_conds, context)
                entry["trigger_results"] = trig_results
                entry["trigger_met"] = all(
                    r["result"] is True for r in trig_results
                )
            elif trigger_price is not None:
                if trigger_price_value is not None:
                    met = float(trigger_price_value) >= float(trigger_price)
                    price_label = "live_price" if live_price is not None else "close"
                    entry["trigger_results"] = [{"expr": f"{price_label} >= {trigger_price}", "result": met, "error": None}]
                    entry["trigger_met"] = met

            if invalidation_conds:
                inv_results = _eval_conditions(invalidation_conds, context)
                entry["invalidation_results"] = inv_results
                # Invalidation: ANY condition being true means thesis is broken
                entry["invalidation_met"] = any(
                    r["result"] is True for r in inv_results
                )
            elif invalidation_price is not None:
                if close_price is not None:
                    met = float(close_price) <= float(invalidation_price)
                    entry["invalidation_results"] = [{"expr": f"close <= {invalidation_price}", "result": met, "error": None}]
                    entry["invalidation_met"] = met

        except Exception as e:
            entry["error"] = str(e)

        results.append(entry)

    return results
