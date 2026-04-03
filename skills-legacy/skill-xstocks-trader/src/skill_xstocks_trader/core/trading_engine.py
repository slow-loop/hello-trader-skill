"""
trading_engine.py — Paper trading engine for xStocks (Hyperliquid).

Adapted from tw-trader. Differences:
  - No tick size / board lot logic (fractional crypto units)
  - No limit up/down validation (24/7 crypto market)
  - Fee model: Hyperliquid maker/taker fees
  - Uses CCXT for live price validation
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from skill_xstocks_trader.core.account_paths import EQUITY_FILE, LEDGER_FILE, ensure_account_dirs

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_INITIAL_CASH = 10_000.0

# Hyperliquid fee structure (approximate)
TAKER_FEE_RATE = 0.0005   # 0.05%
MAKER_FEE_RATE = 0.0002   # 0.02%
DEFAULT_FEE_RATE = TAKER_FEE_RATE  # assume taker for paper trading


# ── Data Access ──────────────────────────────────────────────────────────────

def _default_ledger() -> Dict[str, Any]:
    return {
        "cash": DEFAULT_INITIAL_CASH,
        "positions": {},
        "trade_history": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_ledger() -> Dict[str, Any]:
    if not LEDGER_FILE.exists():
        return _default_ledger()
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Migration: ensure required keys
    data.setdefault("cash", DEFAULT_INITIAL_CASH)
    data.setdefault("positions", {})
    data.setdefault("trade_history", [])
    return data


def _save_ledger(data: Dict[str, Any]) -> None:
    ensure_account_dirs()
    _write_json_file(LEDGER_FILE, data)


def _load_equity_curve() -> List[Dict[str, Any]]:
    if not EQUITY_FILE.exists():
        return []
    with open(EQUITY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_equity_curve(entries: List[Dict[str, Any]]) -> None:
    ensure_account_dirs()
    _write_json_file(EQUITY_FILE, entries)


def _write_json_file(path, payload, *, indent: int = 2) -> None:
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=indent, ensure_ascii=False)
    tmp.replace(path)


# ── Initialization ───────────────────────────────────────────────────────────

def initialize_ledger(initial_cash: float = DEFAULT_INITIAL_CASH, force: bool = False) -> str:
    ensure_account_dirs()
    if LEDGER_FILE.exists() and not force:
        return f"Ledger already exists at {LEDGER_FILE}. Use --force to reinitialize."

    ledger = _default_ledger()
    ledger["cash"] = initial_cash
    _save_ledger(ledger)
    return f"Initialized paper trading account with ${initial_cash:,.2f} USDC."


# ── Order Validation ─────────────────────────────────────────────────────────

def validate_order(
    symbol: str,
    side: str,
    qty: float,
    price: float,
    ledger: Dict[str, Any],
) -> tuple[bool, str]:
    """
    Validate an order. Returns (ok, reason).
    """
    if side not in ("BUY", "SELL"):
        return False, f"Invalid side: {side}"

    if qty <= 0:
        return False, f"Invalid quantity: {qty}"

    if price <= 0:
        return False, f"Invalid price: {price}"

    if side == "BUY":
        cost = qty * price * (1 + DEFAULT_FEE_RATE)
        if cost > ledger["cash"]:
            return False, f"Insufficient cash: need ${cost:,.2f}, have ${ledger['cash']:,.2f}"

    if side == "SELL":
        position = ledger["positions"].get(symbol)
        if not position:
            return False, f"No position in {symbol}"
        if qty > position["qty"]:
            return False, f"Cannot sell {qty}, only hold {position['qty']}"

    return True, "OK"


# ── Trade Execution ──────────────────────────────────────────────────────────

def execute_order(
    symbol: str,
    side: str,
    qty: float,
    price: Optional[float] = None,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
    reason: str = "",
    strategy: str = "",
    tags: Optional[List[str]] = None,
    confidence: Optional[float] = None,
    market_snapshot: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Unified trade execution entry point.
    If price is None, fetch live price from Hyperliquid.
    """
    ledger = _load_ledger()

    # Fetch live price if not specified
    if price is None:
        try:
            from skill_xstocks_trader.core.market_service import get_latest_price
            quote = get_latest_price(symbol)
            price = quote.get("price")
            if price is None:
                return f"❌ Cannot fetch price for {symbol}: {quote.get('error', 'unknown')}"
        except Exception as e:
            return f"❌ Price fetch failed: {e}"

    # Validate
    ok, msg = validate_order(symbol, side, qty, price, ledger)
    if not ok:
        return f"❌ Order rejected: {msg}"

    # Build trade record
    trade = {
        "id": len(ledger["trade_history"]) + 1,
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "fee": round(qty * price * DEFAULT_FEE_RATE, 4),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reason": reason,
    }
    if strategy:
        trade["strategy"] = strategy
    if tags:
        trade["tags"] = tags
    if confidence is not None:
        trade["confidence"] = confidence
    if market_snapshot:
        trade["market_snapshot"] = market_snapshot

    # Execute
    if side == "BUY":
        result = _execute_buy(ledger, symbol, qty, price, stop_loss, take_profit, reason, trade)
    else:
        result = _execute_sell(ledger, symbol, qty, price, reason, trade)

    _save_ledger(ledger)
    return result


