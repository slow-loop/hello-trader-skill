from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import yaml

from skill_tw_trader.core.account_paths import RESEARCH_DIR, RESEARCH_TEMPLATES_DIR, WATCHLIST_FILE
from skill_tw_trader.core.market_service import build_stock_analysis
from skill_tw_trader.core.market_data.symbols import normalize_symbol, strip_suffix


def init_research_file(symbol: str) -> Path:
    normalized = normalize_symbol(symbol)
    analysis = build_stock_analysis(normalized)
    
    template_path = RESEARCH_TEMPLATES_DIR / "template.md"
    if not template_path.exists():
        # Fallback to a basic template if missing
        content = f"# 台股深度研究：{analysis['quote']['name']} ({normalized})\n\n日期: {date.today().isoformat()}\n標的: {normalized}\n"
    else:
        content = template_path.read_text(encoding="utf-8")
        
    # Replacements
    content = content.replace("YYYY-MM-DD", date.today().isoformat())
    content = content.replace("0000.TW", normalized)
    
    # Fill in names if possible
    if "標的:" in content:
        content = content.replace(f"標的: {normalized}", f"標的: {normalized}（{analysis['quote']['name']}）")

    # Add Technical Data to Technical section
    tech_summary = _build_tech_summary(analysis)
    content = _inject_into_section(content, "## 技術面與籌碼", tech_summary)
    
    # Add Chips Data to Chips section
    chips_summary = _build_chips_summary_text(analysis)
    content = _inject_into_section(content, "## 原始資料確認", chips_summary)

    # Output file path
    ticker_id = strip_suffix(normalized).lower()
    filename = f"{date.today().isoformat()}-tw-{ticker_id}.md"
    output_path = RESEARCH_DIR / filename
    
    output_path.write_text(content, encoding="utf-8")
    return output_path


def _build_tech_summary(analysis: dict) -> str:
    metrics = analysis.get("metrics", {})
    triggers = analysis.get("triggers", {})
    
    lines = [
        f"- **價格**: {analysis['quote']['price']} (Change: {analysis['quote']['change_pct']}%)",
        f"- **趨勢指標**: ADX {metrics.get('adx_14')}, RSI {metrics.get('rsi_14')}",
        f"- **動能指標**: MACD Histogram {metrics.get('macd_histogram')}, Stoch K {metrics.get('stoch_k')}",
        f"- **關鍵訊號**: {', '.join(triggers.get('bullish', []) + triggers.get('momentum', []))}",
    ]
    return "\n" + "\n".join(lines) + "\n"


def _build_chips_summary_text(analysis: dict) -> str:
    chips = analysis.get("chips", {})
    if not chips:
        return "\n- (無籌碼資料)\n"
    
    lines = [
        f"- **籌碼日期**: {chips.get('trade_date')}",
        f"- **法人買賣超**: 外資 {chips.get('foreign_net')}, 投信 {chips.get('trust_net')}, 自營 {chips.get('dealer_net')}",
        f"- **融資餘額**: {chips.get('margin_balance')} ({chips.get('margin_balance_trend')})",
        f"- **法人連買**: 外資 {chips.get('foreign_investors')}, 投信 {chips.get('investment_trust')}",
    ]
    return "\n" + "\n".join(lines) + "\n"


def _inject_into_section(content: str, section_header: str, injection: str) -> str:
    if section_header not in content:
        return content + f"\n\n{section_header}\n{injection}"
    
    # Find the next header or the end of the file
    pattern = rf"({re.escape(section_header)}.*?\n)(#|$)"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        return content[:match.end(1)] + injection + content[match.start(2):]
    
    # Simple append if pattern doesn't match for some reason
    return content.replace(section_header, f"{section_header}\n{injection}")
