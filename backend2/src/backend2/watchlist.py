"""Compat shim — watchlist evaluation lives in market_core.watchlist."""
from __future__ import annotations

from backend2.models import EvaluatedWatchlistConfig, WorkspaceRuntimeConfig
from backend2.workspace import load_watchlist
from market_core.policies import MarketProfile
from market_core.watchlist import evaluate_watchlist, evaluate_watchlist_item

__all__ = ["evaluate_watchlist_item", "load_evaluated_watchlist"]


def load_evaluated_watchlist(
    config: WorkspaceRuntimeConfig,
    profile: MarketProfile,
) -> EvaluatedWatchlistConfig:
    watchlist = load_watchlist(config)
    return evaluate_watchlist(watchlist, config, profile)
