from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import typer
from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=True), override=True)

# Route all logging (including third-party INFO from yfinance/FinMind/etc.) to stderr
# so JSON output on stdout stays pipe-clean.
logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(levelname)s %(name)s: %(message)s",
    force=True,
)

from market_core.market import analyze_symbol, bars_to_dataframe, build_overview, get_bars, get_news, get_quote
from market_core.models import MarketConfig, MarketRuntimeConfig
from market_core.policies import get_market_profile
from market_core.screener import run_screener

app = typer.Typer(add_completion=False, no_args_is_help=True, help="market-core CLI — market data + screener")


def _config(profile: str, benchmark: str | None = None) -> MarketRuntimeConfig:
    return MarketRuntimeConfig(market=MarketConfig(profile=profile, benchmark_symbol=benchmark))


def _echo(obj: Any) -> None:
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


@app.command()
def quote(
    symbol: str,
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
) -> None:
    """Fetch latest quote for a symbol."""
    q = get_quote(symbol, get_market_profile(profile))
    _echo(q.model_dump())


@app.command()
def analysis(
    symbol: str,
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
) -> None:
    """Run technical analysis for a symbol."""
    config = _config(profile)
    snapshot = analyze_symbol(symbol, config, get_market_profile(profile))
    _echo(snapshot.model_dump(exclude={"bars"}))


@app.command()
def screener(
    strategy: str = typer.Option("momentum", "--strategy", "-s"),
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
    limit: int = typer.Option(30, "--limit", "-n"),
    enrich: bool = typer.Option(True, "--enrich/--no-enrich"),
) -> None:
    """Run a quantitative screener."""
    config = _config(profile)
    result = run_screener(
        config,
        get_market_profile(profile),
        strategy=strategy,
        limit=limit,
        enrich=enrich,
    )
    _echo(result.model_dump())


@app.command()
def news(
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
) -> None:
    """Fetch news (requires NewsConfig with sources; returns empty by default)."""
    config = _config(profile)
    items = get_news(config)
    _echo([item.model_dump() for item in items])


@app.command()
def overview(
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
    benchmark: str | None = typer.Option(None, "--benchmark", "-b"),
) -> None:
    """Market session + benchmark overview."""
    config = _config(profile, benchmark)
    ov = build_overview(config, get_market_profile(profile))
    _echo(ov.model_dump())


def _fetch_trimmed_df(symbol: str, bars: int, profile: str) -> "pd.DataFrame":
    """Fetch bars, sort ascending, trim to most recent N, return DataFrame with capitalized cols."""
    import pandas as pd

    profile_obj = get_market_profile(profile)
    lookback = int(bars * 1.5) + 10
    all_bars = get_bars(symbol, profile_obj, lookback_days=lookback)
    sorted_bars = sorted(all_bars, key=lambda b: b.bar_time)
    trimmed = sorted_bars[-bars:]
    df = bars_to_dataframe(trimmed)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df.index.name = "Date"
    df.columns = [c.capitalize() for c in df.columns]
    return df


@app.command()
def candles(
    symbol: str,
    bars: int = typer.Option(60, "--bars", "-n", help="Number of trading bars to return"),
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
) -> None:
    """Output raw OHLC bars as JSON (most recent N trading bars, oldest first)."""
    df = _fetch_trimmed_df(symbol, bars, profile)
    rows = [
        {
            "date": str(idx.date()),
            "open": row["Open"],
            "high": row["High"],
            "low": row["Low"],
            "close": row["Close"],
            "volume": int(row["Volume"]) if row["Volume"] else None,
        }
        for idx, row in df.iterrows()
    ]
    _echo(rows)


