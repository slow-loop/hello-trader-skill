"""Markdown report writer for backtest results (for agent consumption)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from market_core.backtest.factor_ic import FactorICResult
from market_core.backtest.strategy_bt import StrategyBTResult


def write_factor_ic_report(
    result: FactorICResult,
    out_dir: Path,
    *,
    universe_name: str = "",
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"factor_ic_{result.factor_id}.md"
    lines = [
        f"# Factor IC Report: {result.factor_id}",
        "",
        f"- universe: {universe_name}",
        f"- sample_size: {result.ic_sample_size}",
        f"- generated: {datetime.utcnow().isoformat()}Z",
        "",
        "## IC by horizon",
        "",
        "| period (days) | IC | IC std | t-stat |",
        "|---|---|---|---|",
    ]
    for p, ic in result.ic_by_period.items():
        std = result.ic_std_by_period.get(p, 0.0)
        t = (ic / std * (result.ic_sample_size ** 0.5)) if std else 0.0
        lines.append(f"| {p} | {ic:+.4f} | {std:.4f} | {t:+.2f} |")
    lines.append("")

    lines.append("## Quantile mean returns (bps per period)")
    for p, quants in result.quantile_returns.items():
        lines.append(f"\n### {p}-day forward")
        lines.append("| quantile | mean return |")
        lines.append("|---|---|")
        for q, ret in sorted(quants.items()):
            lines.append(f"| Q{q} | {ret * 10000:+.1f} bps |")
    lines.append("")
    path.write_text("\n".join(lines))
    return path


def write_strategy_bt_report(
    result: StrategyBTResult,
    out_dir: Path,
    *,
    strategy_config_path: str | None = None,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"strategy_bt_{result.strategy_name}.md"
    lines = [
        f"# Strategy Backtest: {result.strategy_name}",
        "",
        f"- period: {result.period}",
        f"- universe_size: {result.universe_size}",
        f"- config: {strategy_config_path or '(not supplied)'}",
        f"- generated: {datetime.utcnow().isoformat()}Z",
        "",
        "## Metrics",
        "",
        f"- Sharpe: **{result.sharpe:.2f}**",
        f"- Total return: {result.total_return * 100:+.2f}%",
        f"- Max drawdown: {result.max_drawdown * 100:+.2f}%",
        f"- Calmar: {result.calmar:.2f}",
        f"- Turnover (daily proxy): {result.turnover:.3f}",
        f"- Trades: {result.num_trades}",
        "",
        "## Equity curve (last 5 points)",
        "",
    ]
    lines.append("| date | equity |")
    lines.append("|---|---|")
    for dt, val in result.equity_curve.tail(5).items():
        lines.append(f"| {dt.date() if hasattr(dt, 'date') else dt} | {val:,.2f} |")
    lines.append("")
    path.write_text("\n".join(lines))
    return path
