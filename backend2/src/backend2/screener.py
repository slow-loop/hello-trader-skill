"""Compat shim — screener logic lives in market_core.screener.

`WorkspaceRuntimeConfig` is duck-type compatible with `MarketRuntimeConfig`
(both expose `.market`, `.analysis`, `.news`), so we pass it through.
"""

from market_core.screener import run_screener, run_tw_momentum_screener

__all__ = ["run_screener", "run_tw_momentum_screener"]
