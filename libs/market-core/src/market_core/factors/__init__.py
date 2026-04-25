"""Factor registry: @register decorators + catalog of built-in factors.

Import side effect: importing this subpackage registers all catalog factors
into FACTOR_REGISTRY.
"""

from market_core.factors.registry import (
    FACTOR_REGISTRY,
    FactorOutput,
    evaluate_all,
    list_factors,
    register,
)

# Side-effect: register all catalog factors.
from market_core.factors import catalog as _catalog  # noqa: F401

__all__ = [
    "FACTOR_REGISTRY",
    "FactorOutput",
    "evaluate_all",
    "list_factors",
    "register",
]