def _execute_buy(
    ledger: Dict[str, Any],
    symbol: str,
    qty: float,
    price: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    reason: str,
    trade: Dict[str, Any],
) -> str:
    cost = qty * price
    fee = round(cost * DEFAULT_FEE_RATE, 4)
    total_cost = cost + fee

    ledger["cash"] -= total_cost

    # Update or create position
    pos = ledger["positions"].get(symbol)
    if pos:
        # Average up/down
        old_total = pos["qty"] * pos["avg_price"]
        new_total = old_total + cost
        pos["qty"] += qty
        pos["avg_price"] = round(new_total / pos["qty"], 4)
        pos["total_fees"] = round(pos.get("total_fees", 0) + fee, 4)
    else:
        pos = {
            "qty": qty,
            "avg_price": price,
            "total_fees": fee,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }
    if stop_loss is not None:
        pos["stop_loss"] = stop_loss
    if take_profit is not None:
        pos["take_profit"] = take_profit

    ledger["positions"][symbol] = pos
    trade["action"] = "BUY"
    ledger["trade_history"].append(trade)

    sl_str = f", SL=${stop_loss}" if stop_loss else ""
    tp_str = f", TP=${take_profit}" if take_profit else ""
    return (
        f"✅ BOUGHT {qty} {symbol} @ ${price:,.2f} "
        f"(fee=${fee:,.4f}, cost=${total_cost:,.2f}{sl_str}{tp_str})"
    )


def _execute_sell(
    ledger: Dict[str, Any],
    symbol: str,
    qty: float,
    price: float,
    reason: str,
    trade: Dict[str, Any],
) -> str:
    pos = ledger["positions"][symbol]
    proceeds = qty * price
    fee = round(proceeds * DEFAULT_FEE_RATE, 4)
    net_proceeds = proceeds - fee

    # Calculate P&L
    cost_basis = qty * pos["avg_price"]
    pnl = net_proceeds - cost_basis
    pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else 0

    ledger["cash"] += net_proceeds

    # Update position
    pos["qty"] -= qty
    pos["total_fees"] = round(pos.get("total_fees", 0) + fee, 4)

    if pos["qty"] <= 0.0001:  # essentially zero (floating point)
        del ledger["positions"][symbol]

    trade["action"] = "SELL"
    trade["pnl"] = round(pnl, 4)
    trade["pnl_pct"] = round(pnl_pct, 2)
    ledger["trade_history"].append(trade)

    emoji = "🟢" if pnl >= 0 else "🔴"
    return (
        f"✅ SOLD {qty} {symbol} @ ${price:,.2f} "
        f"(fee=${fee:,.4f}, PnL={emoji}${pnl:+,.2f} / {pnl_pct:+.2f}%)"
    )


# ── Pending Order Checks ─────────────────────────────────────────────────────

def check_pending_orders(current_prices: Dict[str, float]) -> List[str]:
    """Check and auto-execute stop-loss / take-profit."""
    ledger = _load_ledger()
    actions: List[str] = []

    for symbol, pos in list(ledger["positions"].items()):
        price = current_prices.get(symbol)
        if price is None:
            continue

        if pos.get("stop_loss") and price <= pos["stop_loss"]:
            result = execute_order(symbol, "SELL", pos["qty"], price, reason="Auto stop-loss triggered")
            actions.append(result)

        elif pos.get("take_profit") and price >= pos["take_profit"]:
            result = execute_order(symbol, "SELL", pos["qty"], price, reason="Auto take-profit triggered")
            actions.append(result)

    return actions


