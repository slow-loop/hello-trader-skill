from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .api import _as_float, _days_to_resolution, build_market_summary, fetch_events_page, is_candidate_market
from .profiles import get_profile_spec, resolve_profile_stages

DEFAULT_BUFFER_MULTIPLIER = 4
DEFAULT_EVENT_PAGE_SIZE = 100
GEO_BUCKET_LIMIT = 20
MAX_EVENT_PAGES_PER_STAGE = 2
MAX_DAYS_SENTINEL = 9_999


def discover_markets(
    *,
    limit: int | None = None,
    profile_name: str | None = None,
    excluded_slugs: set[str] | None = None,
) -> list[dict[str, Any]]:
    profile = get_profile_spec(profile_name)
    stages = resolve_profile_stages(profile["name"])
    target_limit = max(1, int(limit or profile["default_limit"]))
    excluded_market_slugs = {str(slug).strip() for slug in (excluded_slugs or set()) if str(slug).strip()}
    if profile.get("preserve_stage_buckets"):
        return _discover_bucketed_markets(
            profile=profile,
            stages=stages,
            target_limit=target_limit,
            excluded_slugs=excluded_market_slugs,
        )

    candidates_by_slug: dict[str, dict[str, Any]] = {}
    for stage_index, stage in enumerate(stages):
        stage_candidates = _collect_stage_candidates(
            stage=stage,
            stage_index=stage_index,
            profile=profile,
            target_limit=target_limit,
            excluded_slugs=excluded_market_slugs,
        )
        for candidate in stage_candidates:
            slug = str(candidate.get("slug") or "")
            if not slug:
                continue
            existing = candidates_by_slug.get(slug)
            if existing is None or _final_sort_key(candidate, profile) < _final_sort_key(existing, profile):
                candidates_by_slug[slug] = candidate

    merged = list(candidates_by_slug.values())
    merged.sort(key=lambda item: _final_sort_key(item, profile))
    return merged[:target_limit]


def _discover_bucketed_markets(
    *,
    profile: dict[str, Any],
    stages: list[dict[str, Any]],
    target_limit: int,
    excluded_slugs: set[str],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_slugs = set(excluded_slugs)
    bucket_limit = max(1, int(profile.get("bucket_limit") or target_limit))

    for stage_index, stage in enumerate(stages):
        stage_candidates = _collect_stage_candidates(
            stage=stage,
            stage_index=stage_index,
            profile=profile,
            target_limit=bucket_limit,
            excluded_slugs=selected_slugs,
        )
        stage_candidates.sort(key=lambda item: _bucket_sort_key(item, order=str(stage["params"].get("order") or "")))
        bucket_count = 0
        for candidate in stage_candidates:
            slug = str(candidate.get("slug") or "")
            if not slug or slug in selected_slugs:
                continue
            selected.append(candidate)
            selected_slugs.add(slug)
            bucket_count += 1
            if bucket_count >= bucket_limit:
                break

    return selected[:target_limit]


def _collect_stage_candidates(
    *,
    stage: dict[str, Any],
    stage_index: int,
    profile: dict[str, Any],
    target_limit: int,
    excluded_slugs: set[str],
) -> list[dict[str, Any]]:
    harvested_events = _harvest_stage_events(stage, target_limit=target_limit)
    selected: list[dict[str, Any]] = []

    for event in harvested_events:
        event_tags = _extract_event_tags(event)
        event_candidates: list[dict[str, Any]] = []
        for market in event.get("markets", []) if isinstance(event.get("markets"), list) else []:
            enriched_market = _enrich_market(market, event, event_tags)
            market_key = str(enriched_market.get("slug") or enriched_market.get("id") or "")
            if not market_key or market_key in excluded_slugs:
                continue
            if not is_candidate_market(enriched_market):
                continue

            market_summary = _build_stage_market_summary(
                market=enriched_market,
                event=event,
                event_tags=event_tags,
                profile=profile,
                stage_name=stage["name"],
                stage_index=stage_index,
            )
            if market_summary is None:
                continue
            event_candidates.append(market_summary)

        if not event_candidates:
            continue

        event_candidates.sort(key=lambda item: _event_market_rank_key(item, profile))
        selected.extend(event_candidates[: profile["max_markets_per_event"]])
    return selected


def _harvest_stage_events(stage: dict[str, Any], *, target_limit: int) -> list[dict[str, Any]]:
    target_events = max(50, min(200, target_limit * DEFAULT_BUFFER_MULTIPLIER))
    per_page_limit = max(20, min(DEFAULT_EVENT_PAGE_SIZE, target_events))
    collected: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()

    for page_index in range(MAX_EVENT_PAGES_PER_STAGE):
        offset = page_index * per_page_limit
        page = fetch_events_page(limit=per_page_limit, offset=offset, **stage["params"])
        if not page:
            continue

        for event in page:
            if not isinstance(event, dict):
                continue
            event_id = str(event.get("id") or event.get("slug") or "")
            if not event_id or event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)
            collected.append(event)

        if len(collected) >= target_events:
            return collected[:target_events]
    return collected


