"""Freqtrade configuration management: merge layers, validate against risk rules."""

from __future__ import annotations

import json
from pathlib import Path

import os
import yaml

from skill_crypto_trader.journal.helpers import (
    get_data_dir,
    get_freqtrade_userdata,
    get_risk_rules_path,
)


def load_base_config() -> dict:
    path = get_data_dir() / "config" / "freqtrade_base.json"
    if not path.exists():
        raise FileNotFoundError(f"Base config not found: {path}")
    return json.loads(path.read_text())


def load_overlay(mode: str) -> dict:
    path = get_data_dir() / "config" / f"freqtrade_{mode}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Deep merge overlay into base."""
    result = base.copy()
    for key, value in overlay.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_risk_rules() -> dict:
    path = get_risk_rules_path()
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text()) or {}


def validate_against_rules(config: dict, rules: dict) -> list[str]:
    """Validate config does not violate risk rules. Returns list of violations."""
    violations = []

    max_trades = rules.get("max_open_trades", 10)
    if config.get("max_open_trades", 0) > max_trades:
        violations.append(
            f"max_open_trades {config.get('max_open_trades')} > limit {max_trades}"
        )

    # Check leverage
    max_leverage = rules.get("max_leverage", 1)
    trading_mode = config.get("trading_mode", "spot")
    if trading_mode == "futures":
        margin_mode = config.get("margin_mode", "isolated")
        # We'll just warn if futures is enabled with high leverage
        if max_leverage <= 1:
            violations.append(
                f"Futures trading not allowed with max_leverage={max_leverage}"
            )

    return violations


def generate_active_config(
    strategy_name: str,
    pairs: list[str],
    mode: str = "dryrun",
    max_open_trades: int = 3,
    stake_amount: str = "unlimited",
) -> Path:
    """Generate a complete freqtrade config from base + overlay + dynamic values."""
    base = load_base_config()
    overlay = load_overlay(mode)
    config = _deep_merge(base, overlay)

    # Dynamic injection
    config["strategy"] = strategy_name
    config["exchange"]["pair_whitelist"] = pairs
    config["max_open_trades"] = max_open_trades
    config["stake_amount"] = stake_amount

    # Inject Bybit API keys and Sandbox (Testnet) mode
    config["exchange"]["key"] = os.getenv("BYBIT_API_KEY", "")
    config["exchange"]["secret"] = os.getenv("BYBIT_API_SECRET", "")

    testnet = os.getenv("BYBIT_TESTNET", "false").lower() == "true"
    if testnet:
        config["exchange"]["ccxt_config"] = config["exchange"].get("ccxt_config", {})
        config["exchange"]["ccxt_config"]["sandbox"] = True

    # Validate against risk rules
    rules = load_risk_rules()
    violations = validate_against_rules(config, rules)
    if violations:
        raise ValueError(f"Risk rule violations: {violations}")

    # Write active config
    out_path = get_freqtrade_userdata() / "config_active.json"
    out_path.write_text(json.dumps(config, indent=2))
    return out_path


def show_config() -> dict:
    """Show the current active config."""
    path = get_freqtrade_userdata() / "config_active.json"
    if not path.exists():
        return {"error": "No active config. Run 'config generate' first."}
    return json.loads(path.read_text())
