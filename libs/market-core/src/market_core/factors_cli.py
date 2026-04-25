"""`factor` CLI: inspect factors, compute signals for a universe.

Commands:
    factor list                       — list all registered factors + metadata
    factor features SYMBOL            — compute feature panel for one symbol (last N bars)
    factor signal --strategy FILE [--universe NAME] [--top N]
                                      — run strategy on universe, print top signals
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import typer

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(levelname)s %(name)s: %(message)s",
)

app = typer.Typer(add_completion=False, no_args_is_help=True, help="factor CLI")


def _echo(obj) -> None:
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


@app.command("list")
def list_factors_cmd(category: str | None = typer.Option(None)) -> None:
    """List all registered factors."""
    from market_core.factors.registry import list_factors

    items = list_factors(category=category)  # type: ignore[arg-type]
    out = [
        {
            "id": m.id,
            "category": m.category,
            "bias_default": m.bias_default,
            "confidence_base": m.confidence_base,
            "description": m.description,
            "requires": m.requires,
            "ic": m.ic,
            "ic_sample_size": m.ic_sample_size,
        }
        for m in items
    ]
    _echo(out)


@app.command()
def features(
    symbol: str,
    start: str = typer.Option("2023-01-01"),
    end: str | None = typer.Option(None),
    tail: int = typer.Option(5, help="print last N rows"),
) -> None:
    """Compute feature panel for one symbol and print the tail."""
    from market_core.data.ohlc_cache import load_ohlc
    from market_core.features import compute_features

    df = load_ohlc(symbol, start=start, end=end)
    if df.empty:
        typer.echo(f"no data for {symbol}", err=True)
        raise typer.Exit(1)
    feat = compute_features(df)
    tail_df = feat.tail(tail)
    _echo({
        "symbol": symbol.upper(),
        "bars": len(feat),
        "last_date": str(feat.index[-1].date()),
        "tail": tail_df.reset_index().to_dict(orient="records"),
    })


@app.command()
def signal(
    strategy: Path = typer.Option(..., exists=True, help="path to strategy yaml"),
    universe: str = typer.Option("megacap_tech", help="sp500|megacap_tech|<comma list>"),
    start: str = typer.Option("2023-01-01"),
    end: str | None = typer.Option(None),
    top: int = typer.Option(20, help="top N by composite score on latest bar"),
) -> None:
    """Evaluate strategy across a universe, print top signals on the latest bar."""
    from market_core.data.ohlc_cache import load_many
    from market_core.features import compute_features
    from market_core.strategy import apply_strategy, load_strategy
    from market_core.universes import resolve_universe

    cfg = load_strategy(strategy)
    if "," in universe:
        symbols = [s.strip().upper() for s in universe.split(",")]
    else:
        symbols = resolve_universe(universe)

    ohlc = load_many(symbols, start=start, end=end)
    if not ohlc:
        typer.echo("no data loaded", err=True)
        raise typer.Exit(1)

    rows = []
    for sym, df in ohlc.items():
        if len(df) < 250:
            continue
        feat = compute_features(df)
        sig = apply_strategy(cfg, feat)
        latest = sig.iloc[-1]
        rows.append({
            "symbol": sym,
            "date": str(feat.index[-1].date()),
            "close": round(float(feat["close"].iloc[-1]), 2),
            "composite_score": round(float(latest["composite_score"]), 3),
            "entry_ok": bool(latest["entry_ok"]),
            "firing_factors": list(latest["firing_factors"]),
            "per_factor": {
                fref.id: round(float(latest.get(fref.id, 0.0)), 3)
                for fref in cfg.factors
            },
        })

    rows.sort(key=lambda r: r["composite_score"], reverse=True)
    _echo({
        "strategy": cfg.name,
        "version": cfg.version,
        "universe_size": len(rows),
        "top": rows[:top],
    })


def main() -> None:
    app()


if __name__ == "__main__":
    main()
