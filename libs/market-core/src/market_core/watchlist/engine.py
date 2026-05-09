"""Watchlist evaluation — runs invalidation_signals against fresh market
data. Stateless; takes a list of items and returns evaluated items. No
I/O — caller handles loading/saving via watchlist.store.

Design note:
  - There is **no** entry/attention signal evaluated here. By design,
    deciding when to enter is an agent judgment call (see TRADING_TW.md),
    not a pre-computed boolean. The agent integrates thesis, regime,
    catalyst freshness, relative strength, concentration, etc. — that
    integration is the value-add of using an LLM agent over a Python
    rule engine.
  - Invalidation IS evaluated automatically. Pre-set kill conditions
    are the "automatic safety net" half of trading; entries are the
    "discretionary judgment" half. Asymmetric on purpose.

Naming convention:
  - invalidation_signals (item)              — kill expressions
  - invalidation_signal_results (eval)       — per-expression results
  - invalidation_active (eval)               — true when any kill expr is true
"""

from __future__ import annotations

from market_core.market import _twse_taiex_quote, analyze_symbol, get_quote
from market_core.models import (
    AnalysisReport,
    EvaluatedWatchlistConfig,
    EvaluatedWatchlistItem,
    MarketRuntimeConfig,
    Quote,
    RelativePerformance,
    WatchlistConditionResult,
    WatchlistConfig,
    WatchlistEvaluation,
    WatchlistItem,
)
from market_core.policies import MarketProfile, get_market_session
from market_core.technical import _evaluate_expression

SNAPSHOT_KEYS = (
    "close",
    "price",
    "change_pct",
    "rsi_14",
    "adx_14",
    "volume_ratio_20",
    "bb_position_ratio",
    "atr_14_pct",
    "stoch_k",
    "macd_histogram",
    "benchmark_change_pct",
    "excess_vs_benchmark_pct",
)


def evaluate_watchlist(
    watchlist: WatchlistConfig,
    config: MarketRuntimeConfig,
    profile: MarketProfile,
) -> EvaluatedWatchlistConfig:
    session = get_market_session(profile)
    benchmark = _resolve_benchmark(config, profile)
    items = [
        evaluate_watchlist_item(item, config, profile, session=session, benchmark=benchmark)
        for item in watchlist.items
    ]
    return EvaluatedWatchlistConfig(items=items)


def evaluate_watchlist_item(
    item: WatchlistItem,
    config: MarketRuntimeConfig,
    profile: MarketProfile,
    *,
    session: dict[str, str | bool] | None = None,
    benchmark: Quote | None = None,
) -> EvaluatedWatchlistItem:
    evaluated = EvaluatedWatchlistItem.model_validate(item.model_dump(mode="python"))
    try:
        snapshot = analyze_symbol(item.symbol, config, profile)
        evaluated.analysis = _build_analysis_report(snapshot)
        if not _has_invalidation_rules(item):
            return evaluated

        market_session = session or get_market_session(profile)
        resolved_benchmark = benchmark if benchmark is not None else _resolve_benchmark(config, profile)

        context = dict(snapshot.extra.get("context") or snapshot.metrics)
        live_quote = _get_live_quote(item.symbol, profile, market_session)
        live_price = live_quote.price if live_quote is not None else None
        context["price"] = live_price if live_price is not None else context.get("close")

        relative = _build_relative_performance(context, resolved_benchmark)
        if relative is not None:
            if relative.benchmark_change_pct is not None:
                context["benchmark_change_pct"] = relative.benchmark_change_pct
            if relative.excess_vs_benchmark_pct is not None:
                context["excess_vs_benchmark_pct"] = relative.excess_vs_benchmark_pct

        evaluation = WatchlistEvaluation(
            invalidation_signal_results=_build_invalidation_signal_results(item, context),
            context_snapshot=_build_snapshot(context),
            relative_performance=relative,
        )
        evaluation.invalidation_active = _resolve_invalidation_active(
            item, evaluation.invalidation_signal_results, context
        )
    except Exception as exc:
        evaluation = WatchlistEvaluation(error=str(exc))

    evaluated.evaluation = evaluation
    return evaluated


def _resolve_benchmark(config: MarketRuntimeConfig, profile: MarketProfile) -> Quote | None:
    symbol = config.market.benchmark_symbol or profile.benchmark_symbol
    if not symbol:
        return None
    if profile.id == "tw_equity" and symbol.upper() in {"^TWII", "TAIEX"}:
        quote = _twse_taiex_quote(profile)
        if quote is not None:
            return quote
    try:
        return get_quote(symbol, profile)
    except Exception:
        return None


def _build_relative_performance(
    context: dict[str, bool | int | float | str | None],
    benchmark: Quote | None,
) -> RelativePerformance | None:
    if benchmark is None:
        return None
    symbol_change = context.get("change_pct")
    symbol_change_val = float(symbol_change) if isinstance(symbol_change, (int, float)) else None
    benchmark_change = benchmark.change_pct
    excess = (
        round(symbol_change_val - benchmark_change, 4)
        if symbol_change_val is not None and benchmark_change is not None
        else None
    )
    return RelativePerformance(
        symbol_change_pct=symbol_change_val,
        benchmark_symbol=benchmark.symbol,
        benchmark_change_pct=benchmark_change,
        excess_vs_benchmark_pct=excess,
    )


def _has_invalidation_rules(item: WatchlistItem) -> bool:
    return bool(item.invalidation_signals)


def _get_live_quote(
    symbol: str,
    profile: MarketProfile,
    session: dict[str, str | bool],
) -> Quote | None:
    if not session.get("is_open"):
        return None
    try:
        return get_quote(symbol, profile)
    except Exception:
        return None


def _evaluate_conditions(
    conditions: list[str],
    context: dict[str, bool | int | float | str | None],
) -> list[WatchlistConditionResult]:
    results: list[WatchlistConditionResult] = []
    for expr in conditions:
        try:
            value = _evaluate_expression(expr, context)
            results.append(WatchlistConditionResult(expr=expr, result=bool(value)))
        except Exception as exc:
            results.append(WatchlistConditionResult(expr=expr, error=str(exc)))
    return results


def _build_invalidation_signal_results(
    item: WatchlistItem,
    context: dict[str, bool | int | float | str | None],
) -> list[WatchlistConditionResult]:
    return _evaluate_conditions(item.invalidation_signals, context) if item.invalidation_signals else []


def _resolve_invalidation_active(
    item: WatchlistItem,
    results: list[WatchlistConditionResult],
    context: dict[str, bool | int | float | str | None],
) -> bool:
    return bool(item.invalidation_signals) and any(result.result is True for result in results)


def _build_snapshot(context: dict[str, bool | int | float | str | None]) -> dict[str, object]:
    snapshot: dict[str, object] = {}
    for key in SNAPSHOT_KEYS:
        value = context.get(key)
        if value is None:
            continue
        if isinstance(value, float):
            snapshot[key] = round(value, 4)
        else:
            snapshot[key] = value
    return snapshot


def _build_analysis_report(snapshot) -> AnalysisReport:
    return AnalysisReport(
        symbol=snapshot.symbol,
        quote=snapshot.quote,
        metrics=snapshot.metrics,
        triggers={tag: names for tag, names in snapshot.triggers.items() if names},
        warnings=snapshot.warnings,
        news=[],
    )
