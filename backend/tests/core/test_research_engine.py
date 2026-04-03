from unittest.mock import patch
from pathlib import Path
from backend.core.research_engine import _inject_into_section, _build_tech_summary, _build_chips_summary_text

def test_inject_into_section():
    content = "## Header 1\nExisting content\n## Header 2\nOther content"
    injected = _inject_into_section(content, "## Header 1", "New content\n")
    assert "## Header 1\nExisting content\nNew content\n## Header 2" in injected

def test_inject_into_section_missing_header():
    content = "## Header 1\nContent"
    injected = _inject_into_section(content, "## Header 2", "New stuff")
    assert "## Header 2\nNew stuff" in injected

def test_build_tech_summary():
    analysis = {
        "quote": {"name": "TSMC", "price": 600, "change_pct": 1.5},
        "metrics": {"adx_14": 25, "rsi_14": 65},
        "triggers": {"bullish": ["Golden Cross"], "momentum": ["Strong"]}
    }
    summary = _build_tech_summary(analysis)
    assert "**價格**: 600" in summary
    assert "Change: 1.5%" in summary
    assert "ADX 25" in summary
    assert "Golden Cross, Strong" in summary

def test_build_chips_summary_text():
    analysis = {
        "chips": {
            "trade_date": "2025-01-01",
            "foreign_net": 1000,
            "margin_balance": 500,
            "margin_balance_trend": "INCREASING",
            "foreign_investors": "NET_BUY_3_DAYS"
        }
    }
    summary = _build_chips_summary_text(analysis)
    assert "**籌碼日期**: 2025-01-01" in summary
    assert "外資 1000" in summary
    assert "500 (INCREASING)" in summary
