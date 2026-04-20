from __future__ import annotations

from datetime import date

from backend2 import db, workspace
from backend2.market import build_overview, get_quote
from backend2.models import (
    ExitOrder,
    OrderRequest,
    OrderStatus,
    OrderUpdateRequest,
    PositionStatus,
    TradeRecord,
    TradingState,
    WorkspaceRuntimeConfig,
    WorkspaceStatus,
)
from market_core import MarketProfile, get_market_profile, get_market_session, normalize_symbol
from market_core.paper import (
    check_exit_orders as _check_exit_orders,
    default_cash,
    execute_buy as _execute_buy,
    execute_sell as _execute_sell,
)


def get_runtime_config() -> WorkspaceRuntimeConfig:
    return workspace.load_runtime_config()


def get_market_profile_for_runtime(config: WorkspaceRuntimeConfig | None = None) -> MarketProfile:
    runtime_config = config or get_runtime_config()
    return get_market_profile(runtime_config.market.profile)


async def get_trading_state() -> TradingState:
    config = get_runtime_config()
    profile = get_market_profile_for_runtime(config)
    state = await db.get_trading_state(config.id)
    if state is not None:
        return state
    default_state = TradingState(cash=config.risk.initial_cash or default_cash(profile))
    await db.save_trading_state(config.id, default_state)
    return default_state


async def get_workspace_status() -> WorkspaceStatus:
    config = get_runtime_config()
    profile = get_market_profile_for_runtime(config)
    state = await get_trading_state()
    prices: dict[str, float] = {}
    for symbol in state.positions:
        try:
            prices[symbol] = get_quote(symbol, profile).price
        except Exception:
            continue

    total_market_value = 0.0
    positions: list[PositionStatus] = []
    for symbol, pos in state.positions.items():
        current_price = prices.get(symbol)
        market_value = pos.quantity * (current_price if current_price is not None else pos.avg_price)
        total_market_value += market_value
        cost = pos.quantity * pos.avg_price
        unrealized_pnl = (market_value - cost) if current_price is not None else None
        unrealized_pnl_pct = ((market_value - cost) / cost * 100) if current_price is not None and cost > 0 else None
        positions.append(
            PositionStatus(
                symbol=symbol,
                quantity=round(pos.quantity, 8),
                avg_price=round(pos.avg_price, 4),
                cost=round(cost, 4),
                reason=pos.reason,
                current_price=round(current_price, 4) if current_price is not None else None,
                market_value=round(market_value, 4),
                unrealized_pnl=round(unrealized_pnl, 4) if unrealized_pnl is not None else None,
                unrealized_pnl_pct=round(unrealized_pnl_pct, 4) if unrealized_pnl_pct is not None else None,
            )
        )

    account_value = state.cash + total_market_value
    for position in positions:
        if position.market_value is not None and account_value > 0:
            position.allocation_pct = round(position.market_value / account_value * 100, 4)

    orders: list[OrderStatus] = []
    for symbol, order in state.orders.items():
        current_price = prices.get(symbol)
        dist_to_stop = None
        dist_to_take = None
        if current_price and current_price > 0:
            if order.stop_loss is not None:
                dist_to_stop = round((order.stop_loss - current_price) / current_price * 100, 4)
            if order.take_profit is not None:
                dist_to_take = round((order.take_profit - current_price) / current_price * 100, 4)
        orders.append(
            OrderStatus(
                symbol=symbol,
                stop_loss=order.stop_loss,
                take_profit=order.take_profit,
                dist_to_stop_pct=dist_to_stop,
                dist_to_take_pct=dist_to_take,
            )
        )

    today = date.today().isoformat()
    today_trades = [trade for trade in await db.list_trades(config.id, limit=100) if trade.executed_at.startswith(today)]
    exposure_pct = round(total_market_value / account_value * 100, 4) if account_value > 0 else 0.0
    return WorkspaceStatus(
        workspace_id=config.id,
        name=config.name,
        market_profile=profile.id,
        cash=round(state.cash, 4),
        realized_pnl=round(state.realized_pnl, 4),
        account_value=round(account_value, 4),
        market_value=round(total_market_value, 4),
        exposure_pct=exposure_pct,
        positions=positions,
        orders=orders,
        today_trades=today_trades,
    )


