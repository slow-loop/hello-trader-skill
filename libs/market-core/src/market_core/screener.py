from __future__ import annotations

from datetime import date, timedelta
import json
import logging
import os
import ssl
import urllib.request
from typing import Any

import pandas as pd

from market_core.market import build_analysis
from market_core.models import MarketRuntimeConfig, ScreenerResponse, ScreenerResult
from market_core.policies import MarketProfile, get_market_profile, normalize_symbol

logger = logging.getLogger(__name__)

_TWSE_SNAPSHOT_URL = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
_INVESTOR_FIELDS = {
    "Foreign_Investor": "foreign_net",
    "Investment_Trust": "trust_net",
}
_SCREENER_REGISTRY: dict[tuple[str, str], str] = {
    ("tw_equity", "momentum"): "run_tw_momentum_screener",
}
_finmind_loader: Any | None = None


def run_screener(
    config: MarketRuntimeConfig,
    profile: MarketProfile,
    *,
    strategy: str = "momentum",
    limit: int = 30,
    enrich: bool = True,
) -> ScreenerResponse:
    runner_name = _SCREENER_REGISTRY.get((profile.id, strategy))
    if runner_name:
        runner = globals()[runner_name]
        return runner(config, profile, limit=limit, enrich=enrich)
    raise ValueError(f"unsupported screener strategy '{strategy}' for market profile '{profile.id}'")


def run_tw_momentum_screener(
    config: MarketRuntimeConfig,
    profile: MarketProfile,
    *,
    limit: int = 30,
    min_trade_value: float = 1_000_000_000,
    enrich: bool = True,
) -> ScreenerResponse:
    data = _fetch_twse_snapshot()
    items: list[ScreenerResult] = []
    for item in data:
        code = str(item.get("Code", "")).strip()
        if len(code) != 4 or not code.isdigit() or code.startswith("00"):
            continue

        try:
            trade_value = _parse_number(item.get("TradeValue"))
            change = _parse_number(item.get("Change"))
            close = _parse_number(item.get("ClosingPrice"))
            prev_close = close - change if close and change else 0
            change_pct = (change / prev_close * 100) if prev_close > 0 else 0
        except (TypeError, ValueError, ZeroDivisionError):
            continue

        if trade_value <= min_trade_value or change <= 0:
            continue

        items.append(
            ScreenerResult(
                symbol=code,
                name=str(item.get("Name", "")).strip(),
                close=close,
                change=change,
                change_pct=round(change_pct, 2),
                trade_value=round(trade_value / 1_000_000, 2),
            )
        )

    items.sort(key=lambda r: r.trade_value, reverse=True)
    items = items[:limit]

    if enrich:
        for r in items:
            _enrich_tw_result(r, config, profile)

    return ScreenerResponse(strategy="momentum", market_profile=profile.id, items=items)


def _fetch_twse_snapshot() -> list[dict]:
    try:
        request = urllib.request.Request(
            _TWSE_SNAPSHOT_URL,
            headers={"User-Agent": "market-core-screener/1.0"},
        )
        context = ssl._create_unverified_context()
        with urllib.request.urlopen(request, context=context, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        logger.warning("twse snapshot fetch failed: %s", exc)
        return []


def _parse_number(value: object) -> float:
    if value is None:
        raise ValueError("missing numeric value")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "")
    if not text:
        raise ValueError("missing numeric value")
    return float(text)


def _enrich_tw_result(
    item: ScreenerResult,
    config: MarketRuntimeConfig,
    profile: MarketProfile,
) -> None:
    try:
        item.analysis = build_analysis(item.symbol, config, profile)
    except Exception as exc:
        logger.debug("analysis enrichment failed for %s: %s", item.symbol, exc)

    chips = _try_fetch_tw_chips(item.symbol)
    if chips:
        item.chips = chips


def _try_fetch_tw_chips(symbol: str) -> dict[str, int | str]:
    api_key = os.getenv("FINMIND_API_KEY")
    if not api_key:
        return {}

    try:
        loader = _get_finmind_loader(api_key)
        stock_id = normalize_symbol(symbol, get_market_profile("tw_equity")).removesuffix(".TW").removesuffix(".TWO")
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        investor_df = loader.taiwan_stock_institutional_investors(
            stock_id=stock_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        margin_df = loader.taiwan_stock_margin_purchase_short_sale(
            stock_id=stock_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
    except Exception as exc:
        logger.debug("chips enrichment failed for %s: %s", symbol, exc)
        return {}

    result: dict[str, int | str] = {}

    if not investor_df.empty:
        investor_df = investor_df[investor_df["name"].isin(_INVESTOR_FIELDS)].copy()
        if not investor_df.empty:
            investor_df["net"] = investor_df["buy"] - investor_df["sell"]
            investor_df["field"] = investor_df["name"].map(_INVESTOR_FIELDS)
            pivot = (
                investor_df.pivot_table(index="date", columns="field", values="net", aggfunc="last")
                .reset_index()
                .sort_values("date")
            )
            rows = pivot.to_dict("records")
            foreign_days = _net_buy_streak(rows, "foreign_net")
            trust_days = _net_buy_streak(rows, "trust_net")
            if foreign_days:
                result["foreign_net_days"] = foreign_days
            if trust_days:
                result["trust_net_days"] = trust_days

    if not margin_df.empty and "MarginPurchaseTodayBalance" in margin_df.columns:
        balances = (
            margin_df[["date", "MarginPurchaseTodayBalance"]]
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
            ["MarginPurchaseTodayBalance"]
            .tolist()
        )
        margin_trend = _margin_trend(balances)
        if margin_trend:
            result["margin_trend"] = margin_trend

    return result


def _get_finmind_loader(api_key: str):
    global _finmind_loader
    if _finmind_loader is not None:
        return _finmind_loader
    from FinMind.data import DataLoader

    loader = DataLoader()
    loader.login_by_token(api_token=api_key)
    _finmind_loader = loader
    return loader


def _net_buy_streak(rows: list[dict], field_name: str) -> int:
    streak = 0
    direction: int | None = None
    for row in reversed(rows):
        value = row.get(field_name)
        if value is None or pd.isna(value) or value == 0:
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


def _margin_trend(balances: list[float]) -> str:
    valid = [float(b) for b in balances if b is not None and not pd.isna(b)]
    if len(valid) < 2:
        return ""
    current = valid[-1]
    baseline = valid[-6] if len(valid) >= 6 else valid[0]
    if baseline <= 0:
        return ""
    change_pct = (current - baseline) / baseline * 100
    if change_pct > 5:
        return "INCREASING"
    if change_pct < -5:
        return "DECREASING"
    return "STABLE"