def _build_stage_market_summary(
    *,
    market: dict[str, Any],
    event: dict[str, Any],
    event_tags: list[str],
    profile: dict[str, Any],
    stage_name: str,
    stage_index: int,
) -> dict[str, Any] | None:
    summary = build_market_summary(market)
    if summary is None:
        return None

    resolved_end_date = summary.get("endDate") or event.get("endDate")
    liquidity = summary.get("liquidity") or 0.0
    volume24hr = summary.get("volume24hr") or 0.0
    days_to_resolution = _days_to_resolution(resolved_end_date)
    family_market = _is_family_market(market, event, event_tags)
    min_days_to_resolution = profile.get("min_days_to_resolution")

    if liquidity < profile["market_liquidity_min"]:
        return None
    if volume24hr < profile["market_volume24hr_min"]:
        return None
    if days_to_resolution is not None and days_to_resolution < 0:
        return None
    if isinstance(min_days_to_resolution, int) and days_to_resolution is not None and days_to_resolution < min_days_to_resolution:
        return None
    if profile["exclude_family_markets"] and family_market:
        return None
    if profile["exclude_obvious_derivatives"] and _is_obvious_derivative_market(summary):
        return None
    if _matches_excluded_text_patterns(market, event, profile):
        return None

    summary.update(
        {
            "profile": profile["name"],
            "sourceQuery": stage_name,
            "sourceStageIndex": stage_index,
            "endDate": resolved_end_date,
            "familyMarket": family_market,
            "eventTitle": str(event.get("title", "") or "").strip(),
            "eventSlug": str(event.get("slug", "") or ""),
            "eventCategory": _normalize_text(event.get("category")),
            "eventSubcategory": _normalize_text(event.get("subcategory")),
            "eventTags": event_tags,
            "daysToResolution": days_to_resolution,
            "priceExtreme": round(_price_extreme(summary), 4),
            "isDerivative": _is_obvious_derivative_market(summary),
        }
    )
    return summary


def _event_market_rank_key(item: dict[str, Any], profile: dict[str, Any]) -> tuple[Any, ...]:
    derivative_penalty = 1 if item.get("isDerivative") else 0
    days = item.get("daysToResolution")
    normalized_days = days if isinstance(days, int) else MAX_DAYS_SENTINEL

    if profile["name"] == "sports":
        return (
            derivative_penalty,
            -(item.get("volume24hr") or 0.0),
            -(item.get("liquidity") or 0.0),
            normalized_days,
        )

    return (
        derivative_penalty,
        -(item.get("volume24hr") or 0.0),
        -(item.get("liquidity") or 0.0),
        normalized_days,
    )


def _final_sort_key(item: dict[str, Any], profile: dict[str, Any]) -> tuple[Any, ...]:
    days = item.get("daysToResolution")
    normalized_days = days if isinstance(days, int) else MAX_DAYS_SENTINEL
    stage_index = int(item.get("sourceStageIndex") or 0)

    if profile["final_sort"] == "endDate":
        return (
            normalized_days,
            -(item.get("volume24hr") or 0.0),
            -(item.get("liquidity") or 0.0),
            stage_index,
        )

    if profile["final_sort"] == "updatedAt":
        return (
            -_timestamp(item.get("updatedAt")),
            -(item.get("volume24hr") or 0.0),
            -(item.get("liquidity") or 0.0),
            normalized_days,
            stage_index,
        )

    return (
        -(item.get("volume24hr") or 0.0),
        -(item.get("liquidity") or 0.0),
        normalized_days,
        -_timestamp(item.get("updatedAt")),
        stage_index,
    )


