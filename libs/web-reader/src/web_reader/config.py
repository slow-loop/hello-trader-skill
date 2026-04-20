"""YAML config loader for web-reader."""

from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class CacheConfig(BaseModel):
    """Minimal cache strategy for a source."""

    ttl: Optional[int] = None  # seconds


class SourceConfig(BaseModel):
    """A single source in the feeds config."""

    name: str
    reader: str  # web, rss, reddit, youtube, email, json, substack
    url: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    tags: list[str] = Field(default_factory=list)


class DefaultsConfig(BaseModel):
    """Default params and cache applied to all sources."""

    params: dict[str, Any] = Field(default_factory=dict)
    cache: Optional[CacheConfig] = None


class FeedConfig(BaseModel):
    """Top-level feeds.yaml structure."""

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    sources: list[SourceConfig] = Field(default_factory=list)


def load_config(path: str | Path) -> FeedConfig:
    """Load a feeds.yaml file."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")

    with open(p) as f:
        raw = yaml.safe_load(f)

    if raw is None:
        return FeedConfig()

    config = FeedConfig.model_validate(raw)

    # Merge defaults into each source
    if config.defaults.params or config.defaults.cache:
        for source in config.sources:
            for key, value in config.defaults.params.items():
                if key not in source.params:
                    source.params[key] = value
            if config.defaults.cache and source.cache.ttl is None:
                source.cache.ttl = config.defaults.cache.ttl

    return config
