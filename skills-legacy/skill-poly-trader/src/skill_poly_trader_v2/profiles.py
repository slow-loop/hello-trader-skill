from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from .tags import resolve_tag_ids

COMMON_EXCLUDE_TAG_SLUGS = (
    "pop-culture",
    "tweets-markets",
    "monthly",
    "hit-price",
)

PROFILES: dict[str, dict[str, Any]] = {
    "all": {
        "default_limit": 80,
        "max_markets_per_event": 1,
        "market_liquidity_min": 25_000.0,
        "market_volume24hr_min": 1_000.0,
        "exclude_family_markets": True,
        "exclude_obvious_derivatives": False,
        "final_sort": "volume24hr",
        "stages": (
            {
                "name": "all-updatedAt",
                "params": {
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "updatedAt",
                    "ascending": False,
                    "liquidity_min": 50_000,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS,
            },
            {
                "name": "all-endDate",
                "params": {
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "endDate",
                    "ascending": True,
                    "liquidity_min": 50_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS,
            },
        ),
    },
    "geo": {
        "default_limit": 60,
        "max_markets_per_event": 1,
        "market_liquidity_min": 25_000.0,
        "market_volume24hr_min": 1_000.0,
        "exclude_family_markets": True,
        "exclude_obvious_derivatives": False,
        "final_sort": "endDate",
        "preserve_stage_buckets": True,
        "bucket_limit": 20,
        "stages": (
            {
                "name": "geo-endDate",
                "params": {
                    "tag_slug": "politics",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "endDate",
                    "ascending": True,
                    "liquidity_min": 50_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS + ("sports", "crypto", "oil", "stocks"),
            },
            {
                "name": "geo-updatedAt",
                "params": {
                    "tag_slug": "politics",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "updatedAt",
                    "ascending": False,
                    "liquidity_min": 50_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS + ("sports", "crypto", "oil", "stocks"),
            },
            {
                "name": "geo-createdAt",
                "params": {
                    "tag_slug": "politics",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "createdAt",
                    "ascending": False,
                    "liquidity_min": 25_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS + ("sports", "crypto", "oil", "stocks"),
            },
        ),
    },
    "macro": {
        "default_limit": 80,
        "max_markets_per_event": 1,
        "market_liquidity_min": 25_000.0,
        "market_volume24hr_min": 1_000.0,
        "exclude_family_markets": True,
        "exclude_obvious_derivatives": False,
        "final_sort": "volume24hr",
        "stages": (
            {
                "name": "macro-economy-updatedAt",
                "params": {
                    "tag_slug": "economy",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "updatedAt",
                    "ascending": False,
                    "liquidity_min": 50_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS + ("sports", "crypto", "stocks", "market-cap"),
            },
            {
                "name": "macro-economy-endDate",
                "params": {
                    "tag_slug": "economy",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "endDate",
                    "ascending": True,
                    "liquidity_min": 50_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS + ("sports", "crypto", "stocks", "market-cap"),
            },
            {
                "name": "macro-fed-updatedAt",
                "params": {
                    "tag_slug": "fed",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "updatedAt",
                    "ascending": False,
                    "liquidity_min": 50_000,
                    "end_date_max_days_from_now": 180,
                },
                "exclude_tag_slugs": COMMON_EXCLUDE_TAG_SLUGS + ("sports", "crypto", "stocks", "market-cap"),
            },
        ),
    },
    "ai": {
        "default_limit": 60,
        "max_markets_per_event": 1,
        "market_liquidity_min": 10_000.0,
        "market_volume24hr_min": 500.0,
        "exclude_family_markets": True,
        "exclude_obvious_derivatives": False,
        "final_sort": "volume24hr",
        "stages": (
            {
                "name": "ai-updatedAt",
                "params": {
                    "tag_slug": "ai",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "updatedAt",
                    "ascending": False,
                    "liquidity_min": 25_000,
                    "end_date_max_days_from_now": 120,
                },
                "exclude_tag_slugs": ("business", "market-cap", "ipo", "ipos"),
            },
            {
                "name": "ai-endDate",
                "params": {
                    "tag_slug": "ai",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "endDate",
                    "ascending": True,
                    "liquidity_min": 25_000,
                    "end_date_max_days_from_now": 120,
                },
                "exclude_tag_slugs": ("business", "market-cap", "ipo", "ipos"),
            },
        ),
    },
    "sports": {
        "default_limit": 80,
        "max_markets_per_event": 1,
        "market_liquidity_min": 25_000.0,
        "market_volume24hr_min": 1_000.0,
        "min_days_to_resolution": 1,
        "exclude_family_markets": True,
        "exclude_obvious_derivatives": True,
        "exclude_text_patterns": (
            "qualification:",
            "qualifier",
            "counter-strike:",
            "valorant:",
            "lol:",
            "esports",
        ),
        "final_sort": "updatedAt",
        "preserve_stage_buckets": True,
        "bucket_limit": 20,
        "stages": (
            {
                "name": "sports-updatedAt",
                "params": {
                    "tag_slug": "sports",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "updatedAt",
                    "ascending": False,
                    "liquidity_min": 25_000,
                    "end_date_max_days_from_now": 14,
                },
                "exclude_tag_slugs": (),
            },
            {
                "name": "sports-createdAt",
                "params": {
                    "tag_slug": "sports",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "createdAt",
                    "ascending": False,
                    "liquidity_min": 25_000,
                    "end_date_max_days_from_now": 14,
                },
                "exclude_tag_slugs": (),
            },
            {
                "name": "sports-endDate",
                "params": {
                    "tag_slug": "sports",
                    "related_tags": True,
                    "active": True,
                    "closed": False,
                    "include_template": False,
                    "order": "endDate",
                    "ascending": True,
                    "liquidity_min": 25_000,
                    "end_date_max_days_from_now": 14,
                },
                "exclude_tag_slugs": (),
            },
        ),
    },
}


def get_profile_spec(name: str | None) -> dict[str, Any]:
    normalized = (name or "all").strip().lower() or "all"
    if normalized not in PROFILES:
        supported = ", ".join(sorted(PROFILES))
        raise RuntimeError(f"Unsupported profile: {name}. Supported profiles: {supported}")
    return {"name": normalized, **PROFILES[normalized]}


def list_profile_names() -> list[str]:
    return sorted(PROFILES)


def resolve_profile_stages(name: str | None) -> list[dict[str, Any]]:
    spec = get_profile_spec(name)
    resolved: list[dict[str, Any]] = []
    for stage in spec["stages"]:
        params = _resolve_stage_params(stage["params"])
        exclude_tag_slugs = tuple(stage.get("exclude_tag_slugs", ()))
        if exclude_tag_slugs:
            exclude_tag_ids = resolve_tag_ids(exclude_tag_slugs, strict=False)
            if exclude_tag_ids:
                params["exclude_tag_id"] = exclude_tag_ids
        resolved.append({"name": stage["name"], "params": params})
    return resolved


def _resolve_stage_params(params: dict[str, Any]) -> dict[str, Any]:
    resolved = {key: value for key, value in params.items() if not key.endswith("_days_from_now")}
    for field in ("start_date_min", "start_date_max", "end_date_min", "end_date_max"):
        relative_key = f"{field}_days_from_now"
        if relative_key in params:
            resolved[field] = _days_from_now_iso(int(params[relative_key]))
    return resolved


def _days_from_now_iso(days: int) -> str:
    target = datetime.now(timezone.utc) + timedelta(days=days)
    return target.replace(microsecond=0).isoformat().replace("+00:00", "Z")