async def place_order(request: OrderRequest) -> str:
    config = get_runtime_config()
    profile = get_market_profile_for_runtime(config)
    state = await get_trading_state()
    session = get_market_session(profile)

    if not session["is_open"]:
        return f"Error: market is not open ({session['reason']})."

    normalized_symbol = normalize_symbol(request.symbol, profile)
    quantity = float(request.quantity)
    if quantity <= 0:
        return "Error: quantity must be greater than 0."
    if not profile.supports_fractional and not quantity.is_integer():
        return "Error: fractional quantity is not supported for this market profile."

    spot = get_quote(normalized_symbol, profile)
    fill_price = request.price or spot.price
    if fill_price <= 0:
        return "Error: invalid price."

    if spot.price > 0:
        deviation = abs(fill_price - spot.price) / spot.price
        if deviation > config.risk.max_price_deviation_pct:
            return (
                f"Error: price deviates {deviation:.1%} from current market price "
                f"(max {config.risk.max_price_deviation_pct:.0%})."
            )

    if request.side == "BUY":
        message, trade = _execute_buy(state, profile, normalized_symbol, quantity, fill_price, request)
    else:
        message, trade = _execute_sell(state, profile, normalized_symbol, quantity, fill_price, request)

    if trade is None:
        return message

    try:
        overview = build_overview(config, profile)
        trade.market_snapshot = overview.model_dump(mode="json")
    except Exception:
        trade.market_snapshot = None

    await db.save_trading_state(config.id, state)
    await db.insert_trade(config.id, trade)
    return message


async def update_orders(request: OrderUpdateRequest) -> str:
    config = get_runtime_config()
    profile = get_market_profile_for_runtime(config)
    state = await get_trading_state()
    symbol = normalize_symbol(request.symbol, profile)

    if symbol not in state.positions:
        return f"Error: no open position for {symbol}."
    if request.stop_loss is None and request.take_profit is None:
        return "Error: provide stop_loss or take_profit."

    order = state.orders.get(symbol, ExitOrder())
    if request.stop_loss is not None:
        order.stop_loss = request.stop_loss
    if request.take_profit is not None:
        order.take_profit = request.take_profit
    state.orders[symbol] = order
    await db.save_trading_state(config.id, state)
    return f"Updated {symbol}: stop_loss={order.stop_loss}, take_profit={order.take_profit}"


async def heartbeat() -> dict[str, object]:
    config = get_runtime_config()
    profile = get_market_profile_for_runtime(config)
    state = await get_trading_state()
    triggered: list[TradeRecord] = []
    session = get_market_session(profile)

    if session["is_open"]:
        prices: dict[str, float] = {}
        for symbol in state.orders:
            try:
                prices[symbol] = get_quote(symbol, profile).price
            except Exception:
                continue
        triggered = _check_exit_orders(state, profile, prices)
        if triggered:
            await db.save_trading_state(config.id, state)
            for trade in triggered:
                await db.insert_trade(config.id, trade)

    overview = build_overview(config, profile)
    await db.insert_market_snapshot(
        workspace_id=config.id,
        market_profile=profile.id,
        phase=overview.session,
        data=overview.model_dump(mode="json"),
        captured_at=overview.timestamp,
    )

    state_now = await db.get_trading_state(config.id)
    if state_now is not None:
        prices_now: dict[str, float] = {}
        for symbol in state_now.positions:
            try:
                prices_now[symbol] = get_quote(symbol, profile).price
            except Exception:
                continue
        mv = sum(pos.quantity * prices_now.get(sym, pos.avg_price) for sym, pos in state_now.positions.items())
        await db.upsert_account_snapshot(
            workspace_id=config.id,
            date=date.today().isoformat(),
            account_value=round(state_now.cash + mv, 4),
            cash=round(state_now.cash, 4),
            market_value=round(mv, 4),
        )

    return {
        "workspace_id": config.id,
        "phase": overview.session,
        "triggered_trades": [trade.model_dump(mode="json") for trade in triggered],
        "snapshot": overview.model_dump(mode="json"),
    }


