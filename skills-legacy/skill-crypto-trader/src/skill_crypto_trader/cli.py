"""CLI interface for skill-crypto-trader.

Usage: uv run python -m skill_crypto_trader <command> [args]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


def _yaml_out(data):
    """Print data as YAML for agent consumption."""
    print(yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False))


# ---------------------------------------------------------------------------
# Strategy commands
# ---------------------------------------------------------------------------

def cmd_strategy_list(args):
    from skill_crypto_trader.core.strategy_registry import load_registry
    entries = load_registry()
    if not entries:
        _yaml_out({"strategies": [], "count": 0})
        return
    summary = []
    for s in entries:
        latest_bt = s.get("backtest_results", [])[-1] if s.get("backtest_results") else {}
        summary.append({
            "name": s["name"],
            "status": s["status"],
            "regime": s.get("regime", ""),
            "timeframe": s.get("timeframe", ""),
            "latest_sharpe": latest_bt.get("sharpe", "N/A"),
            "updated_at": s.get("updated_at", ""),
        })
    _yaml_out({"strategies": summary, "count": len(summary)})


def cmd_strategy_show(args):
    from skill_crypto_trader.core.strategy_registry import get_strategy
    s = get_strategy(args.name)
    if not s:
        _yaml_out({"error": f"Strategy '{args.name}' not found"})
        return
    _yaml_out(s)


def cmd_strategy_validate(args):
    from skill_crypto_trader.core.strategy_validator import validate_by_name
    errors = validate_by_name(args.name)
    if errors:
        _yaml_out({"valid": False, "errors": errors})
    else:
        _yaml_out({"valid": True, "name": args.name})


def cmd_strategy_backtest(args):
    from skill_crypto_trader.core.freqtrade_runner import run_backtest
    from skill_crypto_trader.core.backtest_parser import parse_backtest_result, meets_threshold
    from skill_crypto_trader.core.strategy_registry import record_backtest
    from skill_crypto_trader.journal.helpers import get_freqtrade_userdata

    pairs = args.pairs.split(",") if args.pairs else None

    result = run_backtest(
        strategy_name=args.name,
        timerange=args.timerange or "",
        pairs=pairs,
        config_path=args.config,
    )

    if "error" in result:
        _yaml_out(result)
        return

    # Read explicit export file
    results_dir = get_freqtrade_userdata() / "backtest_results"
    export_file = results_dir / f"latest_{args.name}.json"
    if not export_file.exists():
        _yaml_out({"error": "No backtest result file found"})
        return

    metrics = parse_backtest_result(export_file)
    passed, failures = meets_threshold(metrics)

    # -------------------------------------------------------------
    # Deflated Sharpe Ratio calculation
    # -------------------------------------------------------------
    try:
        from deflated_sharpe import deflated_sharpe_ratio
        obs_sr = metrics.get("sharpe", 0.0)
        num_obs = metrics.get("total_trades", 0)
        if num_obs < 3:
            num_obs = 3
        # We assume 50 trials as a proxy for hyperopt penalties
        dsr, p_val = deflated_sharpe_ratio(obs_sr, num_trials=50, num_obs=num_obs)
        metrics["deflated_sharpe_ratio"] = dsr
        metrics["deflated_sharpe_p_value"] = p_val
    except ImportError:
        metrics["deflated_sharpe_error"] = "deflated-sharpe package not installed"

    bt_record = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "timerange": args.timerange or "full",
        **metrics,
    }
    record_backtest(args.name, bt_record)

    _yaml_out({
        "strategy": args.name,
        "metrics": metrics,
        "passed": passed,
        "failures": failures if failures else "none",
    })


def cmd_strategy_hyperopt(args):
    from skill_crypto_trader.core.freqtrade_runner import run_hyperopt
    result = run_hyperopt(
        strategy_name=args.name,
        epochs=args.epochs,
        loss_fn=args.loss,
        timerange=args.timerange or "",
        config_path=args.config,
    )
    _yaml_out(result)


def cmd_strategy_promote(args):
    from skill_crypto_trader.core.strategy_registry import promote
    try:
        s = promote(args.name)
        _yaml_out({"promoted": args.name, "new_status": s["status"]})
    except ValueError as e:
        _yaml_out({"error": str(e)})


def cmd_strategy_retire(args):
    from skill_crypto_trader.core.strategy_registry import retire
    try:
        s = retire(args.name)
        _yaml_out({"retired": args.name})
    except ValueError as e:
        _yaml_out({"error": str(e)})


def cmd_strategy_decay_check(args):
    from skill_crypto_trader.core.strategy_registry import load_registry
    results = []
    for s in load_registry():
        if s["status"] not in ("active", "deployed"):
            continue
        bts = s.get("backtest_results", [])
        if len(bts) < 2:
            results.append({"name": s["name"], "decay": "insufficient data"})
            continue
        historical = bts[0].get("sharpe", 0)
        recent = bts[-1].get("sharpe", 0)
        decay_pct = round((1 - recent / historical) * 100, 1) if historical > 0 else 0
        results.append({
            "name": s["name"],
            "historical_sharpe": historical,
            "recent_sharpe": recent,
            "decay_pct": decay_pct,
            "alert": decay_pct > 30,
        })
    _yaml_out({"decay_checks": results})


# ---------------------------------------------------------------------------
# Market / Regime / Portfolio Status commands
# ---------------------------------------------------------------------------

def cmd_market_metrics(args):
    import asyncio
    from skill_crypto_trader.market.regime_classifier import RegimeClassifier

    classifier = RegimeClassifier()
    asyncio.run(classifier.generate_report())


def cmd_portfolio_status(args):
    from skill_crypto_trader.core.strategy_registry import load_registry
    from skill_crypto_trader.journal.helpers import get_active_config_path

    active_config_path = get_active_config_path()
    if not active_config_path.exists():
        _yaml_out({"error": "No active_config.yaml found. No strategies are running."})
        return

    active_config = yaml.safe_load(active_config_path.read_text()) or {}
    mode = active_config.get("mode", "unknown")

    registry_map = {s["name"]: s for s in load_registry()}

    active_strats = []
    for s_info in active_config.get("strategies", []):
        s_name = s_info.get("name")
        s_weight = s_info.get("weight", 0)

        reg_s = registry_map.get(s_name, {})
        bts = reg_s.get("backtest_results", [])

        decay_warnings = {}
        status = "HEALTHY"
        if len(bts) >= 2:
            historical = bts[0].get("sharpe", 0)
            recent = bts[-1].get("sharpe", 0)
            if historical > 0:
                decay_warnings["sharpe_decay_pct"] = round((1 - recent / historical) * 100, 1)
                if decay_warnings["sharpe_decay_pct"] > 30:
                    status = "WARNING"
            # In a real implementation we would poll the live drawdown via Freqtrade API
            # For now, we simulate the output structure.

        active_strats.append({
            "name": s_name,
            "current_weight": s_weight,
            "status": status,
            "decay_warnings": decay_warnings if decay_warnings else "insufficient data"
        })

    _yaml_out({
        "running_instance": {
            "mode": mode,
            "cash_reserve_pct": active_config.get("cash_reserve_pct", 0),
            "active_strategies": active_strats
        }
    })


def cmd_portfolio_candidates(args):
    from skill_crypto_trader.core.strategy_scanner import scan_registry_candidates

    statuses = None
    if args.statuses:
        statuses = {item.strip() for item in args.statuses.split(",") if item.strip()}

    result = scan_registry_candidates(
        lookback_bars=args.lookback_bars,
        limit=args.limit,
        statuses=statuses,
    )
    _yaml_out(result)


# ---------------------------------------------------------------------------
# Freqtrade bridge commands
# ---------------------------------------------------------------------------

def cmd_ft_status(args):
    from skill_crypto_trader.core.freqtrade_runner import _run
    result = _run(["show-trades", "--print-json"])
    if result.returncode != 0:
        _yaml_out({"error": result.stderr})
        return
    try:
        trades = json.loads(result.stdout)
        _yaml_out({"open_trades": trades})
    except json.JSONDecodeError:
        _yaml_out({"raw_output": result.stdout})


def cmd_ft_reload(args):
    """Reload Freqtrade configuration.

    Note: Standard Freqtrade CLI does not have a 'reload-config' command.
    Real reloading typically happens via the REST API or by restarting the process.
    For this prototype/research system, we provide this placeholder to simulate the flow.
    """
    from skill_crypto_trader.journal.helpers import get_freqtrade_userdata

    path = get_freqtrade_userdata() / "config_active.json"
    if not path.exists():
        _yaml_out({"error": "No config_active.json found. Run 'config generate' first."})
        return

    # In a full-stack system, we would:
    # 1. Check if Freqtrade is running (e.g. process ID check)
    # 2. If running: call POST /reload_config via REST API
    # 3. If not running: start as new process

    # Simulating success for the research loop workflow
    _yaml_out({
        "success": True,
        "message": "Freqtrade configuration reloaded successfully (Simulation).",
        "detail": f"In a live deployment, this would trigger the /reload_config endpoint on the Freqtrade REST API using the {path.name} file."
    })


def cmd_ft_order_buy(args):
    from skill_crypto_trader.core.freqtrade_api import force_enter
    try:
        res = force_enter(pair=args.pair, side="long", price=args.price, ordertype=args.ordertype)
        _yaml_out({"success": True, "result": res})
    except Exception as e:
        _yaml_out({"error": str(e)})


def cmd_ft_order_close(args):
    from skill_crypto_trader.core.freqtrade_api import force_exit
    try:
        res = force_exit(trade_id=args.trade_id)
        _yaml_out({"success": True, "result": res})
    except Exception as e:
        _yaml_out({"error": str(e)})


def cmd_ft_trades_list(args):
    from skill_crypto_trader.core.freqtrade_api import query_trades
    try:
        res = query_trades()
        _yaml_out({"success": True, "trades": res})
    except Exception as e:
        _yaml_out({"error": str(e)})



# ---------------------------------------------------------------------------
# Config commands
# ---------------------------------------------------------------------------

def cmd_config_generate(args):
    import yaml as _yaml
    from skill_crypto_trader.core.freqtrade_config import generate_active_config
    from skill_crypto_trader.journal.helpers import get_active_config_path
    try:
        raw_weights = args.strategy_weights if hasattr(args, 'strategy_weights') else args.strategy
        # Parse "StrategyA:0.4,StrategyB:0.2" → list of (name, weight) tuples
        strategy_entries = []
        for entry in raw_weights.split(","):
            parts = entry.strip().split(":")
            name = parts[0].strip()
            weight = float(parts[1]) if len(parts) > 1 else 1.0
            strategy_entries.append({"name": name, "weight": weight})

        # Freqtrade only supports a single strategy name; use the highest-weight one
        primary = max(strategy_entries, key=lambda s: s["weight"])
        mode = args.mode or "dryrun"

        path = generate_active_config(
            strategy_name=primary["name"],
            pairs=args.pairs.split(",") if hasattr(args, 'pairs') and args.pairs else ["BTC/USDT", "ETH/USDT"],
            mode=mode,
            max_open_trades=args.max_trades if hasattr(args, 'max_trades') else 3,
        )

        # Write PM state file so portfolio status and ft reload can read it
        pm_state = {
            "mode": mode,
            "cash_reserve_pct": round(100 - sum(s["weight"] * 100 for s in strategy_entries), 1),
            "strategies": [
                {"name": s["name"], "weight": s["weight"]} for s in strategy_entries
            ],
        }
        state_path = get_active_config_path()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(_yaml.dump(pm_state, allow_unicode=True))

        _yaml_out({"config_written": str(path), "pm_state_written": str(state_path)})
    except (ValueError, FileNotFoundError) as e:
        _yaml_out({"error": str(e)})


def cmd_config_show(args):
    from skill_crypto_trader.core.freqtrade_config import show_config
    _yaml_out(show_config())


# ---------------------------------------------------------------------------
# Memory commands
# ---------------------------------------------------------------------------

def cmd_memory_search(args):
    _yaml_out({
        "status": "success",
        "message": f"Searched trade_memory.json for sma_dist_pct={args.sma_dist_pct}, atr_percentile={args.atr_percentile}",
        "stub": True,
        "results": [
            {"context": "相似的熊市高波動 (Bearish, Volatile)", "insight": "突破策略 (Breakout) 勝率較高", "avg_pnl": "+3%"}
        ]
    })


# ---------------------------------------------------------------------------
# Account commands
# ---------------------------------------------------------------------------

def cmd_init(args):
    from skill_crypto_trader.journal.helpers import (
        get_data_dir, get_lessons_path, get_registry_path,
    )

    # Init lessons files
    for agent in ("lab", "pm", "trader"):
        lp = get_lessons_path(agent)
        if not lp.exists():
            lp.write_text(f"# Lessons ({agent})\n\nNo lessons yet.\n")

    # Init registry
    rp = get_registry_path()
    if not rp.exists():
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(yaml.dump({"strategies": []}, allow_unicode=True))

    _yaml_out({"initialized": True, "data_dir": str(get_data_dir())})


def cmd_status(args):
    from skill_crypto_trader.core.strategy_registry import load_registry
    from skill_crypto_trader.journal.helpers import get_active_config_path

    registry = load_registry()
    active_config_path = get_active_config_path()
    active_config = {}
    if active_config_path.exists():
        active_config = yaml.safe_load(active_config_path.read_text()) or {}

    status_counts = {}
    for s in registry:
        st = s["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    _yaml_out({
        "strategy_pool": status_counts,
        "total_strategies": len(registry),
        "active_strategies": active_config.get("strategies", []),
    })


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="crypto-trader",
        description="AI-driven crypto trading with freqtrade",
    )
    sub = parser.add_subparsers(dest="command")

    # -- strategy --
    strat = sub.add_parser("strategy")
    strat_sub = strat.add_subparsers(dest="strat_cmd")

    strat_sub.add_parser("list")

    p = strat_sub.add_parser("show")
    p.add_argument("name")

    p = strat_sub.add_parser("validate")
    p.add_argument("name")

    p = strat_sub.add_parser("backtest")
    p.add_argument("name")
    p.add_argument("--timerange", default="")
    p.add_argument("--pairs", default="")
    p.add_argument("--config", default=None)

    p = strat_sub.add_parser("hyperopt")
    p.add_argument("name")
    p.add_argument("--epochs", type=int, default=500)
    p.add_argument("--loss", default="SharpeHyperOptLossDaily")
    p.add_argument("--timerange", default="")
    p.add_argument("--config", default=None)

    p = strat_sub.add_parser("promote")
    p.add_argument("name")

    p = strat_sub.add_parser("retire")
    p.add_argument("name")

    strat_sub.add_parser("decay-check")

    # -- market --
    market = sub.add_parser("market")
    market_sub = market.add_subparsers(dest="market_cmd")
    market_sub.add_parser("metrics")

    # -- portfolio --
    portfolio = sub.add_parser("portfolio")
    portfolio_sub = portfolio.add_subparsers(dest="portfolio_cmd")
    portfolio_sub.add_parser("status")
    p = portfolio_sub.add_parser("candidates")
    p.add_argument("--lookback-bars", type=int, default=96)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--statuses", default="")

    # -- memory --
    memory = sub.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="memory_cmd")
    p = memory_sub.add_parser("search")
    p.add_argument("--sma-dist-pct", type=float, default=0.0)
    p.add_argument("--atr-percentile", type=float, default=50.0)

    # -- ft --
    ft = sub.add_parser("ft")
    ft_sub = ft.add_subparsers(dest="ft_cmd")
    ft_sub.add_parser("status")
    ft_sub.add_parser("reload")
    
    p = ft_sub.add_parser("buy")
    p.add_argument("pair")
    p.add_argument("--price", type=float, default=None)
    p.add_argument("--ordertype", default="limit")

    p = ft_sub.add_parser("close")
    p.add_argument("trade_id")

    ft_sub.add_parser("trades")
    # -- config --
    cfg = sub.add_parser("config")
    cfg_sub = cfg.add_subparsers(dest="cfg_cmd")

    p = cfg_sub.add_parser("generate")
    p.add_argument("--strategy", default="")
    p.add_argument("--strategy-weights", default="") # For PM new syntax
    p.add_argument("--pairs", default="")
    p.add_argument("--mode", default="dryrun")
    p.add_argument("--max-trades", type=int, default=3)

    cfg_sub.add_parser("show")

    # -- init --
    sub.add_parser("init")

    # -- status (legacy global status) --
    sub.add_parser("status")

    args = parser.parse_args()

    dispatch = {
        "init": cmd_init,
        "status": cmd_status,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    elif args.command == "strategy":
        strat_dispatch = {
            "list": cmd_strategy_list,
            "show": cmd_strategy_show,
            "validate": cmd_strategy_validate,
            "backtest": cmd_strategy_backtest,
            "hyperopt": cmd_strategy_hyperopt,
            "promote": cmd_strategy_promote,
            "retire": cmd_strategy_retire,
            "decay-check": cmd_strategy_decay_check,
        }
        fn = strat_dispatch.get(args.strat_cmd)
        if fn:
            fn(args)
        else:
            strat.print_help()
    elif args.command == "market":
        if args.market_cmd == "metrics":
            cmd_market_metrics(args)
        else:
            market.print_help()
    elif args.command == "portfolio":
        if args.portfolio_cmd == "status":
            cmd_portfolio_status(args)
        elif args.portfolio_cmd == "candidates":
            cmd_portfolio_candidates(args)
        else:
            portfolio.print_help()
    elif args.command == "memory":
        if args.memory_cmd == "search":
            cmd_memory_search(args)
        else:
            memory.print_help()
    elif args.command == "ft":
        ft_dispatch = {
            "status": cmd_ft_status,
            "reload": cmd_ft_reload,
            "buy": cmd_ft_order_buy,
            "close": cmd_ft_order_close,
            "trades": cmd_ft_trades_list,
        }
        fn = ft_dispatch.get(args.ft_cmd)
        if fn:
            fn(args)
        else:
            ft.print_help()
    elif args.command == "config":
        cfg_dispatch = {
            "generate": cmd_config_generate,
            "show": cmd_config_show,
        }
        fn = cfg_dispatch.get(args.cfg_cmd)
        if fn:
            fn(args)
        else:
            cfg.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
