"""Paper-trading broker engine — pure functions over TradingState.

Lifecycle: every intent becomes an Order (PENDING). The fill engine evaluates
pending orders against current quotes (MARKET) or bars since placed_at
(LIMIT/STOP_LOSS/TAKE_PROFIT) and produces TradeRecords. Insufficient cash or
inventory at fill time cancels the order — paper-trading reflects this rather
than reserving cash up front.

No I/O. Callers fetch market data and pass it in.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from market_core.models import (
    Bar,
    Order,
    OrderRequest,
    Position,
    Quote,
    TradeRecord,
    TradingState,
    utc_now_iso,
)
from market_core.policies import MarketProfile


def default_cash(profile: MarketProfile) -> float:
    if profile.currency == "TWD":
        return 1_000_000.0
    return 10_000.0


# ─── placement ──────────────────────────────────────────────────────────────


def place_order(state: TradingState, profile: MarketProfile, request: OrderRequest) -> Order:
    """Validate intent and append a PENDING Order to state. No fill here."""
    _validate_request(state, request)

    order = Order(
        symbol=request.symbol,
        side=request.side,
        type=request.type,
        quantity=request.quantity,
        limit_price=request.limit_price if request.type == "LIMIT" else None,
        attach_stop_loss=request.stop_loss if request.side == "BUY" else None,
        attach_take_profit=request.take_profit if request.side == "BUY" else None,
        reason=request.reason,
        strategy=request.strategy,
        tags=list(request.tags),
    )
    state.orders.append(order)
    state.updated_at = utc_now_iso()
    return order


def cancel_order(state: TradingState, order_id: str, reason: str = "") -> Order:
    order = _find_order(state, order_id)
    if order.status != "PENDING":
        raise ValueError(f"order {order_id} is {order.status}, cannot cancel")
    _mark_cancelled(order, reason or "user cancelled")
    state.updated_at = utc_now_iso()
    return order


def _validate_request(state: TradingState, request: OrderRequest) -> None:
    if request.quantity <= 0:
        raise ValueError("quantity must be > 0")
    if request.type == "LIMIT" and request.limit_price is None:
        raise ValueError("LIMIT orders require limit_price")
    if request.side == "BUY":
        existing = state.positions.get(request.symbol)
        if existing is None and request.stop_loss is None:
            raise ValueError("opening a new position requires stop_loss")
        if existing is None and not request.reason:
            raise ValueError("opening a new position requires reason")
    elif request.side == "SELL":
        pos = state.positions.get(request.symbol)
        held = pos.quantity if pos else 0.0
        if held < request.quantity:
            raise ValueError(f"insufficient quantity: hold {held:g} of {request.symbol}")


# ─── evaluation ─────────────────────────────────────────────────────────────


def evaluate_orders(
    state: TradingState,
    profile: MarketProfile,
    quotes: dict[str, Quote],
    bars_by_symbol: dict[str, list[Bar]] | None = None,
    *,
    expire_limit_after_days: int | None = None,
) -> list[TradeRecord]:
    """Walk pending orders and fill what can fill. Returns TradeRecords for fills.

    quotes: current quote per symbol — used for MARKET orders and limit-up detection.
    bars_by_symbol: bars on/after each order's placed_at, ascending chronologically —
        used for LIMIT/STOP_LOSS/TAKE_PROFIT. Caller decides bar timeframe.
    expire_limit_after_days: if set, cancel LIMIT orders older than N days before
        evaluating fills. STOP_LOSS/TAKE_PROFIT are tied to positions and never expire.
    """
    bars_by_symbol = bars_by_symbol or {}
    trades: list[TradeRecord] = []

    if expire_limit_after_days is not None:
        _expire_limit_orders(state, expire_limit_after_days)

    # Stop-loss before take-profit on same bar → conservative.
    pending = [o for o in state.orders if o.status == "PENDING"]
    pending.sort(key=lambda o: _eval_priority(o.type))

    for order in pending:
        trade = _try_fill(state, profile, order, quotes, bars_by_symbol)
        if trade is not None:
            trades.append(trade)

    if trades:
        state.updated_at = utc_now_iso()
    return trades


def _eval_priority(order_type: str) -> int:
    return {"STOP_LOSS": 0, "TAKE_PROFIT": 1, "MARKET": 2, "LIMIT": 3}.get(order_type, 9)


def _try_fill(
    state: TradingState,
    profile: MarketProfile,
    order: Order,
    quotes: dict[str, Quote],
    bars_by_symbol: dict[str, list[Bar]],
) -> TradeRecord | None:
    fill_price = _resolve_fill_price(order, quotes.get(order.symbol), bars_by_symbol.get(order.symbol, []))
    if fill_price is None:
        return None
    return _execute_fill(state, profile, order, fill_price)


def _resolve_fill_price(order: Order, quote: Quote | None, bars: list[Bar]) -> float | None:
    if order.type == "MARKET":
        if quote is None:
            return None
        if order.side == "BUY" and quote.is_limit_up:
            return None
        if order.side == "SELL" and quote.is_limit_down:
            return None
        return quote.price

    if order.type == "LIMIT":
        limit = order.limit_price
        if limit is None or not bars:
            return None
        for bar in bars:
            if order.side == "BUY" and bar.low <= limit:
                # Gap-down: fill at open if open already through limit.
                return min(limit, bar.open)
            if order.side == "SELL" and bar.high >= limit:
                return max(limit, bar.open)
        return None

    if order.type == "STOP_LOSS":
        trigger = order.trigger_price
        if trigger is None or not bars:
            return None
        for bar in bars:
            if bar.low <= trigger:
                return min(trigger, bar.open)
        return None

    if order.type == "TAKE_PROFIT":
        trigger = order.trigger_price
        if trigger is None or not bars:
            return None
        for bar in bars:
            if bar.high >= trigger:
                return max(trigger, bar.open)
        return None

    return None


def _execute_fill(
    state: TradingState,
    profile: MarketProfile,
    order: Order,
    fill_price: float,
) -> TradeRecord | None:
    if order.side == "BUY":
        return _fill_buy(state, profile, order, fill_price)
    return _fill_sell(state, profile, order, fill_price)


def _fill_buy(state: TradingState, profile: MarketProfile, order: Order, price: float) -> TradeRecord | None:
    notional = order.quantity * price
    fee = round(notional * profile.buy_fee_rate, 4)
    total_cost = notional + fee
    if state.cash < total_cost:
        _mark_cancelled(order, f"insufficient cash: need {total_cost:.4f}, have {state.cash:.4f}")
        return None

    state.cash -= total_cost
    pos = state.positions.get(order.symbol)
    if pos is None:
        pos = Position(quantity=0.0, avg_price=0.0, reason=order.reason)
    old_total = pos.quantity * pos.avg_price
    pos.quantity += order.quantity
    pos.avg_price = round((old_total + notional) / pos.quantity, 8)
    if order.reason:
        pos.reason = order.reason
    state.positions[order.symbol] = pos

    if order.attach_stop_loss is not None:
        state.orders.append(
            Order(
                symbol=order.symbol,
                side="SELL",
                type="STOP_LOSS",
                quantity=order.quantity,
                trigger_price=order.attach_stop_loss,
                reason=f"attached to {order.id}",
            )
        )
    if order.attach_take_profit is not None:
        state.orders.append(
            Order(
                symbol=order.symbol,
                side="SELL",
                type="TAKE_PROFIT",
                quantity=order.quantity,
                trigger_price=order.attach_take_profit,
                reason=f"attached to {order.id}",
            )
        )

    _mark_filled(order, price)
    return TradeRecord(
        action="BUY",
        symbol=order.symbol,
        quantity=order.quantity,
        price=price,
        fee=fee,
        reason=order.reason,
        strategy=order.strategy,
        tags=order.tags,
        order_id=order.id,
    )


def _fill_sell(state: TradingState, profile: MarketProfile, order: Order, price: float) -> TradeRecord | None:
    pos = state.positions.get(order.symbol)
    if pos is None or pos.quantity < order.quantity:
        held = pos.quantity if pos else 0.0
        _mark_cancelled(order, f"insufficient quantity: hold {held:g} of {order.symbol}")
        return None

    notional = order.quantity * price
    fee = round(notional * (profile.sell_fee_rate + profile.sell_tax_rate), 4)
    net_revenue = notional - fee
    cost_basis = order.quantity * pos.avg_price
    pnl = round(net_revenue - cost_basis, 4)

    state.cash += net_revenue
    state.realized_pnl = round(state.realized_pnl + pnl, 4)
    pos.quantity = round(pos.quantity - order.quantity, 8)
    if pos.quantity <= 0:
        state.positions.pop(order.symbol, None)
        _cancel_remaining_exit_orders(state, order.symbol, except_id=order.id)
    else:
        state.positions[order.symbol] = pos

    _mark_filled(order, price)
    return TradeRecord(
        action="SELL",
        symbol=order.symbol,
        quantity=order.quantity,
        price=price,
        fee=fee,
        reason=order.reason,
        strategy=order.strategy,
        tags=order.tags,
        pnl=pnl,
        order_id=order.id,
    )


def _expire_limit_orders(state: TradingState, after_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=after_days)
    for order in state.orders:
        if order.status != "PENDING" or order.type != "LIMIT":
            continue
        placed = datetime.fromisoformat(order.placed_at.replace("Z", "+00:00"))
        if placed < cutoff:
            _mark_cancelled(order, f"expired after {after_days}d")


def _cancel_remaining_exit_orders(state: TradingState, symbol: str, *, except_id: str) -> None:
    for o in state.orders:
        if (
            o.status == "PENDING"
            and o.symbol == symbol
            and o.type in ("STOP_LOSS", "TAKE_PROFIT")
            and o.id != except_id
        ):
            _mark_cancelled(o, "position closed")


# ─── helpers ────────────────────────────────────────────────────────────────


def _find_order(state: TradingState, order_id: str) -> Order:
    for order in state.orders:
        if order.id == order_id:
            return order
    raise ValueError(f"order {order_id} not found")


def _mark_filled(order: Order, price: float) -> None:
    order.status = "FILLED"
    order.fill_price = price
    order.filled_at = utc_now_iso()


def _mark_cancelled(order: Order, reason: str) -> None:
    order.status = "CANCELLED"
    order.cancelled_at = utc_now_iso()
    order.cancelled_reason = reason
