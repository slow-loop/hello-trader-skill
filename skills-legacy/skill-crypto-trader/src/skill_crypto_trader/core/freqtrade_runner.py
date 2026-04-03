"""Subprocess wrapper for freqtrade CLI commands."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from skill_crypto_trader.journal.helpers import get_freqtrade_userdata

USERDATA = str(get_freqtrade_userdata())


def _find_freqtrade() -> str:
    """Find freqtrade binary — prefer the one in the same venv as this process."""
    venv_bin = Path(sys.executable).parent / "freqtrade"
    if venv_bin.exists():
        return str(venv_bin)
    found = shutil.which("freqtrade")
    if found:
        return found
    raise FileNotFoundError(
        "freqtrade not found. Install with: uv add freqtrade"
    )


def _run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a freqtrade command and return the result."""
    ft = _find_freqtrade()
    cmd = [ft, *args, "--userdir", USERDATA]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def download_data(
    pairs: list[str],
    timerange: str = "",
    timeframe: str = "1h",
    exchange: str = "bybit",
) -> str:
    """Download OHLCV data for backtesting."""
    args = [
        "download-data",
        "--exchange", exchange,
        "--pairs", *pairs,
        "--timeframes", timeframe,
    ]
    if timerange:
        args.extend(["--timerange", timerange])
    result = _run(args, timeout=300)
    return result.stdout + result.stderr


def run_backtest(
    strategy_name: str,
    timerange: str = "",
    pairs: list[str] | None = None,
    config_path: str | None = None,
) -> dict:
    """Run backtest and return parsed results."""
    args = ["backtesting", "-s", strategy_name]
    if timerange:
        args.extend(["--timerange", timerange])
    if pairs:
        args.extend(["--pairs", *pairs])
    if config_path:
        args.extend(["-c", config_path])
    args.append("--export=trades")
    
    export_file = get_freqtrade_userdata() / "backtest_results" / f"latest_{strategy_name}.json"
    args.extend(["--export-filename", str(export_file)])

    result = _run(args, timeout=600)

    if result.returncode != 0:
        return {"error": result.stderr, "stdout": result.stdout}

    if export_file.exists():
        return json.loads(export_file.read_text())

    # Freqtrade 2026.2+ might zip results automatically. 
    # Check for latest zip if explicit filename failed.
    results_dir = get_freqtrade_userdata() / "backtest_results"
    zips = sorted(results_dir.glob("backtest-result-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if zips:
        latest_zip = zips[0]
        import zipfile
        with zipfile.ZipFile(latest_zip, 'r') as zip_ref:
            # Files inside zip are typically named like the zip file but with .json
            # e.g. backtest-result-2026-03-29_14-47-22.json
            inner_name = latest_zip.stem + ".json"
            if inner_name in zip_ref.namelist():
                content = zip_ref.read(inner_name)
                # Save it to the expected path for cli.py to see it too
                export_file.write_bytes(content)
                return json.loads(content)

    return {"error": "No backtest result file found", "stdout": result.stdout}



def run_hyperopt(
    strategy_name: str,
    epochs: int = 500,
    loss_fn: str = "SharpeHyperOptLossDaily",
    timerange: str = "",
    config_path: str | None = None,
) -> dict:
    """Run hyperopt optimization."""
    args = [
        "hyperopt",
        "-s", strategy_name,
        "--epochs", str(epochs),
        "--hyperopt-loss", loss_fn,
    ]
    if timerange:
        args.extend(["--timerange", timerange])
    if config_path:
        args.extend(["-c", config_path])

    result = _run(args, timeout=1800)

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run_trade(
    config_path: str,
    strategy_name: str,
    dry_run: bool = True,
) -> subprocess.Popen:
    """Start freqtrade in trade mode (background process)."""
    ft = _find_freqtrade()
    args = [
        ft, "trade",
        "-s", strategy_name,
        "-c", config_path,
        "--userdir", USERDATA,
    ]
    if dry_run:
        args.append("--dry-run")

    return subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def stop_trade(process: subprocess.Popen) -> None:
    """Gracefully stop a running freqtrade process."""
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
