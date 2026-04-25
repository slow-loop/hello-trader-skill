"""Strategy: YAML config → composite signal → entry/exit rules.

A strategy is a declarative combination of:
  - factors to evaluate
  - weights / thresholds for composite score
  - regime gating (benchmark-level conditions)
  - risk rules (stop/target formulas) — consumed by trader, computed here as
    well for transparency
  - agent_flow_hint (prose for the agent)

`load_strategy` reads YAML and returns a validated StrategyConfig.
`apply_strategy` runs the factor registry on a feature panel and produces a
composite signal per (date, symbol).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from pydantic import BaseModel, Field, field_validator

from market_core.factors.registry import FACTOR_REGISTRY, evaluate_all


class FactorRef(BaseModel):
    id: str
    weight: float = 1.0
    min_score: float | None = None
    max_score: float | None = None
    required: bool = False


class EntryRules(BaseModel):
    composite_score_min: float = 0.0
    must_include: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)


class RiskRules(BaseModel):
    initial_stop_formula: str | None = None
    target_r: float | None = 2.0
    max_position_pct: float = 30.0
    account_risk_pct: float = 1.0


class BacktestSummary(BaseModel):
    period: str | None = None
    universe: str | None = None
    sharpe: float | None = None
    max_dd: float | None = None
    turnover_monthly: float | None = None
    walk_forward_sharpe: float | None = None
    ic_by_factor: dict[str, float] = Field(default_factory=dict)


class StrategyConfig(BaseModel):
    name: str
    version: str = "0.0.1"
    description: str = ""
    promoted_at: str | None = None
    promoted_from: str | None = None
    approved_by: str | None = None

    factors: list[FactorRef]
    entry: EntryRules = Field(default_factory=EntryRules)
    risk: RiskRules = Field(default_factory=RiskRules)
    backtest_summary: BacktestSummary | None = None
    agent_flow_hint: str = ""

    @field_validator("factors")
    @classmethod
    def _check_factors_known(cls, v: list[FactorRef]) -> list[FactorRef]:
        for ref in v:
            if ref.id not in FACTOR_REGISTRY:
                raise ValueError(f"unknown factor id in strategy: {ref.id}")
        return v


def load_strategy(path: str | Path) -> StrategyConfig:
    data = yaml.safe_load(Path(path).read_text())
    return StrategyConfig.model_validate(data)


def apply_strategy(
    config: StrategyConfig,
    features: pd.DataFrame,
) -> pd.DataFrame:
    """Run all referenced factors on `features`, return signal panel.

    Output columns:
        <factor_id>         raw signed score per factor
        composite_score     weighted sum of included factors
        entry_ok            True if composite + required gates satisfied
        firing_factors      list[str] of factor ids contributing
    Index follows `features` index (date or [date, symbol]).
    """
    factor_ids = [f.id for f in config.factors]
    raw = evaluate_all(features, factor_ids=factor_ids)
    # Drop error columns that may have slipped in
    raw = raw.loc[:, [c for c in raw.columns if not str(c).startswith("__err_")]]

    composite = pd.Series(0.0, index=raw.index)
    required_ok = pd.Series(True, index=raw.index)
    firing = pd.Series([[] for _ in range(len(raw))], index=raw.index)

    for ref in config.factors:
        col = raw[ref.id].fillna(0.0)
        gate = pd.Series(True, index=col.index)
        if ref.min_score is not None:
            gate &= col >= ref.min_score
        if ref.max_score is not None:
            gate &= col <= ref.max_score

        contributing = gate & (col.abs() > 0.0)
        weighted = col * ref.weight * contributing.astype(float)
        composite = composite + weighted

        # Accumulate firing list
        firing = firing.combine(
            contributing,
            lambda lst, on, rid=ref.id: (lst + [rid]) if on else lst,
        )

        if ref.required:
            required_ok &= contributing

    out = raw.copy()
    out["composite_score"] = composite
    out["required_ok"] = required_ok
    out["firing_factors"] = firing
    out["entry_ok"] = required_ok & (composite >= config.entry.composite_score_min)
    return out
