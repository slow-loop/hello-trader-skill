from __future__ import annotations

from backend2.market import analyze_symbol, get_quote
from backend2.models import (
    AnalysisReport,
    EvaluatedWatchlistConfig,
    EvaluatedWatchlistItem,
    Quote,
    WatchlistConditionResult,
    WatchlistEvaluation,
    WatchlistItem,
    WorkspaceRuntimeConfig,
)
from market_core import MarketProfile, get_market_session
from market_core.technical import _evaluate_expression
from backend2.workspace import load_watchlist

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
)


def load_evaluated_watchlist(
    config: WorkspaceRuntimeConfig,
    profile: MarketProfile,
) -> EvaluatedWatchlistConfig:
    watchlist = load_watchlist(config)
    session = get_market_session(profile)
    items = [evaluate_watchlist_item(item, config, profile, session=session) for item in watchlist.items]
    return EvaluatedWatchlistConfig(items=items)


def evaluate_watchlist_item(
    item: WatchlistItem,
    config: WorkspaceRuntimeConfig,
    profile: MarketProfile,
    *,
    session: dict[str, str | bool] | None = None,
) -> EvaluatedWatchlistItem:
    evaluated = EvaluatedWatchlistItem.model_validate(item.model_dump(mode="python"))
    try:
        snapshot = analyze_symbol(item.symbol, config, profile)
        evaluated.analysis = _build_analysis_report(snapshot)
        if not _has_rules(item):
            return evaluated

        market_session = session or get_market_session(profile)
        context = dict(snapshot.technical_analysis.values)
        live_quote = _get_live_quote(item.symbol, profile, market_session)
        live_price = live_quote.price if live_quote is not None else None
        context["price"] = live_price if live_price is not None else context.get("close")

        evaluation = WatchlistEvaluation(
            trigger_results=_build_trigger_results(item, context),
            invalidation_results=_build_invalidation_results(item, context),
            context_snapshot=_build_snapshot(context),
        )
        evaluation.trigger_met = _resolve_trigger_state(item, evaluation.trigger_results, context)
        evaluation.invalidation_met = _resolve_invalidation_state(item, evaluation.invalidation_results, context)
    except Exception as exc:
        evaluation = WatchlistEvaluation(error=str(exc))

    evaluated.evaluation = evaluation
    return evaluated


def _has_rules(item: WatchlistItem) -> bool:
    return bool(
        item.trigger_conditions
        or item.invalidation_conditions
        or item.trigger_price is not None
        or item.invalidation_price is not None
    )
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


def _build_trigger_results(
    item: WatchlistItem,
    context: dict[str, bool | int | float | str | None],
) -> list[WatchlistConditionResult]:
    if item.trigger_conditions:
        return _evaluate_conditions(item.trigger_conditions, context)
    if item.trigger_price is None:
        return []
    price = context.get("price")
    if not isinstance(price, (int, float)):
        return [WatchlistConditionResult(expr=f"price >= {item.trigger_price}", error="price unavailable")]
    return [
        WatchlistConditionResult(
            expr=f"price >= {item.trigger_price}",
            result=float(price) >= float(item.trigger_price),
        )
    ]


def _build_invalidation_results(
    item: WatchlistItem,
    context: dict[str, bool | int | float | str | None],
) -> list[WatchlistConditionResult]:
    if item.invalidation_conditions:
        return _evaluate_conditions(item.invalidation_conditions, context)
    if item.invalidation_price is None:
        return []
    price = context.get("price")
    if not isinstance(price, (int, float)):
        return [WatchlistConditionResult(expr=f"price <= {item.invalidation_price}", error="price unavailable")]
    return [
        WatchlistConditionResult(
            expr=f"price <= {item.invalidation_price}",
            result=float(price) <= float(item.invalidation_price),
        )
    ]


def _resolve_trigger_state(
    item: WatchlistItem,
    results: list[WatchlistConditionResult],
    context: dict[str, bool | int | float | str | None],
) -> bool:
    if item.trigger_conditions:
        return all(result.result is True for result in results)
    if item.trigger_price is None:
        return False
    price = context.get("price")
    return bool(isinstance(price, (int, float)) and float(price) >= float(item.trigger_price))


def _resolve_invalidation_state(
    item: WatchlistItem,
    results: list[WatchlistConditionResult],
    context: dict[str, bool | int | float | str | None],
) -> bool:
    if item.invalidation_conditions:
        return any(result.result is True for result in results)
    if item.invalidation_price is None:
        return False
    price = context.get("price")
    return bool(isinstance(price, (int, float)) and float(price) <= float(item.invalidation_price))


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
    metrics = {
        key: (round(value, 4) if isinstance(value, float) else value)
        for key, value in snapshot.technical_analysis.values.items()
        if key in (snapshot.technical_config.outputs or ())
    }
    return AnalysisReport(
        symbol=snapshot.symbol,
        quote=snapshot.quote,
        metrics=metrics,
        triggers={tag: names for tag, names in snapshot.technical_analysis.triggers.items() if names},
        warnings=snapshot.technical_analysis.warnings,
        news=[],
    )
