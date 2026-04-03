from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import quote, urlencode

from .api import _fetch_json

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TAG_INDEX_PATH = APP_ROOT / "data" / "tags.json"
DEFAULT_TAG_PAGE_SIZE = 500


def fetch_tags_page(*, limit: int = DEFAULT_TAG_PAGE_SIZE, offset: int = 0) -> list[dict[str, Any]]:
    params = {
        "limit": str(limit),
        "offset": str(offset),
    }
    payload = _fetch_json(f"/tags?{urlencode(params)}")
    return payload if isinstance(payload, list) else []


def fetch_tag_by_slug(slug: str) -> dict[str, Any] | None:
    normalized = str(slug or "").strip().lower()
    if not normalized:
        return None
    try:
        payload = _fetch_json(f"/tags/slug/{quote(normalized)}")
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    return payload if isinstance(payload, dict) else None


def load_tag_index(*, tag_index_path: Path | None = None, sync_if_missing: bool = True) -> dict[str, Any]:
    path = tag_index_path or DEFAULT_TAG_INDEX_PATH
    if not path.exists():
        if not sync_if_missing:
            return _empty_index()
        return sync_tag_index(tag_index_path=path)
    return json.loads(path.read_text(encoding="utf-8"))


def sync_tag_index(*, tag_index_path: Path | None = None) -> dict[str, Any]:
    path = tag_index_path or DEFAULT_TAG_INDEX_PATH
    collected: list[dict[str, Any]] = []
    offset = 0
    while True:
        page = fetch_tags_page(limit=DEFAULT_TAG_PAGE_SIZE, offset=offset)
        if not page:
            break
        collected.extend(page)
        if len(page) < DEFAULT_TAG_PAGE_SIZE:
            break
        offset += len(page)

    index = _build_index(collected)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def resolve_tag_ids(
    slugs: tuple[str, ...] | list[str],
    *,
    tag_index_path: Path | None = None,
    strict: bool = True,
) -> list[int]:
    index = load_tag_index(tag_index_path=tag_index_path, sync_if_missing=True)
    slug_to_id = {str(key).lower(): int(value) for key, value in index.get("slugToId", {}).items()}
    resolved: list[int] = []
    missing: list[str] = []

    for slug in slugs:
        normalized = str(slug or "").strip().lower()
        if not normalized:
            continue
        tag_id = slug_to_id.get(normalized)
        if tag_id is not None:
            resolved.append(tag_id)
        else:
            missing.append(normalized)

    if missing:
        additions: list[dict[str, Any]] = []
        for slug in missing:
            tag = fetch_tag_by_slug(slug)
            if tag is None:
                continue
            additions.append(tag)
            tag_id = _normalize_tag_id(tag.get("id"))
            if tag_id is not None:
                slug_to_id[slug] = tag_id
                resolved.append(tag_id)

        if additions:
            updated_index = _merge_index(index, additions)
            path = tag_index_path or DEFAULT_TAG_INDEX_PATH
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(updated_index, indent=2), encoding="utf-8")

    if strict:
        unresolved = sorted({slug for slug in missing if slug not in slug_to_id})
        if unresolved:
            joined = ", ".join(unresolved)
            raise RuntimeError(f"Could not resolve tag slug(s): {joined}")

    return sorted(set(resolved))


def _empty_index() -> dict[str, Any]:
    return {
        "fetchedAt": None,
        "count": 0,
        "tags": [],
        "slugToId": {},
    }


def _build_index(tags: list[dict[str, Any]]) -> dict[str, Any]:
    normalized_tags: list[dict[str, Any]] = []
    slug_to_id: dict[str, int] = {}
    seen_ids: set[int] = set()
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        tag_id = _normalize_tag_id(tag.get("id"))
        slug = str(tag.get("slug", "") or "").strip().lower()
        if tag_id is None or not slug or tag_id in seen_ids:
            continue
        seen_ids.add(tag_id)
        slug_to_id[slug] = tag_id
        normalized_tags.append(
            {
                "id": tag_id,
                "slug": slug,
                "label": str(tag.get("label", "") or "").strip(),
                "createdAt": tag.get("createdAt"),
                "updatedAt": tag.get("updatedAt"),
            }
        )
    normalized_tags.sort(key=lambda item: item["id"])
    return {
        "fetchedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "count": len(normalized_tags),
        "tags": normalized_tags,
        "slugToId": slug_to_id,
    }


def _merge_index(index: dict[str, Any], additions: list[dict[str, Any]]) -> dict[str, Any]:
    existing = index.get("tags", [])
    merged = [item for item in existing if isinstance(item, dict)] + additions
    return _build_index(merged)


def _normalize_tag_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
