from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
import yaml

import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from skill_tw_trader import PROJECT_ROOT
from skill_tw_trader.core.account_paths import WATCHLIST_FILE
from skill_tw_trader.core.market_service import get_history_dataframe
from skill_tw_trader.core.technical_engine import (
    build_technical_analysis,
    get_expression_definitions,
    get_indicator_definitions,
    load_analysis_config,
)

# CJK Font setup
def setup_cjk_font():
    # Priority for macOS font family names
    mac_families = [
        "Heiti TC",
        "STHeiti",
        "PingFang HK",
        "Arial Unicode MS"
    ]
    # Get all available font names in the system
    available_fonts = {f.name for f in fm.fontManager.ttflist}
    target_family = "sans-serif"
    for family in mac_families:
        if family in available_fonts:
            target_family = family
            break
            
    # Set global defaults
    plt.rcParams['font.sans-serif'] = [target_family, 'sans-serif']
    plt.rcParams['font.family'] = target_family
    plt.rcParams['axes.unicode_minus'] = False 
    
    # Get absolute path for FontProperties to be extra sure
    try:
        font_path = fm.findfont(target_family)
        return target_family, font_path
    except:
        return target_family, None

font_family, font_file = setup_cjk_font()
font_prop = fm.FontProperties(fname=font_file) if font_file else fm.FontProperties(family=font_family)

CHARTS_DIR = PROJECT_ROOT / "data" / "market" / "charts"

def extract_numbers(text: str) -> list[float]:
    """Extract numbers from a string like '266.5-270' or '突破 285'."""
    if not text or not isinstance(text, str):
        return []
    nums = re.findall(r"(\d+\.?\d*)", text)
    return [float(n) for n in nums]

def get_agent_plan(symbol: str) -> dict:
    """Read the default account watchlist and extract trigger and invalidation levels."""
    if not WATCHLIST_FILE.exists():
        return {}
    
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    if not data or not isinstance(data, list):
        return {}
    
    item = next((i for i in data if i.get("symbol") == symbol), None)
    if not item:
        return {}
    
    plan = {"thesis": item.get("thesis", "")}
    triggers = extract_numbers(item.get("trigger", ""))
    if triggers:
        plan["trigger"] = triggers[-1] 
        
    invals = extract_numbers(item.get("invalidation", ""))
    if invals:
        plan["invalidation"] = invals[0]
        
    return plan

