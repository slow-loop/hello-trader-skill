"""Local trading state for tw-trader.

Wraps market_core.broker with tw-trader's workspace layout. Resolves paths
from TW_TRADER_ROOT env var or falls back to the skill directory.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from market_core import MarketConfig, MarketRuntimeConfig, get_market_profile, get_quote
from market_core.market import get_bars
from market_core.models import Bar, Order, OrderRequest, Quote, TradeRecord, TradingState
from market_core.broker import (
    append_trade,
    cancel_order as _cancel_order,
    default_cash,
    evaluate_orders,
    load_state,
    load_trades,
    place_order as _place_order,
    save_state,
    workspace_paths,
)

from tw_trader.events import append_event
from tw_trader.workspace import sync_watchlist_with_positions

SKILL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[4]
STATE_SUBDIR = "data/account/state"
SWEEP_TIMEFRAME = "5m"
# Entry LIMIT orders auto-cancel after this many days. STOP_LOSS/TAKE_PROFIT
# don't expire — they're tied to the position's lifetime.
LIMIT_EXPIRY_DAYS = 3
# Fallback bar lookback when no pending order has a placed_at to anchor from.
# Normally lookback is computed dynamically from the oldest pending order.
SWEEP_LOOKBACK_FALLBACK_DAYS = 3
# Hard cap on bar lookback — a STOP_LOSS held longer than this won't see
# older bars. Fills via quote still work; only historical bar evaluation is bounded.
SWEEP_LOOKBACK_MAX_DAYS = 30


def _trade_payload(trade: TradeRecord) -> dict:
    return trade.model_dump(mode="json", exclude_none=True)


def _order_payload(order: Order) -> dict:
    return order.model_dump(mode="json", exclude_none=True)


def workspace_root() -> Path:
    """Skill root — holds static config under config/."""
    env = os.getenv("TW_TRADER_ROOT")
    return Path(env).expanduser() if env else SKILL_ROOT


def data_root() -> Path:
    """Runtime data root — holds account/ etc. Defaults to repo root."""
    env = os.getenv("TW_TRADER_DATA_ROOT")
    return Path(env).expanduser() if env else PROJECT_ROOT


def state_dir() -> Path:
    return data_root() / STATE_SUBDIR


def _paths() -> tuple[Path, Path]:
    return workspace_paths(state_dir())


def _load_workspace_yaml() -> dict:
    path = workspace_root() / "config/workspace.yaml"
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


# ─── order placement ────────────────────────────────────────────────────────


def place_order(request: OrderRequest) -> tuple[Order, list[TradeRecord]]:
    """Place an order then immediately sweep — MARKET fills now if possible."""
    state = get_state()
    profile = _profile()
    order = _place_order(state, profile, request)
    append_event("order.placed", _order_payload(order))
    triggered = _sweep_state(state, profile)
    save(state)
    _persist_trades(triggered)
    sync_watchlist_with_positions(set(state.positions.keys()))
    return order, triggered


def cancel_order(order_id: str, reason: str = "") -> Order:
    state = get_state()
    order = _cancel_order(state, order_id, reason)
    save(state)
    append_event("order.cancelled", _order_payload(order))
    return order


def buy(
    symbol: str,
    quantity: float,
    *,
    limit_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
    reason: str = "",
    strategy: str = "",
) -> tuple[Order, list[TradeRecord]]:
    request = OrderRequest(
        symbol=symbol,
        side="BUY",
        type="LIMIT" if limit_price is not None else "MARKET",
        quantity=quantity,
        limit_price=limit_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        reason=reason,
        strategy=strategy,
    )
    return place_order(request)


def sell(
    symbol: str,
    quantity: float,
    *,
    limit_price: float | None = None,
    reason: str = "",
    strategy: str = "",
) -> tuple[Order, list[TradeRecord]]:
    request = OrderRequest(
        symbol=symbol,
        side="SELL",
        type="LIMIT" if limit_price is not None else "MARKET",
        quantity=quantity,
        limit_price=limit_price,
        reason=reason,
        strategy=strategy,
    )
    return place_order(request)


# ─── sweep ──────────────────────────────────────────────────────────────────


def sweep() -> list[TradeRecord]:
    """Fetch market data for symbols with pending orders, then evaluate."""
    state = get_state()
    profile = _profile()
    triggered = _sweep_state(state, profile)
    save(state)
    _persist_trades(triggered)
    sync_watchlist_with_positions(set(state.positions.keys()))
    return triggered


def _sweep_state(state: TradingState, profile) -> list[TradeRecord]:
    pending_symbols = sorted({o.symbol for o in state.orders if o.status == "PENDING"})
    if not pending_symbols:
        return []

    lookback = _compute_lookback_days(state.orders)

    quotes: dict[str, Quote] = {}
    bars_by_symbol: dict[str, list[Bar]] = {}
    for symbol in pending_symbols:
        try:
            quotes[symbol] = get_quote(symbol, profile)
        except Exception:
            continue
        if any(o.symbol == symbol and o.type != "MARKET" for o in state.orders if o.status == "PENDING"):
            try:
                bars = get_bars(symbol, profile, timeframe=SWEEP_TIMEFRAME, lookback_days=lookback)
            except Exception:
                bars = []
            bars_by_symbol[symbol] = _filter_bars_by_pending(state.orders, symbol, bars)

    return evaluate_orders(
        state, profile, quotes, bars_by_symbol,
        expire_limit_after_days=LIMIT_EXPIRY_DAYS,
    )


def _compute_lookback_days(orders: list[Order]) -> int:
    """Lookback = days since oldest pending non-MARKET order, clamped."""
    earliest = None
    for o in orders:
        if o.status != "PENDING" or o.type == "MARKET":
            continue
        if earliest is None or o.placed_at < earliest:
            earliest = o.placed_at
    if earliest is None:
        return SWEEP_LOOKBACK_FALLBACK_DAYS
    age = (datetime.now(timezone.utc) - _parse_iso(earliest)).days + 1
    return max(SWEEP_LOOKBACK_FALLBACK_DAYS, min(age, SWEEP_LOOKBACK_MAX_DAYS))


def _persist_trades(trades: list[TradeRecord]) -> None:
    if not trades:
        return
    _, trades_path = _paths()
    for trade in trades:
        append_trade(trades_path, trade)
        append_event("trade.fill", _trade_payload(trade))


def _filter_bars_by_pending(orders: list[Order], symbol: str, bars: list[Bar]) -> list[Bar]:
    """Drop bars older than the earliest pending non-MARKET order for this symbol.

    Each order strictly should be evaluated against its own placed_at, but bars
    are shared; the engine walks chronologically and takes the first crossing,
    so trimming to the earliest placed_at across all pending orders is safe and
    keeps the data payload small.
    """
    earliest = None
    for o in orders:
        if o.status != "PENDING" or o.symbol != symbol or o.type == "MARKET":
            continue
        if earliest is None or o.placed_at < earliest:
            earliest = o.placed_at
    if earliest is None:
        return bars
    cutoff = _parse_iso(earliest)
    return [b for b in bars if _parse_iso(b.bar_time) >= cutoff]


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _profile():
    config = _market_config()
    return get_market_profile(config.market.profile)


# ─── account view ───────────────────────────────────────────────────────────


def get_account_status() -> dict:
    profile = _profile()
    state = get_state()

    prices: dict[str, float] = {}
    symbols_to_quote = set(state.positions) | {o.symbol for o in state.orders if o.status == "PENDING"}
    for symbol in symbols_to_quote:
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

    pending_orders: list[dict] = []
    committed_buy_cash = 0.0
    for order in state.orders:
        if order.status != "PENDING":
            continue
        ref_price = order.limit_price or order.trigger_price or prices.get(order.symbol)
        dist_pct = None
        current = prices.get(order.symbol)
        if ref_price is not None and current and current > 0:
            dist_pct = round((ref_price - current) / current * 100, 4)
        pending_orders.append(
            {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "type": order.type,
                "quantity": order.quantity,
                "limit_price": order.limit_price,
                "trigger_price": order.trigger_price,
                "ref_distance_pct": dist_pct,
                "placed_at": order.placed_at,
                "reason": order.reason,
            }
        )
        if order.side == "BUY" and ref_price is not None:
            committed_buy_cash += order.quantity * ref_price

    exposure_pct = round(total_market_value / account_value * 100, 4) if account_value > 0 else 0.0
    return {
        "market_profile": profile.id,
        "cash": round(state.cash, 4),
        "committed_in_pending": round(committed_buy_cash, 4),
        "realized_pnl": round(state.realized_pnl, 4),
        "account_value": round(account_value, 4),
        "market_value": round(total_market_value, 4),
        "exposure_pct": exposure_pct,
        "positions": positions,
        "pending_orders": pending_orders,
    }