# ── Order Management ─────────────────────────────────────────────────────────

def update_orders(
    symbol: str,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> str:
    ledger = _load_ledger()
    pos = ledger["positions"].get(symbol)
    if not pos:
        return f"❌ No position in {symbol}"

    changes = []
    if stop_loss is not None:
        pos["stop_loss"] = stop_loss
        changes.append(f"SL=${stop_loss}")
    if take_profit is not None:
        pos["take_profit"] = take_profit
        changes.append(f"TP=${take_profit}")

    if not changes:
        return "No changes specified."

    ledger["positions"][symbol] = pos
    _save_ledger(ledger)
    return f"✅ Updated {symbol}: {', '.join(changes)}"


# ── Portfolio Status ─────────────────────────────────────────────────────────

def build_status(current_prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """Build portfolio status."""
    ledger = _load_ledger()

    # Optionally fetch live prices
    if current_prices is None:
        current_prices = {}
        try:
            from skill_xstocks_trader.core.market_service import get_latest_price
            for symbol in ledger["positions"]:
                quote = get_latest_price(symbol)
                if quote.get("price") is not None:
                    current_prices[symbol] = quote["price"]
        except Exception:
            pass

    # Check pending stop-loss/take-profit
    check_pending_orders(current_prices)
    # Reload in case pending orders triggered
    ledger = _load_ledger()

    positions_detail = []
    total_position_value = 0.0

    for symbol, pos in ledger["positions"].items():
        current = current_prices.get(symbol)
        market_value = (pos["qty"] * current) if current else None
        unrealized_pnl = None
        unrealized_pnl_pct = None

        if current:
            cost_basis = pos["qty"] * pos["avg_price"]
            unrealized_pnl = round((pos["qty"] * current) - cost_basis, 2)
            unrealized_pnl_pct = round((unrealized_pnl / cost_basis) * 100, 2) if cost_basis > 0 else 0
            total_position_value += market_value

        detail = {
            "symbol": symbol,
            "qty": pos["qty"],
            "avg_price": pos["avg_price"],
            "current_price": current,
            "market_value": round(market_value, 2) if market_value else None,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
        }
        if pos.get("stop_loss"):
            detail["stop_loss"] = pos["stop_loss"]
        if pos.get("take_profit"):
            detail["take_profit"] = pos["take_profit"]

        positions_detail.append(detail)

    total_equity = ledger["cash"] + total_position_value

    return {
        "cash": round(ledger["cash"], 2),
        "total_position_value": round(total_position_value, 2),
        "total_equity": round(total_equity, 2),
        "positions": positions_detail,
        "open_positions": len(ledger["positions"]),
        "total_trades": len(ledger["trade_history"]),
    }


# ── Trade History ────────────────────────────────────────────────────────────

def get_trade_history(days: int = 7) -> List[Dict[str, Any]]:
    """Return recent trade history."""
    ledger = _load_ledger()
    cutoff = datetime.now(timezone.utc).isoformat()[:10]  # rough filter

    history = ledger.get("trade_history", [])
    if days > 0:
        from datetime import timedelta
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff_dt.isoformat()
        history = [t for t in history if t.get("timestamp", "") >= cutoff_str]

    return history


def record_daily_snapshot(snapshot_date: Optional[str] = None) -> str:
    """Record daily equity snapshot."""
    status = build_status()
    date_str = snapshot_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    entry = {
        "date": date_str,
        "equity": status["total_equity"],
        "cash": status["cash"],
        "positions_value": status["total_position_value"],
        "open_positions": status["open_positions"],
    }

    curve = _load_equity_curve()
    # Replace if same date exists
    curve = [e for e in curve if e.get("date") != date_str]
    curve.append(entry)
    curve.sort(key=lambda x: x["date"])
    _save_equity_curve(curve)

    return f"Snapshot recorded for {date_str}: equity=${status['total_equity']:,.2f}"
