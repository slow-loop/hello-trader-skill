import pandas as pd
import numpy as np
import pytest
from backend.core.technical_engine import (
    _coerce_expression_value,
    _evaluate_expression,
    _candle_metrics,
    _compute_levels,
    IndicatorSpec,
    compute_base_values
)

def test_coerce_expression_value():
    assert _coerce_expression_value(True) is True
    assert _coerce_expression_value(1) == 1
    assert _coerce_expression_value(1.5) == 1.5
    assert _coerce_expression_value(np.float64(1.5)) == 1.5
    assert _coerce_expression_value(np.nan) is None
    assert _coerce_expression_value(None) is None
    assert _coerce_expression_value("hello") == "hello"
    with pytest.raises(TypeError):
        _coerce_expression_value([])

def test_evaluate_expression():
    names = {"rsi": 75, "sma": 100}
    assert _evaluate_expression("rsi > 70", names) is True
    assert _evaluate_expression("rsi < 70", names) is False
    assert _evaluate_expression("rsi + 5", names) == 80
    assert _evaluate_expression("abs(-10)", names) == 10

def test_candle_metrics():
    row = pd.Series({"open": 100, "high": 110, "low": 95, "close": 105})
    metrics = _candle_metrics(row)
    assert metrics["body"] == 5.0
    assert metrics["body_abs"] == 5.0
    assert metrics["full_range"] == 15.0
    assert metrics["upper_shadow"] == 5.0
    assert metrics["lower_shadow"] == 5.0

    row_red = pd.Series({"open": 105, "high": 110, "low": 95, "close": 100})
    metrics_red = _candle_metrics(row_red)
    assert metrics_red["body"] == -5.0
    assert metrics_red["body_abs"] == 5.0

def test_compute_levels():
    # Create a dummy dataframe with some swing points
    data = {
        "close": [10, 11, 12, 11, 10, 9, 8, 9, 10, 11, 12, 13, 14, 13, 12] * 5,
        "high":  [10.5, 11.5, 12.5, 11.5, 10.5, 9.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 13.5, 12.5] * 5,
        "low":   [9.5, 10.5, 11.5, 10.5, 9.5, 8.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 12.5, 11.5] * 5
    }
    df = pd.DataFrame(data)
    levels = _compute_levels(df, lookback=60)
    assert "nearest_support" in levels
    assert "nearest_resistance" in levels
    assert levels["nearest_support"] < df["close"].iloc[-1]
    assert levels["nearest_resistance"] >= df["close"].iloc[-1]

def test_compute_base_values():
    # Minimum 20 rows for volume average
    data = {
        "open": [100] * 25,
        "high": [110] * 25,
        "low": [90] * 25,
        "close": [105] * 25,
        "volume": [1000] * 25
    }
    df = pd.DataFrame(data)
    indicators = [IndicatorSpec(name="rsi_14", ta_fn="rsi", params={"length": 14})]
    
    values, warnings = compute_base_values(df, indicators)
    assert values["close"] == 105
    assert values["prev_close"] == 105
    assert "rsi_14" in values
    assert values["avg_volume_20"] == 1000.0