@app.command()
def chart(
    symbol: str,
    bars: int = typer.Option(60, "--bars", "-n", help="Number of trading bars to render"),
    profile: str = typer.Option("tw_equity", "--profile", "-p"),
    sma: str = typer.Option("20,60", "--sma", help="Comma-separated SMA periods to overlay"),
    indicators: str = typer.Option(
        "bb,rsi,macd,adx",
        "--indicators", "-i",
        help="Comma-separated overlays: bb, rsi, macd, adx. Use 'none' to disable.",
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output PNG path (default: /tmp/chart_{symbol}.png)"),
) -> None:
    """Generate candlestick chart PNG with volume, SMA, and technical indicator subplots."""
    try:
        import mplfinance as mpf
    except ImportError:
        typer.echo("mplfinance not installed. Run: pip install mplfinance", err=True)
        raise typer.Exit(1)

    import pandas as pd
    import pandas_ta as ta

    # Fetch extra bars for indicator warm-up (MACD needs ~35, ADX ~28; use 60 as safe buffer),
    # compute indicators on the full set, then trim to the requested display window.
    WARMUP = 60
    df_full = _fetch_trimmed_df(symbol, bars + WARMUP, profile)
    sma_periods = tuple(int(p.strip()) for p in sma.split(",") if p.strip())
    active = set() if indicators.lower() == "none" else {i.strip().lower() for i in indicators.split(",") if i.strip()}

    addplots: list = []
    panel_ratios: list = [3, 1]   # price, volume
    next_panel = 2

    # ── Bollinger Bands (main panel) ─────────────────────────────────────
    if "bb" in active:
        bb = ta.bbands(df_full["Close"], length=20)
        if bb is not None and not bb.empty:
            df_full["BB_upper"] = bb[[c for c in bb.columns if c.startswith("BBU")][0]]
            df_full["BB_mid"]   = bb[[c for c in bb.columns if c.startswith("BBM")][0]]
            df_full["BB_lower"] = bb[[c for c in bb.columns if c.startswith("BBL")][0]]

    # ── RSI ──────────────────────────────────────────────────────────────
    if "rsi" in active:
        rsi = ta.rsi(df_full["Close"], length=14)
        if rsi is not None and not rsi.empty:
            df_full["RSI"] = rsi

    # ── MACD ─────────────────────────────────────────────────────────────
    if "macd" in active:
        macd_df = ta.macd(df_full["Close"])
        if macd_df is not None and not macd_df.empty:
            df_full["MACD_line"] = macd_df[[c for c in macd_df.columns if c.startswith("MACD_")][0]]
            df_full["MACD_sig"]  = macd_df[[c for c in macd_df.columns if c.startswith("MACDs")][0]]
            df_full["MACD_hist"] = macd_df[[c for c in macd_df.columns if c.startswith("MACDh")][0]]

    # ── ADX ──────────────────────────────────────────────────────────────
    if "adx" in active:
        adx_df = ta.adx(df_full["High"], df_full["Low"], df_full["Close"], length=14)
        if adx_df is not None and not adx_df.empty:
            df_full["ADX"] = adx_df[[c for c in adx_df.columns if c.startswith("ADX_")][0]]

    # ── Trim to display window (indicators already warmed up) ─────────────
    df = df_full.iloc[-bars:]

    # ── Build addplots from trimmed df ────────────────────────────────────
    if "bb" in active and "BB_upper" in df.columns:
        addplots += [
            mpf.make_addplot(df["BB_upper"], panel=0, color="steelblue", linestyle="--", width=0.8, alpha=0.5),
            mpf.make_addplot(df["BB_mid"],   panel=0, color="steelblue", linestyle=":",  width=0.6, alpha=0.3),
            mpf.make_addplot(df["BB_lower"], panel=0, color="steelblue", linestyle="--", width=0.8, alpha=0.5),
        ]

    if "rsi" in active and "RSI" in df.columns:
        p = next_panel; next_panel += 1; panel_ratios.append(1)
        addplots += [
            mpf.make_addplot(df["RSI"], panel=p, color="purple", width=1.2),
            mpf.make_addplot(pd.Series(70, index=df.index), panel=p, color="red",   linestyle="--", width=0.7, alpha=0.4),
            mpf.make_addplot(pd.Series(30, index=df.index), panel=p, color="green", linestyle="--", width=0.7, alpha=0.4),
        ]

    if "macd" in active and "MACD_hist" in df.columns:
        p = next_panel; next_panel += 1; panel_ratios.append(1.2)
        hist_colors = ["green" if v >= 0 else "red" for v in df["MACD_hist"].fillna(0)]
        addplots += [
            mpf.make_addplot(df["MACD_hist"], panel=p, type="bar", color=hist_colors, alpha=0.6),
            mpf.make_addplot(df["MACD_line"], panel=p, color="royalblue", width=1.0),
            mpf.make_addplot(df["MACD_sig"],  panel=p, color="tomato",    width=1.0),
        ]

    if "adx" in active and "ADX" in df.columns:
        p = next_panel; next_panel += 1; panel_ratios.append(1)
        addplots += [
            mpf.make_addplot(df["ADX"], panel=p, color="darkgreen", width=1.2),
            mpf.make_addplot(pd.Series(25, index=df.index), panel=p, color="gray", linestyle="--", width=0.7, alpha=0.4),
        ]

    out_path = output or Path(f"/tmp/chart_{symbol}.png")
    fig_height = 5 + (next_panel - 2) * 2

    # mplfinance only wants OHLCV columns; drop indicator columns before passing
    ohlcv_cols = [c for c in df.columns if c in ("Open", "High", "Low", "Close", "Volume")]
    plot_kwargs: dict = dict(
        type="candle",
        volume=True,
        mav=sma_periods,
        style="charles",
        title=f"{symbol}  ({len(df)} bars)",
        figsize=(12, fig_height),
        panel_ratios=tuple(panel_ratios),
        returnfig=True,
    )
    if addplots:
        plot_kwargs["addplot"] = addplots

    fig, axes = mpf.plot(df[ohlcv_cols], **plot_kwargs)
    for ax in fig.get_axes():
        ax.yaxis.set_ticks_position("right")
        ax.yaxis.set_label_position("right")
    fig.savefig(str(out_path), dpi=130, bbox_inches="tight")
    _echo({"path": str(out_path), "symbol": symbol, "bars": len(df), "sma": sma_periods, "indicators": sorted(active)})


def main() -> None:
    app()


if __name__ == "__main__":
    main()
