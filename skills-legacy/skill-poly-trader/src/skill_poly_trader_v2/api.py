from __future__ import annotations

import json
from datetime import datetime, timezone
from time import sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

GAMMA_API = "https://gamma-api.polymarket.com"
USER_AGENT = "skill-poly-trader-v2/0.1"
DEFAULT_MARKET_ORDER = "volume24hr"


def fetch_markets_page(
    *,
    limit: int = 100,
    offset: int = 0,
    closed: bool = False,
    order: str = DEFAULT_MARKET_ORDER,
    ascending: bool = False,
) -> list[dict[str, Any]]:
    params = {
        "closed": str(closed).lower(),
        "limit": str(limit),
        "offset": str(offset),
        "order": order,
        "ascending": str(ascending).lower(),
    }
    payload = _fetch_json(f"/markets?{urlencode(params)}")
    return payload if isinstance(payload, list) else []


def fetch_events_page(
    *,
    limit: int = 100,
    offset: int = 0,
    active: bool | None = True,
    archived: bool | None = None,
    featured: bool | None = None,
    cyom: bool | None = None,
    include_chat: bool | None = None,
    include_template: bool | None = None,
    recurrence: str | None = None,
    closed: bool | None = False,
    order: str = DEFAULT_MARKET_ORDER,
    ascending: bool = False,
    id: list[int] | None = None,
    tag_id: int | None = None,
    exclude_tag_id: list[int] | None = None,
    slug: list[str] | None = None,
    tag_slug: str | None = None,
    related_tags: bool | None = None,
    liquidity_min: float | None = None,
    liquidity_max: float | None = None,
    volume_min: float | None = None,
    volume_max: float | None = None,
    start_date_min: str | None = None,
    start_date_max: str | None = None,
    end_date_min: str | None = None,
    end_date_max: str | None = None,
) -> list[dict[str, Any]]:
    params = {
        "limit": str(limit),
        "offset": str(offset),
        "order": order,
        "ascending": str(ascending).lower(),
    }
    if active is not None:
        params["active"] = str(active).lower()
    if archived is not None:
        params["archived"] = str(archived).lower()
    if featured is not None:
        params["featured"] = str(featured).lower()
    if cyom is not None:
        params["cyom"] = str(cyom).lower()
    if include_chat is not None:
        params["include_chat"] = str(include_chat).lower()
    if include_template is not None:
        params["include_template"] = str(include_template).lower()
    if recurrence:
        params["recurrence"] = recurrence
    if closed is not None:
        params["closed"] = str(closed).lower()
    if id:
        params["id"] = [str(item) for item in id]
    if tag_id is not None:
        params["tag_id"] = str(tag_id)
    if exclude_tag_id:
        params["exclude_tag_id"] = [str(item) for item in exclude_tag_id]
    if slug:
        params["slug"] = list(slug)
    if tag_slug:
        params["tag_slug"] = tag_slug
    if related_tags is not None:
        params["related_tags"] = str(related_tags).lower()
    if liquidity_min is not None:
        params["liquidity_min"] = str(liquidity_min)
    if liquidity_max is not None:
        params["liquidity_max"] = str(liquidity_max)
    if volume_min is not None:
        params["volume_min"] = str(volume_min)
    if volume_max is not None:
        params["volume_max"] = str(volume_max)
    if start_date_min:
        params["start_date_min"] = start_date_min
    if start_date_max:
        params["start_date_max"] = start_date_max
    if end_date_min:
        params["end_date_min"] = end_date_min
    if end_date_max:
        params["end_date_max"] = end_date_max
    payload = _fetch_json(f"/events?{urlencode(params, doseq=True)}")
    return payload if isinstance(payload, list) else []


def fetch_market_by_slug(slug: str) -> dict[str, Any] | None:
    payload = _fetch_json(f"/markets?{urlencode({'slug': slug})}")
    if isinstance(payload, list) and payload:
        return payload[0]
    return None


def build_market_summary(market: dict[str, Any]) -> dict[str, Any] | None:
    parsed = _parse_outcomes_and_prices(market)
    if parsed is None:
        return None
    outcomes, prices = parsed
    return {
        "question": str(market.get("question", "") or "").strip(),
        "slug": str(market.get("slug", "") or ""),
        "description": str(market.get("description", "") or "").strip(),
        "outcomes": outcomes,
        "outcomePrices": prices,
        "endDate": market.get("endDate"),
        "createdAt": market.get("createdAt"),
        "volume24hr": _as_float(market.get("volume24hr")) or 0.0,
        "liquidity": _as_float(market.get("liquidity")) or _as_float(market.get("liquidityNum")) or 0.0,
        "bestBid": _as_float(market.get("bestBid")),
        "bestAsk": _as_float(market.get("bestAsk")),
        "spread": _as_float(market.get("spread")),
        "updatedAt": market.get("updatedAt"),
    }


