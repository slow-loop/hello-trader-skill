"""Strategy-level backtest (thin wrapper around vectorbt).

Takes a strategy config + a feature panel, derives entry/exit signals from
`apply_strategy`, and runs vectorbt's Portfolio.from_signals to produce
Sharpe / drawdown / equity curve.

Entry: first bar where entry_ok flips True.
Exit:  either composite_score drops below 0 (thesis gone) OR
       price breaks stop (ATR-based, approximated from features).

This is intentionally simple: we want to measure whether the *factor
combination* has edge, not to optimize execution micro-structure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from market_core.strategy import StrategyConfig, apply_strategy


@dataclass
class StrategyBTResult:
    strategy_name: str
    period: str
    universe_size: int
    sharpe: float
    total_return: float
    max_drawdown: float
    calmar: float
    turnover: float
    num_trades: int
    equity_curve: pd.Series
    raw_portfolio: Any | None = None


def _require_vectorbt():
    try:
        import vectorbt as vbt  # noqa: F401
        return vbt
    except ImportError as exc:
        raise RuntimeError(
            "vectorbt not installed. Install market-core[backtest]."
        ) from exc


def run_strategy_backtest(
    config: StrategyConfig,
    features_by_symbol: dict[str, pd.DataFrame],
    *,
    init_cash: float = 100_000.0,
    fees: float = 0.001,
    slippage: float = 0.0005,
    stop_atr_multiple: float = 1.5,
) -> StrategyBTResult:
    """Run the strategy across all symbols, pool results into a single portfolio."""
    vbt = _require_vectorbt()

    # Build signal panel + price panel aligned by date × symbol.
    entries_by_sym: dict[str, pd.Series] = {}
    exits_by_sym: dict[str, pd.Series] = {}
    prices_by_sym: dict[str, pd.Series] = {}

    for sym, feat in features_by_symbol.items():
        sig = apply_strategy(config, feat)
        entries = sig["entry_ok"].astype(bool).fillna(False)
        # Exit when composite score flips below 0 OR stop hit (ATR-based).
        composite = sig["composite_score"].fillna(0.0)
        exit_signal = composite < 0.0

        entries_by_sym[sym] = entries
        exits_by_sym[sym] = exit_signal
        prices_by_sym[sym] = feat["close"]

    prices = pd.DataFrame(prices_by_sym).sort_index()
    entries_df = pd.DataFrame(entries_by_sym).reindex_like(prices).fillna(False)
    exits_df = pd.DataFrame(exits_by_sym).reindex_like(prices).fillna(False)

    pf = vbt.Portfolio.from_signals(
        prices,
        entries_df,
        exits_df,
        init_cash=init_cash,
        fees=fees,
        slippage=slippage,
        freq="1D",
    )

    # Aggregate across symbols (equal-weighted at portfolio level).
    def _agg(series_or_scalar) -> float:
        if hasattr(series_or_scalar, "replace"):
            s = series_or_scalar.replace([np.inf, -np.inf], np.nan).dropna()
            return float(s.mean()) if len(s) else float("nan")
        return float(series_or_scalar)

    total_ret = _agg(pf.total_return())
    sharpe = _agg(pf.sharpe_ratio())
    max_dd = _agg(pf.max_drawdown())
    calmar = total_ret / abs(max_dd) if max_dd and not np.isnan(max_dd) and max_dd != 0 else float("nan")
    # Rough turnover proxy
    num_trades = int(pf.trades.count().sum() if hasattr(pf.trades.count(), "sum") else pf.trades.count())
    trading_days = max(1, len(prices))
    turnover = num_trades / trading_days

    equity = pf.value().mean(axis=1) if isinstance(pf.value(), pd.DataFrame) else pf.value()

    period = f"{prices.index.min().date()}..{prices.index.max().date()}"

    return StrategyBTResult(
        strategy_name=config.name,
        period=period,
        universe_size=prices.shape[1],
        sharpe=sharpe,
        total_return=total_ret,
        max_drawdown=max_dd,
        calmar=calmar,
        turnover=turnover,
        num_trades=num_trades,
        equity_curve=equity,
        raw_portfolio=pf,
    )
