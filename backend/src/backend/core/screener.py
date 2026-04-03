from __future__ import annotations

import json
import logging
import ssl
import urllib.request
from typing import List

import pandas as pd

from backend.core.market_data import get_bars, get_chips
from backend.core.market_data.symbols import normalize_symbol
from backend.core.technical_engine import (
    build_technical_analysis,
    get_expression_definitions,
    get_indicator_definitions,
    load_analysis_config,
)
from backend.models import ScreenerResult

logger = logging.getLogger(__name__)


def _fetch_twse_snapshot() -> list[dict]:
    """Fetch today's after-market snapshot from TWSE OpenAPI."""
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, context=context, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        logger.error("Error fetching TWSE data: %s", e)
        return []


def _net_buy_streak(rows: list, field_name: str) -> int:
    """Count consecutive net buy (positive) or sell (negative) days."""
    streak = 0
    direction: int | None = None
    for row in reversed(rows):
        value = getattr(row, field_name, None)
        if value is None or value == 0:
            break
        current = 1 if value > 0 else -1
        if direction is None:
            direction = current
        if current != direction:
            break
        streak += 1
    if direction is None:
        return 0
    return streak * direction


def _margin_trend(rows: list) -> str:
    balances = [r.margin_balance for r in rows if r.margin_balance is not None]
    if len(balances) < 2:
        return ""
    current = balances[-1]
    baseline = balances[-6] if len(balances) >= 6 else balances[0]
    if baseline <= 0:
        return ""
    change_pct = (current - baseline) / baseline * 100
    if change_pct > 5:
        return "INCREASING"
    if change_pct < -5:
        return "DECREASING"
    return "STABLE"


def _enrich_result(result: ScreenerResult) -> ScreenerResult:
    """Add technical indicators and chips data to a screener result."""
    symbol = normalize_symbol(result.symbol)
    try:
        bars = get_bars(symbol, lookback_days=120)
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
            result.rsi_14 = vals.get("rsi_14")
            result.adx_14 = vals.get("adx_14")
            result.volume_ratio_20 = vals.get("volume_ratio_20")
            result.bb_position_ratio = vals.get("bb_position_ratio")
            for names in analysis.triggers.values():
                result.triggers.extend(names)
    except Exception as e:
        logger.debug("Technical enrichment failed for %s: %s", result.symbol, e)

    try:
        chips = get_chips(symbol, lookback_days=20)
        if chips:
            result.foreign_net_days = _net_buy_streak(chips, "foreign_net")
            result.trust_net_days = _net_buy_streak(chips, "trust_net")
            result.margin_trend = _margin_trend(chips)
    except Exception as e:
        logger.debug("Chips enrichment failed for %s: %s", result.symbol, e)

    return result


def run_momentum_screener(
    limit: int = 30,
    *,
    min_trade_value: float = 1_000_000_000,
    enrich: bool = True,
    enrich_top_n: int = 30,
) -> List[ScreenerResult]:
    """
    Momentum screener for Taiwan equities.

    Filters:
      - 4-digit ordinary stocks only (no ETF, warrants)
      - Trade value > min_trade_value (default 1B TWD)
      - Positive daily change (收紅)

    Enrichment (when enrich=True):
      - Technical indicators (RSI, ADX, volume ratio, BB position)
      - Chips data (foreign/trust net buy streak, margin trend)
      - Expression triggers from technical_config.yaml

    Sorted by trade value descending (strongest market consensus first).
    """
    data = _fetch_twse_snapshot()
    results: List[ScreenerResult] = []
    for item in data:
        code = item.get("Code", "")
        if len(code) != 4:
            continue
        try:
            trade_value = float(item.get("TradeValue", 0))
            change = float(item.get("Change", 0))
            close = float(item.get("ClosingPrice", 0))
            prev_close = close - change if close and change else 0
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        except (ValueError, ZeroDivisionError):
            continue

        if trade_value > min_trade_value and change > 0:
            results.append(
                ScreenerResult(
                    symbol=code,
                    name=item.get("Name", ""),
                    close=close,
                    change=change,
                    change_pct=round(change_pct, 2),
                    trade_value=trade_value / 1_000_000,
                )
            )

    results.sort(key=lambda x: x.trade_value, reverse=True)
    results = results[:limit]

    if enrich:
        top = results[:enrich_top_n]
        for i, r in enumerate(top):
            logger.info("Enriching %d/%d: %s", i + 1, len(top), r.symbol)
            _enrich_result(r)

    return results