def build_market_detail(market: dict[str, Any]) -> dict[str, Any] | None:
    parsed = _parse_outcomes_and_prices(market)
    if parsed is None:
        return None
    outcomes, prices = parsed
    detail = {
        "id": str(market.get("id", "") or ""),
        "question": str(market.get("question", "") or "").strip(),
        "slug": str(market.get("slug", "") or ""),
        "description": str(market.get("description", "") or "").strip(),
        "outcomes": outcomes,
        "outcomeIndexMap": {str(index): outcome for index, outcome in enumerate(outcomes)},
        "outcomePrices": prices,
        "endDate": market.get("endDate"),
        "active": bool(market.get("active", False)),
        "closed": bool(market.get("closed", False)),
        "acceptingOrders": bool(market.get("acceptingOrders", False)),
        "bestBid": _as_float(market.get("bestBid")),
        "bestAsk": _as_float(market.get("bestAsk")),
        "spread": _as_float(market.get("spread")),
        "lastTradePrice": _as_float(market.get("lastTradePrice")),
        "volume24hr": _as_float(market.get("volume24hr")) or 0.0,
        "liquidity": _as_float(market.get("liquidity")) or _as_float(market.get("liquidityNum")) or 0.0,
        "createdAt": market.get("createdAt"),
        "updatedAt": market.get("updatedAt"),
        "resolutionSource": str(market.get("resolutionSource", "") or ""),
        "resolvedBy": market.get("resolvedBy"),
        "umaResolutionStatuses": _parse_json_list(market.get("umaResolutionStatuses")),
        "events": _extract_event_context(market.get("events")),
        "eventTags": _extract_event_tags(market.get("eventTags")),
    }
    return detail


def fetch_market_detail(slug: str) -> dict[str, Any]:
    market = fetch_market_by_slug(slug)
    if not market:
        raise RuntimeError(f"Market not found for slug: {slug}")
    detail = build_market_detail(market)
    if detail is None:
        raise RuntimeError(f"Market is not a supported binary market: {slug}")
    return detail


def is_candidate_market(market: dict[str, Any]) -> bool:
    parsed = _parse_outcomes_and_prices(market)
    if parsed is None:
        return False

    question = str(market.get("question", "") or "").strip()
    slug = str(market.get("slug", "") or "")
    if not question or not slug:
        return False
    if bool(market.get("closed", False)):
        return False
    if market.get("active") is False:
        return False
    if market.get("acceptingOrders") is False:
        return False
    days = _days_to_resolution(market.get("endDate"))
    if days is not None and days < 0:
        return False
    return True

def derive_terminal_payoffs(market: dict[str, Any]) -> list[float] | None:
    parsed = _parse_outcomes_and_prices(market)
    if parsed is None:
        return None
    _, prices = parsed
    if not bool(market.get("closed", False)):
        return None

    rounded = [_normalize_terminal_price(price) for price in prices]
    if rounded is None:
        return None
    if sum(rounded) != 1:
        return None
    return [float(value) for value in rounded]


def _normalize_terminal_price(price: float) -> int | None:
    if abs(price - 1.0) <= 1e-9:
        return 1
    if abs(price - 0.0) <= 1e-9:
        return 0
    return None


def _extract_event_context(events: Any) -> list[dict[str, Any]]:
    if not isinstance(events, list):
        return []
    context: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        context.append(
            {
                "title": str(event.get("title", "") or "").strip(),
                "slug": str(event.get("slug", "") or ""),
                "category": event.get("category"),
                "description": str(event.get("description", "") or "").strip(),
                "openInterest": _as_float(event.get("openInterest")),
                "endDate": event.get("endDate"),
            }
        )
    return context


def _extract_event_tags(event_tags: Any) -> list[str]:
    if not isinstance(event_tags, list):
        return []
    normalized: list[str] = []
    for tag in event_tags:
        value = str(tag or "").strip().lower()
        if value:
            normalized.append(value)
    return normalized


def _parse_outcomes_and_prices(market: dict[str, Any]) -> tuple[list[str], list[float]] | None:
    outcomes = _parse_json_list(market.get("outcomes"))
    prices = _parse_json_list(market.get("outcomePrices"))
    if len(outcomes) != 2 or len(prices) != 2:
        return None

    normalized_outcomes = [str(item).strip() for item in outcomes]
    normalized_prices = [_as_float(item) for item in prices]
    if any(price is None for price in normalized_prices):
        return None
    return normalized_outcomes, [float(price) for price in normalized_prices]


def _fetch_json(path: str) -> Any:
    url = f"{GAMMA_API}{path}"
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            last_error = exc
            if exc.code < 500 and exc.code != 429:
                raise
        except URLError as exc:
            last_error = exc
        if attempt < 2:
            sleep(0.5 * (attempt + 1))
    assert last_error is not None
    raise last_error


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
