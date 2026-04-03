from __future__ import annotations

from typing import Callable, TypeAlias

import numpy as np
import pandas as pd
import pandas_ta as ta
from pydantic import BaseModel, Field
from simpleeval import simple_eval

ScalarValue: TypeAlias = bool | int | float | str | None
IndicatorParamValue: TypeAlias = bool | int | float | str
IndicatorParams: TypeAlias = dict[str, IndicatorParamValue]
ExpressionContext: TypeAlias = dict[str, ScalarValue]

SAFE_FUNCTIONS: dict[str, Callable[..., object]] = {
    "abs": abs,
    "bool": bool,
    "float": float,
    "int": int,
    "max": max,
    "min": min,
    "round": round,
}


class IndicatorSpec(BaseModel):
    name: str
    ta_fn: str
    params: IndicatorParams = Field(default_factory=dict)


class ExpressionSpec(BaseModel):
    name: str
    expr: str
    tags: list[str] = Field(default_factory=list)


class AnalysisConfig(BaseModel):
    indicators: list[IndicatorSpec] = Field(default_factory=list)
    expressions: list[ExpressionSpec] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)


class ExpressionResult(BaseModel):
    name: str
    expr: str
    value: ScalarValue
    tags: list[str] = Field(default_factory=list)


class TechnicalAnalysis(BaseModel):
    values: ExpressionContext
    expressions: list[ExpressionResult]
    triggers: dict[str, list[str]]
    warnings: list[str]


def default_analysis_config() -> AnalysisConfig:
    return AnalysisConfig(
        indicators=[
            IndicatorSpec(name="rsi_14", ta_fn="rsi", params={"length": 14}),
            IndicatorSpec(name="macd", ta_fn="macd", params={"fast": 12, "slow": 26, "signal": 9}),
            IndicatorSpec(name="sma_20", ta_fn="sma", params={"length": 20}),
            IndicatorSpec(name="sma_50", ta_fn="sma", params={"length": 50}),
            IndicatorSpec(name="ema_20", ta_fn="ema", params={"length": 20}),
            IndicatorSpec(name="ema_50", ta_fn="ema", params={"length": 50}),
            IndicatorSpec(name="bb", ta_fn="bbands", params={"length": 20, "std": 2.0}),
            IndicatorSpec(name="atr_14", ta_fn="atr", params={"length": 14}),
            IndicatorSpec(name="obv", ta_fn="obv", params={}),
            IndicatorSpec(name="stoch", ta_fn="stoch", params={"k": 14, "d": 3, "smooth_k": 3}),
            IndicatorSpec(name="adx", ta_fn="adx", params={"length": 14}),
        ],
        outputs=[
            "change_pct",
            "volume_ratio_20",
            "rsi_14",
            "adx_14",
            "macd_histogram",
            "sma_20",
            "sma_50",
            "ema_20",
            "ema_50",
            "bb_position_ratio",
            "atr_14_pct",
            "nearest_support",
            "nearest_resistance",
        ],
    )


def build_technical_analysis(
    df: pd.DataFrame,
    config: AnalysisConfig | None = None,
) -> TechnicalAnalysis:
    normalized_config = config or default_analysis_config()
    values, warnings = compute_base_values(df, normalized_config.indicators or default_analysis_config().indicators)
    final_values, expression_results, triggers, expression_errors = _evaluate_named_expressions(
        normalized_config.expressions,
        values,
    )
    warnings.extend(expression_errors)
    return TechnicalAnalysis(
        values=final_values,
        expressions=expression_results,
        triggers=triggers,
        warnings=warnings,
    )


