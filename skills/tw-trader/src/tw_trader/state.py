"""Local trading state for tw-trader.

Wraps market_core.paper with tw-trader's workspace layout. Resolves paths
from TW_TRADER_ROOT env var or falls back to the skill directory.
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from market_core import MarketConfig, MarketRuntimeConfig, get_market_profile, get_quote
from market_core.models import OrderRequest, Position, TradeRecord, TradingState
from market_core.paper import (
    append_trade,
    check_exit_orders,
    default_cash,
    execute_buy,
    execute_sell,
    load_state,
    load_trades,
    save_state,
    workspace_paths,
)

SKILL_ROOT = Path(__file__).resolve().parents[2]
STATE_SUBDIR = "data/account/state"


def workspace_root() -> Path:
    env = os.getenv("TW_TRADER_ROOT")
    return Path(env).expanduser() if env else SKILL_ROOT


def state_dir() -> Path:
    return workspace_root() / STATE_SUBDIR


def _paths() -> tuple[Path, Path]:
    return workspace_paths(state_dir())


def _load_workspace_yaml() -> dict:
    path = workspace_root() / "data/config/workspace.yaml"
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _market_config() -> MarketRuntimeConfig:
    raw = _load_workspace_yaml()
    market = raw.get("market") or {}
    return MarketRuntimeConfig(
        market=MarketConfig(
            profile=market.get("profile", "tw_equity"),
            benchmark_symbol=market.get("benchmark_symbol"),
        )
    )


def _initial_cash() -> float:
    raw = _load_workspace_yaml()
    risk = raw.get("risk") or {}
    profile = get_market_profile((raw.get("market") or {}).get("profile", "tw_equity"))
    return float(risk.get("initial_cash") or default_cash(profile))


def get_state() -> TradingState:
    state_path, _ = _paths()
    state = load_state(state_path)
    if state is None:
        state = TradingState(cash=_initial_cash())
        save_state(state_path, state)
    return state


def save(state: TradingState) -> None:
    state_path, _ = _paths()
    save_state(state_path, state)


def list_trades(limit: int | None = None) -> list[TradeRecord]:
    _, trades_path = _paths()
    trades = load_trades(trades_path)
    if limit is None:
        return trades
    return trades[-limit:]


def place_buy(
    symbol: str,
    quantity: float,
    price: float | None,
    *,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    reason: str = "",
    strategy: str = "",
) -> str:
    config = _market_config()
    profile = get_market_profile(config.market.profile)
    state = get_state()
    fill_price = price if price is not None else get_quote(symbol, profile).price
    request = OrderRequest(
        symbol=symbol,
        side="BUY",
        quantity=quantity,
        price=fill_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        strategy=strategy,
    )
    msg, trade = execute_buy(state, profile, symbol, quantity, fill_price, request)
    if trade is not None:
        save(state)
        _, trades_path = _paths()
        append_trade(trades_path, trade)
    return msg


def place_sell(
    symbol: str,
    quantity: float,
    price: float | None,
    *,
    reason: str = "",
    strategy: str = "",
) -> str:
    config = _market_config()
    profile = get_market_profile(config.market.profile)
    state = get_state()
    fill_price = price if price is not None else get_quote(symbol, profile).price
    request = OrderRequest(
        symbol=symbol,
        side="SELL",
        quantity=quantity,
        price=fill_price,
        reason=reason,
        strategy=strategy,
    )
    msg, trade = execute_sell(state, profile, symbol, quantity, fill_price, request)
    if trade is not None:
        save(state)
        _, trades_path = _paths()
        append_trade(trades_path, trade)
    return msg


def sweep_exit_orders() -> list[TradeRecord]:
    config = _market_config()
    profile = get_market_profile(config.market.profile)
    state = get_state()
    prices: dict[str, float] = {}
    for symbol in state.orders:
        try:
            prices[symbol] = get_quote(symbol, profile).price
        except Exception:
            continue
    triggered = check_exit_orders(state, profile, prices)
    if triggered:
        save(state)
        _, trades_path = _paths()
        for trade in triggered:
            append_trade(trades_path, trade)
    return triggered


def get_account_status() -> dict:
    config = _market_config()
    profile = get_market_profile(config.market.profile)
    state = get_state()

    prices: dict[str, float] = {}
    for symbol in state.positions:
        try:
            prices[symbol] = get_quote(symbol, profile).price
        except Exception:
            continue

    positions: list[dict] = []
    total_market_value = 0.0
    for symbol, pos in state.positions.items():
        current = prices.get(symbol)
        market_value = pos.quantity * (current if current is not None else pos.avg_price)
        total_market_value += market_value
        cost = pos.quantity * pos.avg_price
        pnl = (market_value - cost) if current is not None else None
        pnl_pct = ((market_value - cost) / cost * 100) if current is not None and cost > 0 else None
        positions.append(
            {
                "symbol": symbol,
                "quantity": round(pos.quantity, 8),
                "avg_price": round(pos.avg_price, 4),
                "cost": round(cost, 4),
                "reason": pos.reason,
                "current_price": round(current, 4) if current is not None else None,
                "market_value": round(market_value, 4),
                "unrealized_pnl": round(pnl, 4) if pnl is not None else None,
                "unrealized_pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
            }
        )

    account_value = state.cash + total_market_value
    for pos_status in positions:
        if pos_status["market_value"] is not None and account_value > 0:
            pos_status["allocation_pct"] = round(pos_status["market_value"] / account_value * 100, 4)

    orders: list[dict] = []
    for symbol, order in state.orders.items():
        current = prices.get(symbol)
        dist_stop = None
        dist_take = None
        if current and current > 0:
            if order.stop_loss is not None:
                dist_stop = round((order.stop_loss - current) / current * 100, 4)
            if order.take_profit is not None:
                dist_take = round((order.take_profit - current) / current * 100, 4)
        orders.append(
            {
                "symbol": symbol,
                "stop_loss": order.stop_loss,
                "take_profit": order.take_profit,
                "dist_to_stop_pct": dist_stop,
                "dist_to_take_pct": dist_take,
            }
        )

    exposure_pct = round(total_market_value / account_value * 100, 4) if account_value > 0 else 0.0
    return {
        "market_profile": profile.id,
        "cash": round(state.cash, 4),
        "realized_pnl": round(state.realized_pnl, 4),
        "account_value": round(account_value, 4),
        "market_value": round(total_market_value, 4),
        "exposure_pct": exposure_pct,
        "positions": positions,
        "orders": orders,
    }
