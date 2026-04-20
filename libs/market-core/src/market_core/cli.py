from __future__ import annotations

import json
from typing import Any

import typer

from market_core.market import analyze_symbol, build_overview, get_news, get_quote
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