def _bucket_sort_key(item: dict[str, Any], *, order: str) -> tuple[Any, ...]:
    days = item.get("daysToResolution")
    normalized_days = days if isinstance(days, int) else MAX_DAYS_SENTINEL

    if order == "createdAt":
        return (
            -_timestamp(item.get("createdAt")),
            -(item.get("volume24hr") or 0.0),
            -(item.get("liquidity") or 0.0),
            normalized_days,
        )

    if order == "updatedAt":
        return (
            -_timestamp(item.get("updatedAt")),
            -(item.get("volume24hr") or 0.0),
            -(item.get("liquidity") or 0.0),
            normalized_days,
        )

    return (
        normalized_days,
        -(item.get("volume24hr") or 0.0),
        -(item.get("liquidity") or 0.0),
        -_timestamp(item.get("updatedAt")),
    )


def _enrich_market(market: dict[str, Any], event: dict[str, Any], event_tags: list[str]) -> dict[str, Any]:
    enriched = dict(market)
    enriched["events"] = [
        {
            "title": str(event.get("title", "") or "").strip(),
            "slug": str(event.get("slug", "") or ""),
            "category": event.get("category"),
            "subcategory": event.get("subcategory"),
            "description": str(event.get("description", "") or "").strip(),
            "openInterest": _as_float(event.get("openInterest")),
            "endDate": event.get("endDate"),
        }
    ]
    enriched["eventTags"] = event_tags
    return enriched


def _extract_event_tags(event: dict[str, Any]) -> list[str]:
    tags = event.get("tags")
    if not isinstance(tags, list):
        return []
    slugs: list[str] = []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        slug = str(tag.get("slug", "") or "").strip().lower()
        if slug:
            slugs.append(slug)
    return slugs


def _price_extreme(market: dict[str, Any]) -> float:
    prices = _parse_prices(market.get("outcomePrices"))
    if not prices:
        return 0.0
    return min(1.0, abs(prices[0] - 0.5) * 2.0)


def _is_family_market(market: dict[str, Any], event: dict[str, Any], event_tags: list[str]) -> bool:
    family_tags = {
        "weekly",
        "monthly",
        "recurring",
        "multi-strikes",
        "hit-price",
        "tweets-markets",
        "elections",
        "world-elections",
        "global-elections",
    }
    if set(event_tags).intersection(family_tags):
        return True

    question = _normalize_text(market.get("question"))
    event_title = _normalize_text(event.get("title"))
    family_patterns = (
        "between ",
        "less than ",
        "more than ",
        "at least ",
        "at most ",
        " percentage change ",
        " total number of ",
        " hit ",
    )
    if any(pattern in question for pattern in family_patterns):
        return True
    if any(pattern in event_title for pattern in family_patterns):
        return True

    markets = event.get("markets")
    if isinstance(markets, list) and len(markets) >= 4:
        if "winner" in event_title:
            return True
        if "which company has" in event_title:
            return True
        if "which company will have" in event_title:
            return True
        if "largest company" in event_title:
            return True
    return False


def _is_obvious_derivative_market(market: dict[str, Any]) -> bool:
    question = _normalize_text(market.get("question"))
    derivative_patterns = (
        "spread:",
        "o/u",
        "over/under",
        " total ",
        "handicap",
    )
    return any(pattern in question for pattern in derivative_patterns)


def _matches_excluded_text_patterns(market: dict[str, Any], event: dict[str, Any], profile: dict[str, Any]) -> bool:
    patterns = tuple(str(item).strip().lower() for item in profile.get("exclude_text_patterns", ()) if str(item).strip())
    if not patterns:
        return False

    haystacks = (
        _normalize_text(market.get("question")),
        _normalize_text(event.get("title")),
    )
    return any(pattern in haystack for haystack in haystacks for pattern in patterns)


def _parse_prices(value: Any) -> list[float]:
    if isinstance(value, list):
        raw_prices = value
    elif isinstance(value, str):
        try:
            import json

            raw_prices = json.loads(value)
        except json.JSONDecodeError:
            return []
    else:
        return []
    prices: list[float] = []
    for item in raw_prices:
        parsed = _as_float(item)
        if parsed is None:
            return []
        prices.append(parsed)
    return prices


def _timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return parsed.astimezone(timezone.utc).timestamp()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()
