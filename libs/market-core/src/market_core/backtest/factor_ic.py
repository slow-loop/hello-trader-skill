"""Single-factor IC analysis (thin wrapper around alphalens-reloaded).

Input:
    factor_values: Series indexed by (date, symbol) — the factor score per bar.
    prices:        DataFrame indexed by date, columns = symbols, close prices.
    periods:       forward return horizons in trading days, e.g. (1, 5, 20).

Output:
    FactorICResult with per-horizon IC stats and quantile returns.

Alphalens is imported lazily so users without `.[backtest]` can still use the
registry + signal workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class FactorICResult:
    factor_id: str
    ic_by_period: dict[int, float]
    ic_std_by_period: dict[int, float]
    ic_sample_size: int
    quantile_returns: dict[int, dict[int, float]] = field(default_factory=dict)
    raw_tear_data: Any | None = None


def _require_alphalens():
    try:
        import alphalens  # noqa: F401
        return alphalens
    except ImportError as exc:
        raise RuntimeError(
            "alphalens-reloaded not installed. Install market-core[backtest]."
        ) from exc


def run_factor_ic(
    factor_id: str,
    factor_values: pd.Series,
    prices: pd.DataFrame,
    *,
    periods: tuple[int, ...] = (1, 5, 20),
    quantiles: int = 5,
    max_loss: float = 0.9,
) -> FactorICResult:
    """Compute IC for a single factor across the given forward horizons.

    max_loss default is permissive (0.9) because many factors are sparse
    (gated/triggered) and alphalens' default 0.35 rejects them. Tune per factor.
    """
    al = _require_alphalens()

    factor_clean = factor_values.dropna()
    factor_clean = factor_clean[factor_clean != 0]

    clean = al.utils.get_clean_factor_and_forward_returns(
        factor=factor_clean,
        prices=prices,
        periods=periods,
        quantiles=quantiles,
        max_loss=max_loss,
    )
    ic = al.performance.factor_information_coefficient(clean)
    quant_rets = al.performance.mean_return_by_quantile(clean)[0]

    ic_by_period: dict[int, float] = {}
    ic_std_by_period: dict[int, float] = {}
    for p in periods:
        col = f"{p}D"
        if col in ic.columns:
            ic_by_period[p] = float(ic[col].mean())
            ic_std_by_period[p] = float(ic[col].std())

    quantile_returns: dict[int, dict[int, float]] = {}
    for p in periods:
        col = f"{p}D"
        if col in quant_rets.columns:
            quantile_returns[p] = {int(q): float(v) for q, v in quant_rets[col].items()}

    return FactorICResult(
        factor_id=factor_id,
        ic_by_period=ic_by_period,
        ic_std_by_period=ic_std_by_period,
        ic_sample_size=len(clean),
        quantile_returns=quantile_returns,
        raw_tear_data=clean,
    )