def compute_base_values(
    df: pd.DataFrame,
    indicators: list[IndicatorSpec],
) -> tuple[ExpressionContext, list[str]]:
    if len(df) < 2:
        raise ValueError("not enough rows for analysis")

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    values: ExpressionContext = {}
    warnings: list[str] = []

    for field in ("open", "high", "low", "close"):
        values[field] = _maybe_float(latest.get(field))
        values[f"prev_{field}"] = _maybe_float(prev.get(field))
        if len(df) >= 6:
            values[f"prev5_{field}"] = _maybe_float(df[field].iloc[-6])

    values["volume"] = _maybe_int(latest.get("volume"))
    values["prev_volume"] = _maybe_int(prev.get("volume"))
    if len(df) >= 6:
        values["prev5_volume"] = _maybe_int(df["volume"].iloc[-6])

    close = values.get("close")
    prev_close = values.get("prev_close")
    if isinstance(close, (int, float)) and isinstance(prev_close, (int, float)) and prev_close != 0:
        values["change_pct"] = round((close - prev_close) / prev_close * 100, 4)

    if len(df) >= 20:
        avg_volume = float(df["volume"].tail(20).fillna(0).mean())
        values["avg_volume_20"] = round(avg_volume, 4)
        volume = values.get("volume")
        if isinstance(volume, int) and avg_volume > 0:
            values["volume_ratio_20"] = round(volume / avg_volume, 4)

    values.update(_candle_metrics(latest))
    for key, value in _candle_metrics(prev).items():
        values[f"prev_{key}"] = value
    values.update(_compute_levels(df, lookback=20))

    indicator_values: dict[str, pd.Series] = {}
    for item in indicators:
        result, item_warnings = _indicator_series(df, item)
        indicator_values.update(result)
        warnings.extend(item_warnings)

    for name, series in indicator_values.items():
        current_value = _maybe_float(series.iloc[-1]) if len(series) >= 1 else None
        prev_value = _maybe_float(series.iloc[-2]) if len(series) >= 2 else None
        values[name] = current_value
        values[f"prev_{name}"] = prev_value
        if len(series) >= 6:
            values[f"prev5_{name}"] = _maybe_float(series.iloc[-6])

    atr_14 = values.get("atr_14")
    if isinstance(atr_14, (int, float)) and isinstance(close, (int, float)) and close != 0:
        values["atr_14_pct"] = round(atr_14 / close * 100, 4)

    bb_upper = values.get("bb_upper")
    bb_lower = values.get("bb_lower")
    if (
        isinstance(bb_upper, (int, float))
        and isinstance(bb_lower, (int, float))
        and isinstance(close, (int, float))
    ):
        band_width = bb_upper - bb_lower
        values["bb_band_width"] = round(band_width, 4)
        if close != 0:
            values["bb_band_width_pct"] = round(band_width / close * 100, 4)
        if band_width > 0:
            values["bb_position_ratio"] = round((close - bb_lower) / band_width, 4)

    return values, warnings


def _coerce_expression_value(value: object) -> ScalarValue:
    if isinstance(value, np.generic):
        return _coerce_expression_value(value.item())
    if value is None:
        return None
    if isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if np.isnan(value):
            return None
        return value
    raise TypeError(f"unsupported expression result type: {type(value).__name__}")


def _evaluate_expression(expr: str, names: ExpressionContext) -> ScalarValue:
    return _coerce_expression_value(simple_eval(expr, names=names, functions=SAFE_FUNCTIONS))


def _evaluate_named_expressions(
    expressions: list[ExpressionSpec],
    base_context: ExpressionContext,
) -> tuple[ExpressionContext, list[ExpressionResult], dict[str, list[str]], list[str]]:
    context = dict(base_context)
    results: list[ExpressionResult] = []
    triggers: dict[str, list[str]] = {}
    errors: list[str] = []

    for item in expressions:
        if item.name in context:
            errors.append(f"{item.name}: expression name already exists")
            continue
        try:
            value = _evaluate_expression(item.expr, context)
        except Exception as exc:
            errors.append(f"{item.name}: {exc}")
            continue

        context[item.name] = value
        results.append(ExpressionResult(name=item.name, expr=item.expr, value=value, tags=item.tags))
        if value is True:
            for tag in item.tags:
                triggers.setdefault(tag, []).append(item.name)

    return context, results, triggers, errors


