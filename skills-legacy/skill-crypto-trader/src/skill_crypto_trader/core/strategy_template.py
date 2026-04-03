"""Jinja2-based code generator for freqtrade IStrategy classes."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Template

from skill_crypto_trader.journal.helpers import get_strategy_dir

STRATEGY_TEMPLATE = Template('''\
"""{{ description }}

Auto-generated strategy for freqtrade.
Regime: {{ regime }}
"""

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter
from pandas import DataFrame
import talib.abstract as ta


class {{ class_name }}(IStrategy):
    """{{ description }}"""

    INTERFACE_VERSION = 3
    timeframe = "{{ timeframe }}"
    startup_candle_count: int = {{ startup_candle_count }}

    # ROI table
    minimal_roi = {{ minimal_roi }}

    # Stoploss (mandatory)
    stoploss = {{ stoploss }}

    # Trailing stop
    trailing_stop = {{ trailing_stop }}
    {% if trailing_stop %}trailing_stop_positive = {{ trailing_stop_positive }}
    trailing_stop_positive_offset = {{ trailing_stop_positive_offset }}
    trailing_only_offset_is_reached = True{% endif %}

    # Hyperopt parameters
    {% for param in parameters %}
    {{ param.name }} = {{ param.type }}({{ param.default }}, {{ param.low }}, {{ param.high }}, space="{{ param.space }}")
    {% endfor %}

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        {{ populate_indicators | indent(8) }}
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        {{ populate_entry_trend | indent(8) }}
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        {{ populate_exit_trend | indent(8) }}
        return dataframe
''')


def render_strategy(
    name: str,
    *,
    description: str = "",
    regime: str = "any",
    timeframe: str = "1h",
    startup_candle_count: int = 50,
    minimal_roi: str = '{"0": 0.1, "60": 0.05, "120": 0.01}',
    stoploss: float = -0.05,
    trailing_stop: bool = True,
    trailing_stop_positive: float = 0.02,
    trailing_stop_positive_offset: float = 0.04,
    parameters: list[dict] | None = None,
    populate_indicators: str = "# Add indicators here\\npass",
    populate_entry_trend: str = "# Add entry conditions here\\npass",
    populate_exit_trend: str = "# Add exit conditions here\\npass",
) -> str:
    # Convert snake_case name to PascalCase class name
    class_name = "".join(part.capitalize() for part in name.split("_"))
    return STRATEGY_TEMPLATE.render(
        class_name=class_name,
        description=description,
        regime=regime,
        timeframe=timeframe,
        startup_candle_count=startup_candle_count,
        minimal_roi=minimal_roi,
        stoploss=stoploss,
        trailing_stop=trailing_stop,
        trailing_stop_positive=trailing_stop_positive,
        trailing_stop_positive_offset=trailing_stop_positive_offset,
        parameters=parameters or [],
        populate_indicators=populate_indicators,
        populate_entry_trend=populate_entry_trend,
        populate_exit_trend=populate_exit_trend,
    )


def write_strategy(name: str, code: str) -> Path:
    """Write strategy code to freqtrade_userdata/strategies/."""
    class_name = "".join(part.capitalize() for part in name.split("_"))
    path = get_strategy_dir() / f"{class_name}.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)
    return path
