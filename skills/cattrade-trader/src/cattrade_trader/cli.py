"""CLI entry point for cattrade-trader."""

from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from .picker import pick
from .sheet import load_snapshot, parse_csv

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.yaml"


def _load_config(path: Path = CONFIG_PATH) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@app.command()
def scan(
    top_n: int = typer.Option(10, "--top-n", "-n"),
    fixture: Path | None = typer.Option(
        None, "--fixture", help="Parse a local CSV instead of fetching"
    ),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Fetch the latest cattrade snapshot, pick top candidates."""
    cfg = _load_config()
    if fixture:
        snap = parse_csv(fixture.read_text())
    else:
        snap = load_snapshot(cfg["sheet"]["id"], cfg["sheet"]["fetch_timeout_sec"])

    candidates = pick(snap, cfg, top_n=top_n)

    if as_json:
        payload = {
            "meta": {
                "export_time": snap.export_time,
                "snapshot_time": snap.snapshot_time,
                "latency": snap.latency,
            },
            "candidates": [
                {
                    "symbol": c.symbol,
                    "score": c.score,
                    "direction": c.direction,
                    "patterns": c.patterns,
                    "reasons": c.reasons,
                    "oi_usdt": c.oi_usdt,
                }
                for c in candidates
            ],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    console.print(
        f"[dim]export={snap.export_time}  snapshot={snap.snapshot_time}  "
        f"latency={snap.latency}[/dim]"
    )
    table = Table(title=f"Top {len(candidates)} candidates", show_lines=False)
    table.add_column("Sym", style="cyan")
    table.add_column("Dir")
    table.add_column("Score", justify="right")
    table.add_column("Patterns")
    table.add_column("OI", justify="right")
    table.add_column("Reasons", overflow="fold")
    for c in candidates:
        dir_style = "green" if c.direction == "long" else "red"
        table.add_row(
            c.symbol,
            f"[{dir_style}]{c.direction}[/{dir_style}]",
            f"{c.score:.1f}",
            ",".join(c.patterns) or "-",
            f"{c.oi_usdt / 1_000_000:.1f}M" if c.oi_usdt else "-",
            "; ".join(c.reasons),
        )
    console.print(table)


@app.command()
def sections(
    fixture: Path | None = typer.Option(None, "--fixture"),
) -> None:
    """Dump section sizes (debug)."""
    cfg = _load_config()
    snap = (
        parse_csv(fixture.read_text())
        if fixture
        else load_snapshot(cfg["sheet"]["id"], cfg["sheet"]["fetch_timeout_sec"])
    )
    console.print(f"[dim]snapshot={snap.snapshot_time} latency={snap.latency}[/dim]")
    for key, rows in snap.sections.items():
        console.print(f"  {key:<14} {len(rows):>3} rows")


if __name__ == "__main__":
    app()
