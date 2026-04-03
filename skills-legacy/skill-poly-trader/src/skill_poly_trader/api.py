from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import MarketSnapshot

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = "skill-poly-trader/0.1"
DEFAULT_EVENT_ORDER = "volume24hr"


def fetch_events(limit: int = 12, offset: int = 0, order: str = DEFAULT_EVENT_ORDER, ascending: bool = False) -> list[dict[str, Any]]:
    params = {
        "active": "true",
        "closed": "false",
        "limit": str(limit),
        "offset": str(offset),
        "order": order,
        "ascending": str(ascending).lower(),
    }
    payload = _fetch_json(f"/events?{urlencode(params)}")
    return payload if isinstance(payload, list) else []


def fetch_market_by_slug(slug: str) -> dict[str, Any] | None:
    items = _fetch_json(f"/markets?{urlencode({'slug': slug})}")
    if isinstance(items, list) and items:
        return items[0]
    return None


def build_event_candidates(limit: int = 12, max_markets_per_event: int = 6) -> list[dict[str, Any]]:
    events = fetch_events(limit=limit)
    candidates: list[dict[str, Any]] = []
    for event in events:
        snapshots = _event_markets_to_snapshots(event, max_markets=max_markets_per_event)
        candidates.append(
            {
                "event_id": str(event.get("id", "")),
                "slug": str(event.get("slug", "") or ""),
                "title": str(event.get("title", "") or "").strip(),
                "category": event.get("category"),
                "end_date": event.get("endDate"),
                "volume_24h": _as_float(event.get("volume24hr")) or 0.0,
                "volume": _as_float(event.get("volume")) or 0.0,
                "liquidity": _as_float(event.get("liquidity")) or 0.0,
                "market_count": len(snapshots),
                "markets": snapshots,
            }
        )
    return candidates


def build_snapshots(limit: int = 12, max_candidates: int = 6) -> list[MarketSnapshot]:
    events = build_event_candidates(limit=limit, max_markets_per_event=max_candidates)
    return [snapshot for event in events for snapshot in event["markets"]]


def market_to_snapshot(market: dict[str, Any]) -> MarketSnapshot | None:
    outcomes = _parse_json_list(market.get("outcomes"))
    prices = _parse_json_list(market.get("outcomePrices"))
    if len(outcomes) != 2 or len(prices) != 2:
        return None

    normalized_outcomes = [str(item).strip().lower() for item in outcomes]
    if normalized_outcomes != ["yes", "no"]:
        return None

    yes_price = _as_float(prices[0])
    no_price = _as_float(prices[1])
    if yes_price is None or no_price is None:
        return None

    volume_24h = _as_float(market.get("volume24hr")) or 0.0
    liquidity = _as_float(market.get("liquidity")) or _as_float(market.get("liquidityNum")) or 0.0
    best_bid = _as_float(market.get("bestBid"))
    best_ask = _as_float(market.get("bestAsk"))
    change_1d = _as_float(market.get("oneDayPriceChange")) or 0.0
    end_date = market.get("endDate")

    return MarketSnapshot(
        market_id=str(market.get("id", "")),
        slug=str(market.get("slug", "")),
        question=str(market.get("question", "")).strip(),
        yes_price=yes_price,
        no_price=no_price,
        volume_24h=volume_24h,
        liquidity=liquidity,
        one_day_price_change=change_1d,
        best_bid=best_bid,
        best_ask=best_ask,
        end_date=end_date,
        days_to_resolution=_days_to_resolution(end_date),
    )


def is_tradeable_snapshot(snapshot: MarketSnapshot) -> bool:
    if not snapshot.market_id or not snapshot.slug or not snapshot.question:
        return False
    if snapshot.yes_price <= 0.03 or snapshot.yes_price >= 0.97:
        return False
    if snapshot.volume_24h < 25_000 or snapshot.liquidity < 25_000:
        return False
    if snapshot.days_to_resolution is not None:
        if snapshot.days_to_resolution < 1 or snapshot.days_to_resolution > 45:
            return False
    return True


def _event_markets_to_snapshots(event: dict[str, Any], max_markets: int) -> list[MarketSnapshot]:
    snapshots: list[MarketSnapshot] = []
    for market in event.get("markets", []):
        snapshot = market_to_snapshot(market)
        if snapshot is None:
            continue
        if not is_tradeable_snapshot(snapshot):
            continue
        snapshots.append(snapshot)
    return snapshots[:max_markets]


def _fetch_json(path: str) -> Any:
    url = f"{GAMMA_API}{path}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    return []


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _days_to_resolution(end_date: str | None) -> int | None:
    if not end_date:
        return None
    try:
        dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
    except ValueError:
        return None
    delta = dt - datetime.now(timezone.utc)
    return delta.days
