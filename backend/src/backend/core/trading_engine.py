"""
trading_engine.py — Pure trading logic for Taiwan stocks.

All functions are pure: they accept Pydantic models as input and return
updated models. No file I/O. The backend is responsible for persisting state.

Key models (defined in backend.models):
  Ledger        — cash + positions + orders
  Position      — open position for one symbol
  PendingOrder  — stop-loss / take-profit levels
  TradeRecord   — executed trade record
  PortfolioStatus — enriched portfolio view
  EquitySnapshot  — daily equity data point
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

from backend.core.market_data import Quote
from backend.core.market_data import get_quote as get_spot_price
from backend.core.market_calendar import get_twse_market_session
from backend.core.market_data.symbols import normalize_symbol
from backend.models import (
    EquitySnapshot,
    Ledger,
    OrderStatus,
    PendingOrder,
    Position,
    PortfolioStatus,
    PortfolioSummary,
    PositionStatus,
    TodayTrade,
    TradeRecord,
)

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_INITIAL_CASH = 1_000_000.0
TW_LIMIT_PCT = 0.10
PRICE_DEVIATION_PCT = 0.02
BUY_FEE_RATE = 0.001425
SELL_FEE_RATE = 0.001425
SELL_TAX_RATE = 0.003
SELL_TOTAL_RATE = SELL_FEE_RATE + SELL_TAX_RATE


class SpotPrice(Quote):
    symbol: str = "UNKNOWN"
    market: str = "tw"


def default_ledger(initial_cash: float = DEFAULT_INITIAL_CASH) -> Ledger:
    return Ledger(cash=float(initial_cash))


# ── Tick & Limit ─────────────────────────────────────────────────────────────

def _get_tick_size(price: float) -> float:
    if price < 10: return 0.01
    if price < 50: return 0.05
    if price < 100: return 0.1
    if price < 500: return 0.5
    if price < 1000: return 1.0
    return 5.0


def _calc_limit_prices(prev_close: float) -> tuple[float, float]:
    tick = _get_tick_size(prev_close)
    limit_up = (prev_close * (1 + TW_LIMIT_PCT)) // tick * tick
    limit_down = (prev_close * (1 - TW_LIMIT_PCT) + tick - 0.000001) // tick * tick
    return round(limit_up, 2), round(limit_down, 2)


def _is_locked_limit_up(spot: SpotPrice) -> bool:
    if spot.prev_close is None:
        return False
    limit_up, _ = _calc_limit_prices(spot.prev_close)
    return spot.price is not None and spot.price >= limit_up


def _is_locked_limit_down(spot: SpotPrice) -> bool:
    if spot.prev_close is None:
        return False
    _, limit_down = _calc_limit_prices(spot.prev_close)
    return spot.price is not None and spot.price <= limit_down


# ── Validation ───────────────────────────────────────────────────────────────

def validate_order(
    symbol: str,
    side: str,
    price: Optional[float],
    spot: SpotPrice,
) -> Tuple[bool, str, float]:
    """Returns (ok, reason, fill_price)."""
    fill_price = price if price is not None else spot.price

    if fill_price is None or fill_price <= 0:
        return False, "Invalid price.", 0.0

    if spot.prev_close is not None:
        limit_up, limit_down = _calc_limit_prices(spot.prev_close)
        if side == "BUY":
            if fill_price > limit_up:
                return False, f"Price {fill_price} exceeds limit-up {limit_up}.", 0.0
            if _is_locked_limit_up(spot):
                return False, f"{symbol} locked at limit-up ({spot.price}). Cannot fill buy.", 0.0
        elif side == "SELL":
            if fill_price < limit_down:
                return False, f"Price {fill_price} below limit-down {limit_down}.", 0.0
            if _is_locked_limit_down(spot):
                return False, f"{symbol} locked at limit-down ({spot.price}). Cannot fill sell.", 0.0

    if spot.price and spot.price > 0:
        deviation = abs(fill_price - spot.price) / spot.price
        if deviation > PRICE_DEVIATION_PCT:
            return (
                False,
                f"Price {fill_price} deviates {deviation:.1%} from current {spot.price} (max {PRICE_DEVIATION_PCT:.0%}).",
                0.0,
            )

    return True, "", fill_price


# ── Trade Execution (pure) ────────────────────────────────────────────────────

def execute_order(
    ledger: Ledger,
    symbol: str,
    side: str,
    qty: int,
    price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    reason: str = "",
    strategy: str = "",
    tags: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    market_snapshot: Optional[Dict] = None,
) -> Tuple[str, Ledger, Optional[TradeRecord]]:
    """
    Execute a trade against the given ledger.

    Returns: (message, updated_ledger, trade_record | None)
      - trade_record is None on rejection
      - caller is responsible for persisting updated_ledger and trade_record
    """
    if qty <= 0:
        return "Error: Quantity must be greater than 0.", ledger, None

    side = side.upper()
    if side not in ("BUY", "SELL"):
        return "Error: Side must be BUY or SELL.", ledger, None

    symbol = normalize_symbol(symbol)

    try:
        spot = get_spot_price(symbol)
    except Exception as e:
        return f"Error: Cannot fetch price for {symbol}: {e}", ledger, None

    fill_price = price if price is not None else spot.price
    if fill_price is None or fill_price <= 0:
        return "Error: No valid price available.", ledger, None

    session = get_twse_market_session()
    if session == "closed":
        return "Error: Market is closed today. Cannot execute orders.", ledger, None

    ok, reject_reason, validated_price = validate_order(symbol, side, fill_price, spot)
    if not ok:
        return f"Order rejected: {reject_reason}", ledger, None

    ledger = ledger.model_copy(deep=True)

    if side == "BUY":
        msg, trade = _execute_buy(
            ledger, symbol, qty, validated_price,
            stop_loss, take_profit, reason,
            strategy, tags or [], confidence, market_snapshot,
        )
    else:
        msg, trade = _execute_sell(
            ledger, symbol, qty, validated_price,
            reason, strategy, tags or [], market_snapshot,
        )

    return msg, ledger, trade


def _execute_buy(
    ledger: Ledger,
    symbol: str,
    qty: int,
    price: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    reason: str,
    strategy: str,
    tags: List[str],
    confidence: Optional[float],
    market_snapshot: Optional[Dict],
) -> Tuple[str, Optional[TradeRecord]]:
    is_new = symbol not in ledger.positions

    if is_new and not stop_loss:
        return "Error: stop_loss is required when opening a new position.", None
    if is_new and not reason:
        return "Error: reason is required when opening a new position.", None

    cost = qty * price
    fee = round(cost * BUY_FEE_RATE)
    total_cost = cost + fee

    if ledger.cash < total_cost:
        return (
            f"Error: Insufficient funds. Have {ledger.cash:.2f}, need {total_cost:.2f}.",
            None,
        )

    ledger.cash -= total_cost

    pos = ledger.positions.get(symbol, Position(shares=0, avg_price=0.0))
    old_shares = pos.shares
    old_avg = pos.avg_price
    new_shares = old_shares + qty
    pos.shares = new_shares
    pos.avg_price = ((old_shares * old_avg) + total_cost) / new_shares
    if reason:
        pos.reason = reason
    ledger.positions[symbol] = pos

    if stop_loss is not None or take_profit is not None:
        order = ledger.orders.get(symbol, PendingOrder())
        if stop_loss is not None:
            order.stop_loss = stop_loss
        if take_profit is not None:
            order.take_profit = take_profit
        ledger.orders[symbol] = order

    trade = TradeRecord(
        action="BUY",
        symbol=symbol,
        quantity=qty,
        price=price,
        fee=fee,
        total_cost=total_cost,
        reason=reason,
        strategy=strategy,
        tags=tags,
        confidence=confidence,
        market_snapshot=market_snapshot,
        executed_at=datetime.now().isoformat(),
    )

    order = ledger.orders.get(symbol, PendingOrder())
    msg = (
        f"Filled: Bought {qty} shares of {symbol} at {price:.2f}. "
        f"Fee: {fee}, Total cost: {total_cost:.2f}. "
        f"Stop-loss: {order.stop_loss}, Take-profit: {order.take_profit}. "
        f"Remaining cash: {ledger.cash:.2f}."
    )
    return msg, trade


def _execute_sell(
    ledger: Ledger,
    symbol: str,
    qty: int,
    price: float,
    reason: str,
    strategy: str = "",
    tags: Optional[List[str]] = None,
    market_snapshot: Optional[Dict] = None,
) -> Tuple[str, Optional[TradeRecord]]:
    pos = ledger.positions.get(symbol)

    if not pos or pos.shares < qty:
        held = pos.shares if pos else 0
        return f"Error: Insufficient shares. Own {held} shares of {symbol}.", None

    revenue = qty * price
    tax_and_fee = round(revenue * SELL_TOTAL_RATE)
    net_revenue = revenue - tax_and_fee
    cost_basis = qty * pos.avg_price
    trade_pnl = net_revenue - cost_basis

    ledger.cash += net_revenue
    ledger.realized_pnl += trade_pnl

    pnl_r: Optional[float] = None
    order = ledger.orders.get(symbol, PendingOrder())
    if order.stop_loss and pos.avg_price > 0:
        risk_per_share = pos.avg_price - order.stop_loss
        if risk_per_share > 0:
            pnl_r = round(trade_pnl / (qty * risk_per_share), 2)

    trade = TradeRecord(
        action="SELL",
        symbol=symbol,
        quantity=qty,
        price=price,
        fee=0,
        tax_and_fee=tax_and_fee,
        net_revenue=net_revenue,
        pnl=round(trade_pnl, 2),
        pnl_r=pnl_r,
        reason=reason,
        strategy=strategy,
        tags=tags or [],
        market_snapshot=market_snapshot,
        executed_at=datetime.now().isoformat(),
    )

    pos.shares -= qty
    if pos.shares == 0:
        del ledger.positions[symbol]
        ledger.orders.pop(symbol, None)

    msg = (
        f"Filled: Sold {qty} shares of {symbol} at {price:.2f}. "
        f"Net revenue: {net_revenue:.2f}. Realized PnL: {trade_pnl:+,.2f}. "
        f"Remaining cash: {ledger.cash:.2f}."
    )
    return msg, trade


# ── Pending Orders ────────────────────────────────────────────────────────────

def check_pending_orders(
    ledger: Ledger,
    current_prices: Dict[str, float],
) -> Tuple[Ledger, List[TradeRecord]]:
    """
    Check stop-loss / take-profit against current prices.

    Returns: (updated_ledger, list of triggered trade records)
    Caller persists the ledger and trade records.
    """
    ledger = ledger.model_copy(deep=True)
    triggered_trades: List[TradeRecord] = []

    for sym, order in list(ledger.orders.items()):
        curr_price = current_prices.get(sym)
        if curr_price is None:
            continue

        pos = ledger.positions.get(sym)
        if not pos or pos.shares <= 0:
            continue

        if order.stop_loss is not None and curr_price <= order.stop_loss:
            _, trade = _execute_sell(ledger, sym, pos.shares, curr_price, f"SL triggered at {curr_price}")
            if trade:
                trade.trigger = "stop_loss"
                triggered_trades.append(trade)
            continue

        if order.take_profit is not None and curr_price >= order.take_profit:
            _, trade = _execute_sell(ledger, sym, pos.shares, curr_price, f"TP triggered at {curr_price}")
            if trade:
                trade.trigger = "take_profit"
                triggered_trades.append(trade)

    return ledger, triggered_trades


# ── Order Management ──────────────────────────────────────────────────────────

def update_orders(
    ledger: Ledger,
    symbol: str,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> Tuple[str, Ledger]:
    """Returns (message, updated_ledger)."""
    symbol = normalize_symbol(symbol)
    ledger = ledger.model_copy(deep=True)

    if symbol not in ledger.positions:
        return f"Error: No open position for {symbol}.", ledger
    if stop_loss is None and take_profit is None:
        return "Error: Provide at least stop_loss or take_profit.", ledger

    order = ledger.orders.get(symbol, PendingOrder())
    if stop_loss is not None:
        order.stop_loss = stop_loss
    if take_profit is not None:
        order.take_profit = take_profit
    ledger.orders[symbol] = order

    return (
        f"Updated {symbol}: stop_loss={order.stop_loss}, take_profit={order.take_profit}",
        ledger,
    )


# ── Portfolio Status ──────────────────────────────────────────────────────────

def build_status(
    ledger: Ledger,
    trade_history: List[TradeRecord],
    current_prices: Optional[Dict[str, float]] = None,
) -> PortfolioStatus:
    """Pure portfolio status builder."""
    prices = current_prices or {}

    total_market_value = 0.0
    for sym, pos in ledger.positions.items():
        if sym in prices:
            total_market_value += pos.shares * prices[sym]
        else:
            total_market_value += pos.shares * pos.avg_price

    account_value = ledger.cash + total_market_value

    positions: List[PositionStatus] = []
    for sym, pos in ledger.positions.items():
        shares = pos.shares
        avg_price = pos.avg_price
        cost = shares * avg_price
        ps = PositionStatus(
            symbol=sym,
            shares=shares,
            avg_price=round(avg_price, 2),
            cost=round(cost, 0),
            reason=pos.reason,
        )
        if sym in prices:
            curr = prices[sym]
            mkt_val = shares * curr
            pnl = mkt_val - cost
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
            ps.current_price = curr
            ps.market_value = round(mkt_val, 0)
            ps.unrealized_pnl = round(pnl, 0)
            ps.unrealized_pnl_pct = round(pnl_pct, 1)
            ps.allocation_pct = round(mkt_val / account_value * 100, 1) if account_value > 0 else 0
        positions.append(ps)

    orders: List[OrderStatus] = []
    for sym, order in ledger.orders.items():
        curr = prices.get(sym)
        os = OrderStatus(
            symbol=sym,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )
        if curr and curr > 0:
            if order.stop_loss is not None:
                os.dist_to_stop_pct = round((order.stop_loss - curr) / curr * 100, 1)
            if order.take_profit is not None:
                os.dist_to_take_pct = round((order.take_profit - curr) / curr * 100, 1)
        orders.append(os)

    today_str = date.today().isoformat()
    today_trades_records = [t for t in trade_history if t.executed_at.startswith(today_str)]
    today_realized = sum(t.pnl or 0 for t in today_trades_records)
    today_realized_pct = (today_realized / account_value * 100) if account_value > 0 else 0

    total_unrealized = sum(p.unrealized_pnl or 0 for p in positions)
    exposure_pct = (total_market_value / account_value * 100) if account_value > 0 else 0

    summary = PortfolioSummary(
        account_value=round(account_value, 0),
        market_value=round(total_market_value, 0),
        unrealized_pnl=round(total_unrealized, 0),
        realized_pnl=round(ledger.realized_pnl, 0),
        exposure_pct=round(exposure_pct, 0),
        cash_pct=round(100 - exposure_pct, 0),
        today_realized_pnl=round(today_realized, 0),
        today_realized_pnl_pct=round(today_realized_pct, 2),
    )

    alerts: List[str] = []
    for p in positions:
        if (p.allocation_pct or 0) > 30:
            alerts.append(f"{p.symbol} allocation {p.allocation_pct}% exceeds 30% limit")
    for o in orders:
        dist = o.dist_to_stop_pct
        if dist is not None and dist > -3:
            alerts.append(f"{o.symbol} within {abs(dist)}% of stop-loss {o.stop_loss}")
    if today_realized_pct < -3:
        alerts.append(f"Daily loss {today_realized_pct:.1f}% exceeds -3% limit — no new buys")

    today_trades = [
        TodayTrade(
            action=t.action,
            symbol=t.symbol,
            quantity=t.quantity,
            price=t.price,
            pnl=t.pnl,
        )
        for t in today_trades_records
    ]

    return PortfolioStatus(
        cash=round(ledger.cash, 0),
        positions=positions,
        orders=orders,
        summary=summary,
        alerts=alerts,
        today_trades=today_trades,
    )


# ── Equity Snapshot ───────────────────────────────────────────────────────────

def build_equity_snapshot(
    ledger: Ledger,
    current_prices: Optional[Dict[str, float]] = None,
    snapshot_date: Optional[str] = None,
) -> EquitySnapshot:
    """Build a daily equity snapshot. Caller persists to DB."""
    prices = current_prices or {}
    total_market_value = sum(
        pos.shares * prices.get(sym, pos.avg_price)
        for sym, pos in ledger.positions.items()
    )
    account_value = ledger.cash + total_market_value
    unrealized = account_value - ledger.cash - sum(
        pos.shares * pos.avg_price for pos in ledger.positions.values()
    )
    exposure_pct = (total_market_value / account_value * 100) if account_value > 0 else 0

    return EquitySnapshot(
        date=snapshot_date or date.today().isoformat(),
        account_value=round(account_value, 0),
        cash=round(ledger.cash, 0),
        market_value=round(total_market_value, 0),
        realized_pnl=round(ledger.realized_pnl, 0),
        unrealized_pnl=round(unrealized, 0),
        exposure_pct=round(exposure_pct, 0),
        positions_count=len(ledger.positions),
    )