def plot_symbol(symbol: str, days: int = 150) -> Path:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Fetch data
    df = get_history_dataframe(symbol, days=days)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    
    # 2. Tech Analysis (Machine Data)
    config = load_analysis_config()
    analysis = build_technical_analysis(
        df.reset_index(), 
        indicators=get_indicator_definitions(config),
        expressions=get_expression_definitions(config)
    )
    
    # 3. Agent's Plan (Brain Data)
    plan = get_agent_plan(symbol)
    
    # 4. Construct Plot Elements
    addplot = []
    import pandas_ta as ta
    df["sma20"] = ta.sma(df["close"], length=20)
    df["sma50"] = ta.sma(df["close"], length=50)
    addplot.append(mpf.make_addplot(df["sma20"], color='#a78bfa', width=1.0))
    addplot.append(mpf.make_addplot(df["sma50"], color='#fbbf24', width=1.0))

    df["rsi"] = ta.rsi(df["close"], length=14)
    addplot.append(mpf.make_addplot(df["rsi"], panel=2, color='#fbbf24', ylabel='RSI', width=1.0))
    
    reversals = [e.name for e in analysis.expressions if e.value is True and "reversal" in e.tags]
    candles = [e.name for e in analysis.expressions if e.value is True and "candle" in e.tags]
    if any("bullish" in s for s in candles + reversals):
        marker_data = [float('nan')] * len(df)
        marker_data[-1] = df["low"].iloc[-1] * 0.97
        addplot.append(mpf.make_addplot(marker_data, scatter=True, markersize=100, marker='^', color='cyan'))
    
    # 5. Define HLines for S/R and Agent Plan
    hlines_vals = []
    hlines_colors = []
    hlines_styles = []
    
    if "nearest_support" in analysis.values:
        hlines_vals.append(analysis.values["nearest_support"])
        hlines_colors.append('#404040')
        hlines_styles.append('--')
    if "nearest_resistance" in analysis.values:
        hlines_vals.append(analysis.values["nearest_resistance"])
        hlines_colors.append('#404040')
        hlines_styles.append('--')
        
    ai_trigger = plan.get("trigger")
    ai_invalidation = plan.get("invalidation")
    if ai_trigger:
        hlines_vals.append(ai_trigger)
        hlines_colors.append('#10b981') 
        hlines_styles.append('-')
        
    if ai_invalidation:
        hlines_vals.append(ai_invalidation)
        hlines_colors.append('#ef4444') 
        hlines_styles.append('-')
        
    # 6. Final Plot
    chart_path = CHARTS_DIR / f"{symbol.replace('.', '_')}_candles.png"
    
    # Force black background globally for this figure
    plt.rcParams['figure.facecolor'] = 'black'
    plt.rcParams['axes.facecolor'] = 'black'
    plt.rcParams['savefig.facecolor'] = 'black'
    
    mc = mpf.make_marketcolors(up='#26a69a', down='#ef5350', edge='inherit', wick='inherit', volume='in')
    s = mpf.make_mpf_style(base_mpl_style='dark_background', marketcolors=mc, gridcolor='#262626', facecolor='#000000', edgecolor='#000000')
    
    # 8. Create Figure with GridSpec for strict separation
    import textwrap
    thesis_text = plan.get("thesis", "Technical Analysis Report")
    wrapped_lines = textwrap.wrap(thesis_text, width=70)
    line_count = len(wrapped_lines)
    
    # Calculate required header height based on lines
    header_height = 1.2 + (line_count * 0.3)
    total_height = 10 + header_height
    
    fig = plt.figure(figsize=(12, total_height), facecolor='black')
    fig.patch.set_facecolor('black')

    # Row ratios: Header, Price, Volume, RSI
    gs = fig.add_gridspec(4, 1, height_ratios=[header_height, 7, 1.2, 1.2], hspace=0.2)
    
    ax_header = fig.add_subplot(gs[0])
    ax_price  = fig.add_subplot(gs[1])
    ax_volume = fig.add_subplot(gs[2])
    ax_rsi    = fig.add_subplot(gs[3])
    
    # Clear header background
    ax_header.set_facecolor('black')
    ax_header.patch.set_facecolor('black')
    ax_header.axis('off')
    # Narrow the left/right margins for the whole figure
    fig.subplots_adjust(left=0.05, right=0.95, bottom=0.05)

    # Add info as two vertical sections: Ticker and AI Comment
    # Ticker at the absolute top
    ax_header.text(0, 0.95, symbol.replace('_', '.'), 
                  fontsize=22, verticalalignment='top', color='#e5e7eb', fontweight='bold',
                  fontproperties=font_prop)
    
    # AI Comment (Prefix with AI: and combine into one multi-line block)
    ai_full_text = f"AI: {plan.get('thesis', 'Technical analysis complete.')}"
    # Wrap this combined text
    wrapped_ai_text = textwrap.fill(ai_full_text, width=80)
    
    ax_header.text(0, 0.65, wrapped_ai_text, 
                  fontsize=12, verticalalignment='top', color='#d1d5db', 
                  fontproperties=font_prop)

    # Prepare RSI addplot specifically for its axis
    rsi_plot = [mpf.make_addplot(df["rsi"], ax=ax_rsi, color='#fbbf24', ylabel='RSI', width=1.0)]
    # SMAs and Markers for the Price axis
    price_plots = [
        mpf.make_addplot(df["sma20"], ax=ax_price, color='#a78bfa', width=1.0),
        mpf.make_addplot(df["sma50"], ax=ax_price, color='#fbbf24', width=1.0),
    ]
    
    reversals = [e.name for e in analysis.expressions if e.value is True and "reversal" in e.tags]
    candles = [e.name for e in analysis.expressions if e.value is True and "candle" in e.tags]
    if any("bullish" in s for s in candles + reversals):
        marker_data = [float('nan')] * len(df)
        marker_data[-1] = df["low"].iloc[-1] * 0.97
        price_plots.append(mpf.make_addplot(marker_data, scatter=True, markersize=120, marker='^', color='cyan', ax=ax_price))

    # Actual Plotting using the pre-defined axes
    mpf.plot(
        df,
        type='candle',
        ax=ax_price,
        volume=ax_volume,
        addplot=price_plots + rsi_plot,
        style=s,
        hlines=dict(hlines=hlines_vals, colors=hlines_colors, linestyle=hlines_styles, linewidths=0.4),
        datetime_format='%m/%d',
        xrotation=0,
    )
    
    # 7. Add Annotations in ax_price
    if ai_trigger:
        ax_price.annotate(f"AI TRGR: {ai_trigger}", xy=(0, ai_trigger), xytext=(5, 5), textcoords='offset points', color='#10b981', weight='normal', fontsize=9, fontproperties=font_prop)
    if ai_invalidation:
        ax_price.annotate(f"AI INVL: {ai_invalidation}", xy=(0, ai_invalidation), xytext=(5, -12), textcoords='offset points', color='#ef4444', weight='normal', fontsize=9, fontproperties=font_prop)
    
    # Fix RSI limits and labels
    ax_rsi.set_ylim(0, 100)
    ax_rsi.axhline(70, color='#ef4444', linestyle='--', alpha=0.3, linewidth=0.8)
    ax_rsi.axhline(30, color='#10b981', linestyle='--', alpha=0.3, linewidth=0.8)

    # Final Save
    fig.savefig(str(chart_path), dpi=150, facecolor='black', bbox_inches='tight')
    plt.close(fig)
    
    return chart_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("symbol")
    parser.add_argument("--days", type=int, default=100)
    args = parser.parse_args()
    
    try:
        path = plot_symbol(args.symbol, days=args.days)
        print(f"Chart saved correctly (Agent Perspective): {path}")
    except Exception as e:
        print(f"Error plotting chart: {e}", file=sys.stderr)
        sys.exit(1)
