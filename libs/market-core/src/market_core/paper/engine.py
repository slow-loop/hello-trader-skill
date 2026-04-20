"""Paper-trading engine — pure functions operating on TradingState.

No I/O. No DB. No external APIs. The caller supplies state + a fill price;
the engine mutates state in place and returns a trade record (or an error
message if the order was rejected).
"""

from __future__ import annotations

from market_core.models import (
    ExitOrder,
    OrderRequest,
    Position,
    TradeRecord,
    TradingState,
)
from market_core.policies import MarketProfile


def default_cash(profile: MarketProfile) -> float:
    if profile.currency == "TWD":
        return 1_000_000.0
    return 10_000.0


def execute_buy(
    state: TradingState,
    profile: MarketProfile,
    symbol: str,
    quantity: float,
    price: float,
    request: OrderRequest,
) -> tuple[str, TradeRecord | None]:
    existing = state.positions.get(symbol)
    if existing is None and request.stop_loss is None and request.reason == "":
        return "Error: opening a new position requires reason and stop_loss.", None

    if state.positions.get(symbol) is None and request.stop_loss is None:
        return "Error: opening a new position requires stop_loss.", None

    notional = quantity * price
    fee = round(notional * profile.buy_fee_rate, 4)
    total_cost = notional + fee
    if state.cash < total_cost:
        return f"Error: insufficient cash. Need {total_cost:.4f}, have {state.cash:.4f}.", None

    state.cash -= total_cost
    pos = state.positions.get(symbol)
    if pos is None:
        pos = Position(quantity=0, avg_price=0.0, reason=request.reason)
    old_total = pos.quantity * pos.avg_price
    pos.quantity += quantity
    pos.avg_price = round((old_total + notional) / pos.quantity, 8)
    if request.reason:
        pos.reason = request.reason
    state.positions[symbol] = pos

    if request.stop_loss is not None or request.take_profit is not None:
        order = state.orders.get(symbol, ExitOrder())
        if request.stop_loss is not None:
            order.stop_loss = request.stop_loss
        if request.take_profit is not None:
            order.take_profit = request.take_profit
        state.orders[symbol] = order

    trade = TradeRecord(
        action="BUY",
        symbol=symbol,
        quantity=quantity,
        price=price,
        fee=fee,
        reason=request.reason,
        strategy=request.strategy,
        tags=request.tags,
    )
    return (
        f"Filled BUY {quantity:g} {symbol} @ {price:.4f}. Fee={fee:.4f}. Cash={state.cash:.4f}.",
        trade,
    )


def execute_sell(
    state: TradingState,
    profile: MarketProfile,
    symbol: str,
    quantity: float,
    price: float,
    request: OrderRequest,
) -> tuple[str, TradeRecord | None]:
    pos = state.positions.get(symbol)
    if pos is None or pos.quantity < quantity:
        held = pos.quantity if pos else 0.0
        return f"Error: insufficient quantity. Hold {held:g} of {symbol}.", None

    notional = quantity * price
    fee = round(notional * (profile.sell_fee_rate + profile.sell_tax_rate), 4)
    net_revenue = notional - fee
    cost_basis = quantity * pos.avg_price
    pnl = round(net_revenue - cost_basis, 4)

    state.cash += net_revenue
    state.realized_pnl += pnl
    pos.quantity = round(pos.quantity - quantity, 8)
    if pos.quantity <= 0:
        state.positions.pop(symbol, None)
        state.orders.pop(symbol, None)
    else:
        state.positions[symbol] = pos

    trade = TradeRecord(
        action="SELL",
        symbol=symbol,
        quantity=quantity,
        price=price,
        fee=fee,
        reason=request.reason,
        strategy=request.strategy,
        tags=request.tags,
        pnl=pnl,
    )
    return (
        f"Filled SELL {quantity:g} {symbol} @ {price:.4f}. Fee={fee:.4f}. PnL={pnl:+.4f}. Cash={state.cash:.4f}.",
        trade,
    )


def check_exit_orders(
    state: TradingState,
    profile: MarketProfile,
    prices: dict[str, float],
) -> list[TradeRecord]:
    triggered: list[TradeRecord] = []
    for symbol, order in list(state.orders.items()):
        current_price = prices.get(symbol)
        position = state.positions.get(symbol)
        if current_price is None or position is None or position.quantity <= 0:
            continue

        if order.stop_loss is not None and current_price <= order.stop_loss:
            request = OrderRequest(
                symbol=symbol,
                side="SELL",
                quantity=position.quantity,
                price=current_price,
                reason=f"Stop loss triggered at {current_price:.4f}",
            )
            _, trade = execute_sell(state, profile, symbol, position.quantity, current_price, request)
            if trade is not None:
                triggered.append(trade)
            continue

        if order.take_profit is not None and current_price >= order.take_profit:
            request = OrderRequest(
                symbol=symbol,
                side="SELL",
                quantity=position.quantity,
                price=current_price,
                reason=f"Take profit triggered at {current_price:.4f}",
            )
            _, trade = execute_sell(state, profile, symbol, position.quantity, current_price, request)
            if trade is not None:
                triggered.append(trade)

    return triggered
