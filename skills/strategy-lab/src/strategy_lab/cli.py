"""strategy-lab CLI.

Commands:
    lab factor-ic FACTOR_ID [--universe sp500] [--start ... --end ...]
    lab strategy-bt EXPERIMENT_DIR_OR_YAML
    lab promote EXPERIMENT_DIR --to us-trader [--name NAME --version V]
    lab list-experiments
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import typer
import yaml

logging.basicConfig(
    level=logging.WARNING,
    stream=sys.stderr,
    format="%(levelname)s %(name)s: %(message)s",
)

app = typer.Typer(add_completion=False, no_args_is_help=True, help="strategy-lab CLI")

REPO_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTS_DIR = Path(__file__).resolve().parents[2] / "data" / "experiments"
TRADER_STRATEGIES_DIR = REPO_ROOT / "skills" / "us-trader" / "data" / "strategies"


def _echo(obj) -> None:
    typer.echo(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


@app.command("factor-ic")
def factor_ic_cmd(
    factor_id: str,
    universe: str = typer.Option("megacap_tech"),
    start: str = typer.Option("2020-01-01"),
    end: str = typer.Option("2024-12-31"),
    periods: str = typer.Option("1,5,20", help="comma-separated horizons"),
) -> None:
    """Compute single-factor IC on a universe for the given window."""
    from market_core.backtest.factor_ic import run_factor_ic
    from market_core.backtest.report import write_factor_ic_report
    from market_core.data.ohlc_cache import load_many
    from market_core.factors.registry import FACTOR_REGISTRY, evaluate_all
    from market_core.features import compute_features
    from market_core.universes import resolve_universe

    if factor_id not in FACTOR_REGISTRY:
        raise typer.BadParameter(f"unknown factor: {factor_id}")

    symbols = resolve_universe(universe) if "," not in universe else [
        s.strip() for s in universe.split(",")
    ]
    typer.echo(f"loading {len(symbols)} symbols...", err=True)
    ohlc = load_many(symbols, start=start, end=end)
    if not ohlc:
        typer.echo("no data", err=True)
        raise typer.Exit(1)

    # Build factor panel + price panel aligned on date × symbol.
    factor_series_parts = []
    price_parts = {}
    for sym, df in ohlc.items():
        if len(df) < 250:
            continue
        feat = compute_features(df)
        scores = evaluate_all(feat, factor_ids=[factor_id])[factor_id]
        scores.name = factor_id
        mi = pd.MultiIndex.from_product([feat.index, [sym]], names=["date", "symbol"])
        scores.index = mi
        factor_series_parts.append(scores)
        price_parts[sym] = feat["close"]

    factor_values = pd.concat(factor_series_parts)
    prices = pd.DataFrame(price_parts).sort_index()

    period_tuple = tuple(int(p) for p in periods.split(","))
    result = run_factor_ic(factor_id, factor_values, prices, periods=period_tuple)

    out_dir = EXPERIMENTS_DIR / f"factor_ic_{datetime.utcnow():%Y-%m-%d}_{factor_id}"
    report_path = write_factor_ic_report(result, out_dir, universe_name=universe)
    summary = {
        "factor_id": result.factor_id,
        "ic_by_period": result.ic_by_period,
        "ic_std_by_period": result.ic_std_by_period,
        "sample_size": result.ic_sample_size,
        "report": str(report_path),
        "git_hash": _git_hash(),
    }
    (out_dir / "result.json").write_text(json.dumps(summary, indent=2))
    _echo(summary)


@app.command("strategy-bt")
def strategy_bt_cmd(
    target: Path = typer.Argument(..., help="experiment dir containing config.yaml, OR yaml path"),
    universe: str = typer.Option("megacap_tech"),
    start: str = typer.Option("2020-01-01"),
    end: str = typer.Option("2024-12-31"),
) -> None:
    """Backtest a strategy config."""
    from market_core.backtest.report import write_strategy_bt_report
    from market_core.backtest.strategy_bt import run_strategy_backtest
    from market_core.data.ohlc_cache import load_many
    from market_core.features import compute_features
    from market_core.strategy import load_strategy
    from market_core.universes import resolve_universe

    if target.is_dir():
        cfg_path = target / "config.yaml"
        exp_dir = target.resolve()
    else:
        cfg_path = target
        exp_dir = target.resolve().parent

    # Guard: refuse to write results into the production strategies dir.
    try:
        exp_dir.relative_to(TRADER_STRATEGIES_DIR.resolve())
        raise typer.BadParameter(
            f"target resolves inside the production strategies dir ({TRADER_STRATEGIES_DIR}).\n"
            "Run strategy-bt on an experiment dir under data/experiments/, not on a promoted yaml."
        )
    except ValueError:
        pass  # not inside TRADER_STRATEGIES_DIR — safe to proceed

    cfg = load_strategy(cfg_path)

    symbols = resolve_universe(universe) if "," not in universe else [
        s.strip() for s in universe.split(",")
    ]
    typer.echo(f"loading {len(symbols)} symbols...", err=True)
    ohlc = load_many(symbols, start=start, end=end)

    features_by_symbol: dict[str, pd.DataFrame] = {}
    for sym, df in ohlc.items():
        if len(df) < 250:
            continue
        features_by_symbol[sym] = compute_features(df)

    result = run_strategy_backtest(cfg, features_by_symbol)
    report_path = write_strategy_bt_report(result, exp_dir, strategy_config_path=str(cfg_path))

    summary = {
        "strategy": cfg.name,
        "version": cfg.version,
        "period": result.period,
        "universe": universe,
        "universe_size": result.universe_size,
        "sharpe": result.sharpe,
        "total_return": result.total_return,
        "max_drawdown": result.max_drawdown,
        "calmar": result.calmar,
        "turnover": result.turnover,
        "num_trades": result.num_trades,
        "report": str(report_path),
        "git_hash": _git_hash(),
    }
    (exp_dir / "result.json").write_text(json.dumps(summary, indent=2))
    _echo(summary)


@app.command()
def promote(
    experiment_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    name: str = typer.Option(..., help="full artifact name, e.g. mom_2f_2021-2024_r1"),
    stage: str = typer.Option("research", help="research | paper | live"),
    approved_by: str = typer.Option("human", help="who approved"),
) -> None:
    """Copy experiment config to us-trader/data/strategies/<name>.yaml with metadata.

    Name convention: <family>_<Nf>_<train-window>_<stage><iter>
    Example: mom_2f_2021-2024_r1  (momentum, 2 factors, r=research iter 1)
             mom_2f_2021-2024_p1  (same, promoted to paper trade)
    """
    experiment_dir = experiment_dir.resolve()
    cfg_src = experiment_dir / "config.yaml"
    result_src = experiment_dir / "result.json"
    if not cfg_src.exists():
        raise typer.BadParameter(f"no config.yaml in {experiment_dir}")

    TRADER_STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
    dst = TRADER_STRATEGIES_DIR / f"{name}.yaml"
    if dst.exists():
        raise typer.BadParameter(f"already exists: {dst}")

    cfg = yaml.safe_load(cfg_src.read_text())
    cfg["name"] = name
    cfg["stage"] = stage
    cfg["promoted_at"] = datetime.utcnow().strftime("%Y-%m-%d")
    cfg["promoted_from"] = str(experiment_dir.relative_to(REPO_ROOT))
    cfg["approved_by"] = approved_by

    if result_src.exists():
        result = json.loads(result_src.read_text())
        cfg.setdefault("backtest_summary", {})
        for k in ("period", "universe", "sharpe", "max_drawdown", "turnover", "num_trades"):
            if k in result:
                target_key = "max_dd" if k == "max_drawdown" else k
                cfg["backtest_summary"][target_key] = result[k]

    dst.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))

    manifest = TRADER_STRATEGIES_DIR / "ACTIVE.yaml"
    manifest.write_text(
        yaml.safe_dump(
            {"strategy": name, "stage": stage, "file": dst.name}, sort_keys=False
        )
    )
    _echo({"promoted_to": str(dst), "active": str(manifest)})


@app.command("list-experiments")
def list_experiments() -> None:
    """List experiments on disk."""
    if not EXPERIMENTS_DIR.exists():
        _echo([])
        return
    rows = []
    for p in sorted(EXPERIMENTS_DIR.iterdir()):
        if not p.is_dir():
            continue
        result = p / "result.json"
        rows.append({
            "name": p.name,
            "has_result": result.exists(),
            "result": json.loads(result.read_text()) if result.exists() else None,
        })
    _echo(rows)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
