"""Factor registry: decorator-based registration + unified output schema.

A factor is a Python function taking a feature row or DataFrame and returning a
FactorOutput with signed score (-1..+1), bias, confidence, and notes. Works both
vectorized (DataFrame in → Series out) and single-row (Series in → scalar out).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd

Bias = Literal["long", "short", "neutral"]
Category = Literal[
    "indicator", "pattern", "regime", "earnings", "volume", "volatility", "breadth"
]


@dataclass
class FactorOutput:
    """Unified output from any factor function.

    In vectorized mode, triggered/score are Series; confidence may also be Series
    or scalar. In single-row mode they are scalars.
    """

    triggered: Any
    score: Any
    bias: Bias = "neutral"
    confidence: Any = 0.5
    notes: str = ""


@dataclass
class FactorMeta:
    id: str
    category: Category
    bias_default: Bias
    confidence_base: float
    description: str
    requires: list[str] = field(default_factory=list)
    ic: dict[str, float] = field(default_factory=dict)
    ic_sample_size: int | None = None
    ic_updated_at: str | None = None
    fn: Callable[..., FactorOutput] | None = None


FACTOR_REGISTRY: dict[str, FactorMeta] = {}


def register(
    factor_id: str,
    *,
    category: Category,
    bias_default: Bias = "neutral",
    confidence_base: float = 0.5,
    description: str = "",
    requires: list[str] | None = None,
    ic: dict[str, float] | None = None,
    ic_sample_size: int | None = None,
    ic_updated_at: str | None = None,
) -> Callable[[Callable[..., FactorOutput]], Callable[..., FactorOutput]]:
    """Register a factor function.

    `requires` lists feature column names the factor reads, so callers can
    compute only what's needed.
    `ic` is the historical Information Coefficient measured on various universes,
    e.g. `{"sp500_daily": 0.14}`. Filled by strategy-lab backtest, not by the
    factor author.
    """

    def wrap(fn: Callable[..., FactorOutput]) -> Callable[..., FactorOutput]:
        if factor_id in FACTOR_REGISTRY:
            raise ValueError(f"factor already registered: {factor_id}")
        FACTOR_REGISTRY[factor_id] = FactorMeta(
            id=factor_id,
            category=category,
            bias_default=bias_default,
            confidence_base=confidence_base,
            description=description or (fn.__doc__ or "").strip().splitlines()[0]
            if fn.__doc__
            else "",
            requires=requires or [],
            ic=ic or {},
            ic_sample_size=ic_sample_size,
            ic_updated_at=ic_updated_at,
            fn=fn,
        )
        return fn

    return wrap


def evaluate_all(
    feat: pd.DataFrame | pd.Series,
    *,
    factor_ids: list[str] | None = None,
) -> pd.DataFrame:
    """Run factors on a feature panel.

    Input:
      feat: DataFrame with features (index = date or MultiIndex [date, symbol]).
    Output:
      DataFrame with columns = factor_id, values = signed score.

    Single-row (Series) input returns a 1-row DataFrame.
    """
    if factor_ids is None:
        factor_ids = list(FACTOR_REGISTRY.keys())

    missing = [fid for fid in factor_ids if fid not in FACTOR_REGISTRY]
    if missing:
        raise KeyError(f"unknown factor ids: {missing}")

    if isinstance(feat, pd.Series):
        return _evaluate_single_row(feat, factor_ids)

    return _evaluate_panel(feat, factor_ids)


def _evaluate_panel(feat: pd.DataFrame, factor_ids: list[str]) -> pd.DataFrame:
    cols: dict[str, pd.Series] = {}
    for fid in factor_ids:
        meta = FACTOR_REGISTRY[fid]
        assert meta.fn is not None
        try:
            out = meta.fn(feat)
        except Exception as exc:
            cols[fid] = pd.Series(np.nan, index=feat.index, name=fid)
            cols[f"__err_{fid}"] = pd.Series(str(exc), index=feat.index)
            continue
        score = out.score
        if np.isscalar(score):
            cols[fid] = pd.Series(float(score), index=feat.index, name=fid)
        else:
            s = pd.Series(score, index=feat.index, name=fid).astype(float)
            cols[fid] = s
    return pd.concat(cols.values(), axis=1, keys=cols.keys())


def _evaluate_single_row(feat: pd.Series, factor_ids: list[str]) -> pd.DataFrame:
    rows = {}
    for fid in factor_ids:
        meta = FACTOR_REGISTRY[fid]
        assert meta.fn is not None
        try:
            out = meta.fn(feat)
            score = float(out.score) if not pd.isna(out.score) else float("nan")
            rows[fid] = {
                "score": score,
                "triggered": bool(out.triggered) if out.triggered is not None else False,
                "bias": out.bias,
                "confidence": float(out.confidence) if np.isscalar(out.confidence) else 0.5,
                "notes": out.notes,
            }
        except Exception as exc:
            rows[fid] = {
                "score": float("nan"),
                "triggered": False,
                "bias": "neutral",
                "confidence": 0.0,
                "notes": f"error: {exc}",
            }
    return pd.DataFrame(rows).T


def list_factors(category: Category | None = None) -> list[FactorMeta]:
    items = list(FACTOR_REGISTRY.values())
    if category is not None:
        items = [m for m in items if m.category == category]
    return items