def _indicator_series(df: pd.DataFrame, item: IndicatorSpec) -> tuple[dict[str, pd.Series], list[str]]:
    ta_fn = item.ta_fn.strip().lower()
    close = df["close"]
    params = item.params

    try:
        if ta_fn == "rsi":
            length = int(params.get("length", 14))
            series = ta.rsi(close, length=length)
            return ({item.name: series}, []) if series is not None else ({}, [f"{item.name} returned no data"])

        if ta_fn == "sma":
            length = int(params.get("length", 20))
            series = ta.sma(close, length=length)
            return ({item.name: series}, []) if series is not None else ({}, [f"{item.name} returned no data"])

        if ta_fn == "ema":
            length = int(params.get("length", 20))
            series = ta.ema(close, length=length)
            return ({item.name: series}, []) if series is not None else ({}, [f"{item.name} returned no data"])

        if ta_fn == "macd":
            macd_df = ta.macd(
                close,
                fast=int(params.get("fast", 12)),
                slow=int(params.get("slow", 26)),
                signal=int(params.get("signal", 9)),
            )
            if macd_df is None or macd_df.empty:
                return {}, [f"{item.name} returned no data"]
            cols = list(macd_df.columns)
            return {
                f"{item.name}_line": macd_df[cols[0]],
                f"{item.name}_signal": macd_df[cols[1]],
                f"{item.name}_histogram": macd_df[cols[2]],
            }, []

        if ta_fn == "bbands":
            bb_df = ta.bbands(
                close,
                length=int(params.get("length", 20)),
                std=float(params.get("std", 2.0)),
            )
            if bb_df is None or bb_df.empty:
                return {}, [f"{item.name} returned no data"]
            upper_col = next((col for col in bb_df.columns if "BBU" in col), None)
            mid_col = next((col for col in bb_df.columns if "BBM" in col), None)
            lower_col = next((col for col in bb_df.columns if "BBL" in col), None)
            result: dict[str, pd.Series] = {}
            if upper_col:
                result[f"{item.name}_upper"] = bb_df[upper_col]
            if mid_col:
                result[f"{item.name}_mid"] = bb_df[mid_col]
            if lower_col:
                result[f"{item.name}_lower"] = bb_df[lower_col]
            return result, []

        if ta_fn == "atr":
            series = ta.atr(df["high"], df["low"], close, length=int(params.get("length", 14)))
            return ({item.name: series}, []) if series is not None else ({}, [f"{item.name} returned no data"])

        if ta_fn == "obv":
            series = ta.obv(close, df["volume"])
            return ({item.name: series}, []) if series is not None else ({}, [f"{item.name} returned no data"])

        if ta_fn == "stoch":
            stoch_df = ta.stoch(
                df["high"],
                df["low"],
                close,
                k=int(params.get("k", 14)),
                d=int(params.get("d", 3)),
                smooth_k=int(params.get("smooth_k", 3)),
            )
            if stoch_df is None or stoch_df.empty:
                return {}, [f"{item.name} returned no data"]
            columns = list(stoch_df.columns)
            return {
                f"{item.name}_k": stoch_df[columns[0]],
                f"{item.name}_d": stoch_df[columns[1]],
            }, []

        if ta_fn == "adx":
            length = int(params.get("length", 14))
            adx_df = ta.adx(df["high"], df["low"], close, length=length)
            if adx_df is None or adx_df.empty:
                return {}, [f"{item.name} returned no data"]
            cols = list(adx_df.columns)
            return {
                f"{item.name}_{length}": adx_df[cols[0]],
                f"{item.name}_pos": adx_df[cols[1]],
                f"{item.name}_neg": adx_df[cols[2]],
            }, []
    except Exception as exc:
        return {}, [f"{item.name} failed: {exc}"]

    return {}, [f"unsupported indicator: {item.ta_fn}"]


def _candle_metrics(row: pd.Series) -> dict[str, float | None]:
    open_ = _maybe_float(row.get("open"))
    high = _maybe_float(row.get("high"))
    low = _maybe_float(row.get("low"))
    close = _maybe_float(row.get("close"))
    if None in (open_, high, low, close):
        return {"body": None, "body_abs": None, "full_range": None, "upper_shadow": None, "lower_shadow": None}

    body = close - open_
    body_abs = abs(body)
    full_range = high - low
    upper_shadow = high - max(open_, close)
    lower_shadow = min(open_, close) - low
    return {
        "body": round(body, 4),
        "body_abs": round(body_abs, 4),
        "full_range": round(full_range, 4),
        "upper_shadow": round(upper_shadow, 4),
        "lower_shadow": round(lower_shadow, 4),
    }


def _compute_levels(df: pd.DataFrame, lookback: int = 60) -> dict[str, float | None]:
    if len(df) < 10:
        return {}
    current_price = _maybe_float(df["close"].iloc[-1])
    if current_price is None:
        return {}

    window = 5
    df_copy = df.copy()
    df_copy["is_swing_high"] = df_copy["high"] == df_copy["high"].rolling(window, center=True).max()
    df_copy["is_swing_low"] = df_copy["low"] == df_copy["low"].rolling(window, center=True).min()

    recent = df_copy.iloc[-lookback:]
    swing_highs = recent[recent["is_swing_high"]]["high"].unique()
    swing_lows = recent[recent["is_swing_low"]]["low"].unique()

    recent_high = float(recent["high"].max())
    recent_low = float(recent["low"].min())
    resistances = sorted(float(h) for h in swing_highs if float(h) > current_price)
    supports = sorted((float(l) for l in swing_lows if float(l) < current_price), reverse=True)

    nearest_resistance = resistances[0] if resistances else recent_high
    nearest_support = supports[0] if supports else recent_low
    return {
        "nearest_support": round(nearest_support, 2),
        "nearest_resistance": round(nearest_resistance, 2),
        "dist_to_support_pct": round((nearest_support - current_price) / current_price * 100, 2),
        "dist_to_resistance_pct": round((nearest_resistance - current_price) / current_price * 100, 2),
        "recent_high_lookback": round(recent_high, 2),
        "recent_low_lookback": round(recent_low, 2),
    }


def _maybe_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _maybe_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
