"""
trading_engine.py — Paper trading engine for Taiwan stocks.

Single source of truth for:
  - Ledger data access (load/save)
  - Order validation (limit up/down, price deviation, market session)
  - Trade execution (buy/sell via unified execute_order)
  - Pending order checks (auto-trigger stop-loss / take-profit)
  - Portfolio status & equity snapshots

Data files:
  - data/account/state/ledger.json — positions, cash, orders, trade history
  - data/account/state/equity.json — daily equity snapshots
"""

import json
import logging
import os
import tempfile
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from skill_tw_trader.core.market_data import Quote
from skill_tw_trader.core.market_data import get_quote as get_spot_price
from skill_tw_trader.core.market_calendar import get_twse_market_session
from skill_tw_trader.core.market_data.symbols import normalize_symbol
from skill_tw_trader.core.account_paths import EQUITY_FILE, LEDGER_FILE, ensure_account_dirs

logger = logging.getLogger(__name__)


class SpotPrice(Quote):
    symbol: str = "UNKNOWN"
    market: str = "tw"

# ── Paths & Constants ────────────────────────────────────────────────────────

DEFAULT_INITIAL_CASH = 1_000_000.0
TW_LIMIT_PCT = 0.10          # 台股漲跌停 ±10%
PRICE_DEVIATION_PCT = 0.02   # 價格偏離警戒線 2%
BUY_FEE_RATE = 0.001425      # 買進手續費
SELL_FEE_RATE = 0.001425     # 賣出手續費
SELL_TAX_RATE = 0.003        # 證交稅
SELL_TOTAL_RATE = SELL_FEE_RATE + SELL_TAX_RATE  # 賣出總費率

def _get_tick_size(price: float) -> float:
    """Taiwan stock tick sizes."""
    if price < 10: return 0.01
    if price < 50: return 0.05
    if price < 100: return 0.1
    if price < 500: return 0.5
    if price < 1000: return 1.0
    return 5.0


# ── Data Access ──────────────────────────────────────────────────────────────

def _default_ledger() -> Dict[str, Any]:
    return {
        "cash": float(DEFAULT_INITIAL_CASH),
        "realized_pnl": 0.0,
        "positions": {},
        "orders": {},
        "trade_history": [],
    }


def _load_ledger() -> Dict[str, Any]:
    if not LEDGER_FILE.exists():
        return _default_ledger()
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("trade_history", [])
    data.setdefault("orders", {})

    # Migrate legacy: stop_loss/take_profit from positions → orders
    migrated = False
    for sym, pos in data.get("positions", {}).items():
        if "stop_loss" in pos or "take_profit" in pos:
            order = data["orders"].setdefault(sym, {})
            if "stop_loss" in pos:
                order["stop_loss"] = pos.pop("stop_loss")
                migrated = True
            if "take_profit" in pos:
                order["take_profit"] = pos.pop("take_profit")
                migrated = True
    if migrated:
        _save_ledger(data)

    return data


def _save_ledger(data: Dict[str, Any]):
    ensure_account_dirs()
    _write_json_file(LEDGER_FILE, data, indent=4)


def _load_equity_curve() -> List[Dict[str, Any]]:
    if not EQUITY_FILE.exists():
        return []
    with open(EQUITY_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def _save_equity_curve(entries: List[Dict[str, Any]]):
    ensure_account_dirs()
    _write_json_file(EQUITY_FILE, entries, indent=2)


def _write_json_file(path, payload, *, indent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.stem}-",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        json.dump(payload, tmp, indent=indent, ensure_ascii=False)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def _get_current_prices(ledger: Dict[str, Any]) -> Dict[str, float]:
    prices = {}
    for sym in ledger.get("positions", {}):
        try:
            spot = get_spot_price(sym)
            prices[sym] = spot.price
        except Exception:
            pass
    return prices


# ── Order Validation ─────────────────────────────────────────────────────────

def _calc_limit_prices(prev_close: float) -> tuple[float, float]:
    """Calculate limit-up and limit-down prices from previous close, considering tick size."""
    tick = _get_tick_size(prev_close)
    limit_up = (prev_close * (1 + TW_LIMIT_PCT)) // tick * tick
    limit_down = (prev_close * (1 - TW_LIMIT_PCT) + tick - 0.000001) // tick * tick
    return round(limit_up, 2), round(limit_down, 2)


def _is_locked_limit_up(spot: SpotPrice) -> bool:
    """Check if stock is locked at limit-up (漲停鎖死)."""
    if spot.prev_close is None:
        return False
    limit_up, _ = _calc_limit_prices(spot.prev_close)
    return spot.price is not None and spot.price >= limit_up


def _is_locked_limit_down(spot: SpotPrice) -> bool:
    """Check if stock is locked at limit-down (跌停鎖死)."""
    if spot.prev_close is None:
        return False
    _, limit_down = _calc_limit_prices(spot.prev_close)
    return spot.price is not None and spot.price <= limit_down


def validate_order(
    symbol: str,
    side: str,
    price: Optional[float],
    spot: SpotPrice,
) -> tuple[bool, str, float]:
    """
    Validate an order against market conditions.

    Returns: (ok, reason, fill_price)
      - ok=True:  order is valid, fill_price is the validated price
      - ok=False: order rejected, reason explains why
    """
    fill_price = price if price is not None else spot.price

    if fill_price is None or fill_price <= 0:
        return False, "Invalid price.", 0.0

    # Limit-up / limit-down checks
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

    # Price deviation check
    if spot.price and spot.price > 0:
        deviation = abs(fill_price - spot.price) / spot.price
        if deviation > PRICE_DEVIATION_PCT:
            return (
                False,
                f"Price {fill_price} deviates {deviation:.1%} from current {spot.price} (max {PRICE_DEVIATION_PCT:.0%}).",
                0.0,
            )

    return True, "", fill_price


# ── Trade Execution ──────────────────────────────────────────────────────────

def execute_order(
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
    market_snapshot: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Unified trade execution entry point.

    Args:
        symbol: Stock symbol (e.g. "2330" or "2330.TW")
        side: "BUY" or "SELL"
        qty: Number of shares
        price: Execution price. None → market order (use current spot price)
        stop_loss: Stop-loss price (required for new BUY positions)
        take_profit: Take-profit price (optional)
        reason: Trade reason (required for new BUY positions)
        strategy: Strategy tag (e.g. "momentum")
        tags: Theme/sector tags (e.g. ["satellite", "leo"])
        confidence: Entry confidence 0.0-1.0
        market_snapshot: Normalized market state vector (from build_trade_snapshot)
    """
    if qty <= 0:
        return "Error: Quantity must be greater than 0."

    side = side.upper()
    if side not in ("BUY", "SELL"):
        return "Error: Side must be BUY or SELL."

    symbol = normalize_symbol(symbol)

    # Fetch spot price
    try:
        spot = get_spot_price(symbol)
    except Exception as e:
        return f"Error: Cannot fetch price for {symbol}: {e}"

    # Market order: use current spot price
    fill_price = price if price is not None else spot.price
    if fill_price is None or fill_price <= 0:
        return "Error: No valid price available."

    # Validate
    session = get_twse_market_session()
    if session == "closed":
        return "Error: Market is closed today. Cannot execute orders."

    ok, reject_reason, validated_price = validate_order(symbol, side, fill_price, spot)
    if not ok:
        return f"Order rejected: {reject_reason}"

    # Dispatch
    ledger = _load_ledger()
    extra = {
        "strategy": strategy,
        "tags": tags or [],
        "confidence": confidence,
        "market_snapshot": market_snapshot,
    }
    if side == "BUY":
        result = _execute_buy(ledger, symbol, qty, validated_price, stop_loss, take_profit, reason, extra)
    else:
        result = _execute_sell(ledger, symbol, qty, validated_price, reason, extra)

    _save_ledger(ledger)
    return result


def _execute_buy(
    ledger: Dict[str, Any],
    symbol: str,
    qty: int,
    price: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    is_new = symbol not in ledger["positions"]

    if is_new and not stop_loss:
        return "Error: stop_loss is required when opening a new position."
    if is_new and not reason:
        return "Error: reason is required when opening a new position."

    cost = qty * price
    fee = round(cost * BUY_FEE_RATE)
    total_cost = cost + fee

    if ledger["cash"] < total_cost:
        return (
            f"Error: Insufficient funds. "
            f"Have {ledger['cash']:.2f}, need {total_cost:.2f}."
        )

    ledger["cash"] -= total_cost

    # Update position (weighted average)
    pos = ledger["positions"].get(symbol, {
        "shares": 0,
        "avg_price": 0.0,
        "reason": "",
        "entry_date": date.today().isoformat(),
    })
    old_shares = pos["shares"]
    old_avg = pos["avg_price"]
    new_shares = old_shares + qty
    pos["shares"] = new_shares
    pos["avg_price"] = ((old_shares * old_avg) + total_cost) / new_shares
    if reason:
        pos["reason"] = reason
    ledger["positions"][symbol] = pos

    # Update orders
    if stop_loss is not None or take_profit is not None:
        order = ledger["orders"].get(symbol, {})
        if stop_loss is not None:
            order["stop_loss"] = stop_loss
        if take_profit is not None:
            order["take_profit"] = take_profit
        ledger["orders"][symbol] = order

    # Record trade
    extra = extra or {}
    trade_record: Dict[str, Any] = {
        "date": datetime.now().isoformat(),
        "action": "BUY",
        "symbol": symbol,
        "quantity": qty,
        "price": price,
        "fee": fee,
        "total_cost": total_cost,
        "reason": reason,
    }
    if extra.get("strategy"):
        trade_record["strategy"] = extra["strategy"]
    if extra.get("tags"):
        trade_record["tags"] = extra["tags"]
    if extra.get("confidence") is not None:
        trade_record["confidence"] = extra["confidence"]
    if extra.get("market_snapshot"):
        trade_record["market_snapshot"] = extra["market_snapshot"]
    ledger["trade_history"].append(trade_record)

    order = ledger["orders"].get(symbol, {})
    return (
        f"Filled: Bought {qty} shares of {symbol} at {price:.2f}. "
        f"Fee: {fee}, Total cost: {total_cost:.2f}. "
        f"Stop-loss: {order.get('stop_loss')}, Take-profit: {order.get('take_profit')}. "
        f"Remaining cash: {ledger['cash']:.2f}."
    )


def _execute_sell(
    ledger: Dict[str, Any],
    symbol: str,
    qty: int,
    price: float,
    reason: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    pos = ledger["positions"].get(symbol)

    if not pos or pos["shares"] < qty:
        held = pos["shares"] if pos else 0
        return f"Error: Insufficient shares. Own {held} shares of {symbol}."

    revenue = qty * price
    tax_and_fee = round(revenue * SELL_TOTAL_RATE)
    net_revenue = revenue - tax_and_fee

    cost_basis = qty * pos["avg_price"]
    trade_pnl = net_revenue - cost_basis

    ledger["cash"] += net_revenue
    ledger["realized_pnl"] += trade_pnl

    extra = extra or {}
    trade_record: Dict[str, Any] = {
        "date": datetime.now().isoformat(),
        "action": "SELL",
        "symbol": symbol,
        "quantity": qty,
        "price": price,
        "tax_and_fee": tax_and_fee,
        "net_revenue": net_revenue,
        "pnl": round(trade_pnl, 2),
        "reason": reason,
    }
    # Compute pnl_r (R-multiple) using stop-loss as 1R
    order = ledger["orders"].get(symbol, {})
    sl = order.get("stop_loss")
    if sl and pos["avg_price"] > 0:
        risk_per_share = pos["avg_price"] - sl
        if risk_per_share > 0:
            trade_record["pnl_r"] = round(trade_pnl / (qty * risk_per_share), 2)
    if extra.get("strategy"):
        trade_record["strategy"] = extra["strategy"]
    if extra.get("tags"):
        trade_record["tags"] = extra["tags"]
    if extra.get("market_snapshot"):
        trade_record["market_snapshot"] = extra["market_snapshot"]
    ledger["trade_history"].append(trade_record)

    pos["shares"] -= qty
    if pos["shares"] == 0:
        del ledger["positions"][symbol]
        ledger["orders"].pop(symbol, None)

    return (
        f"Filled: Sold {qty} shares of {symbol} at {price:.2f}. "
        f"Net revenue: {net_revenue:.2f}. Realized PnL: {trade_pnl:+,.2f}. "
        f"Remaining cash: {ledger['cash']:.2f}."
    )


# ── Pending Order Checks ─────────────────────────────────────────────────────

def check_pending_orders(current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
    """Check and auto-execute stop-loss / take-profit. Loads ledger once."""
    ledger = _load_ledger()
    executed = []
    modified = False

    for sym, order in list(ledger["orders"].items()):
        curr_price = current_prices.get(sym)
        if curr_price is None:
            continue

        pos = ledger["positions"].get(sym)
        if not pos or pos["shares"] <= 0:
            continue

        sl = order.get("stop_loss")
        tp = order.get("take_profit")

        if sl is not None and curr_price <= sl:
            result = _execute_sell(ledger, sym, pos["shares"], curr_price, f"SL triggered at {curr_price}")
            executed.append({"type": "stop_loss", "symbol": sym, "price": curr_price, "result": result})
            modified = True
            continue

        if tp is not None and curr_price >= tp:
            result = _execute_sell(ledger, sym, pos["shares"], curr_price, f"TP triggered at {curr_price}")
            executed.append({"type": "take_profit", "symbol": sym, "price": curr_price, "result": result})
            modified = True

    if modified:
        _save_ledger(ledger)
    return executed


# ── Order Management ─────────────────────────────────────────────────────────

def update_orders(
    symbol: str,
    stop_loss: Optional[float] = None,
    take_profit: Optional[float] = None,
) -> str:
    symbol = normalize_symbol(symbol)
    ledger = _load_ledger()

    if symbol not in ledger["positions"]:
        return f"Error: No open position for {symbol}."
    if stop_loss is None and take_profit is None:
        return "Error: Provide at least --stop-loss or --take-profit."

    order = ledger["orders"].get(symbol, {})
    if stop_loss is not None:
        order["stop_loss"] = stop_loss
    if take_profit is not None:
        order["take_profit"] = take_profit
    ledger["orders"][symbol] = order
    _save_ledger(ledger)

    return (
        f"Updated {symbol}: stop_loss={order.get('stop_loss')}, "
        f"take_profit={order.get('take_profit')}"
    )


# ── Portfolio Status ─────────────────────────────────────────────────────────

def build_status(current_prices: Optional[Dict[str, float]] = None) -> dict:
    """Build portfolio status. Automatically checks pending orders first."""
    if current_prices is None:
        ledger = _load_ledger()
        current_prices = _get_current_prices(ledger)

    # Auto-trigger stop-loss / take-profit
    auto_executed = check_pending_orders(current_prices)

    # Reload ledger after potential auto-executions
    ledger = _load_ledger()

    # Compute account value
    total_market_value = 0.0
    for sym, pos in ledger["positions"].items():
        if sym in current_prices:
            total_market_value += pos["shares"] * current_prices[sym]
        else:
            total_market_value += pos["shares"] * pos["avg_price"]
    account_value = ledger["cash"] + total_market_value

    # Positions
    positions = []
    for sym, pos in ledger["positions"].items():
        shares = pos["shares"]
        avg_price = pos["avg_price"]
        cost = shares * avg_price

        entry = {
            "symbol": sym,
            "shares": shares,
            "avg_price": round(avg_price, 2),
            "cost": round(cost, 0),
            "reason": pos.get("reason", ""),
        }

        if sym in current_prices:
            curr = current_prices[sym]
            mkt_val = shares * curr
            pnl = mkt_val - cost
            pnl_pct = (pnl / cost) * 100 if cost > 0 else 0
            entry["current_price"] = curr
            entry["market_value"] = round(mkt_val, 0)
            entry["unrealized_pnl"] = round(pnl, 0)
            entry["unrealized_pnl_pct"] = round(pnl_pct, 1)
            entry["allocation_pct"] = round(mkt_val / account_value * 100, 1) if account_value > 0 else 0

        positions.append(entry)

    # Orders
    orders = []
    for sym, order in ledger["orders"].items():
        entry = {"symbol": sym}
        curr = current_prices.get(sym)

        if "stop_loss" in order:
            entry["stop_loss"] = order["stop_loss"]
            if curr and curr > 0:
                entry["dist_to_stop_pct"] = round((order["stop_loss"] - curr) / curr * 100, 1)
        if "take_profit" in order:
            entry["take_profit"] = order["take_profit"]
            if curr and curr > 0:
                entry["dist_to_take_pct"] = round((order["take_profit"] - curr) / curr * 100, 1)

        orders.append(entry)

    # Today's realized PnL
    today_str = date.today().isoformat()
    today_trades = [
        t for t in ledger.get("trade_history", [])
        if t["date"].startswith(today_str)
    ]
    today_realized = sum(t.get("pnl", 0) for t in today_trades)
    today_realized_pct = (today_realized / account_value * 100) if account_value > 0 else 0

    # Summary
    total_unrealized = sum(p.get("unrealized_pnl", 0) for p in positions)
    exposure_pct = (total_market_value / account_value * 100) if account_value > 0 else 0

    summary = {
        "account_value": round(account_value, 0),
        "market_value": round(total_market_value, 0),
        "unrealized_pnl": round(total_unrealized, 0),
        "realized_pnl": round(ledger["realized_pnl"], 0),
        "exposure_pct": round(exposure_pct, 0),
        "cash_pct": round(100 - exposure_pct, 0),
        "today_realized_pnl": round(today_realized, 0),
        "today_realized_pnl_pct": round(today_realized_pct, 2),
    }

    # Alerts
    alerts = []
    for p in positions:
        sym = p["symbol"]
        alloc = p.get("allocation_pct", 0)
        if alloc > 30:
            alerts.append(f"{sym} allocation {alloc}% exceeds 30% limit")

    for o in orders:
        sym = o["symbol"]
        dist = o.get("dist_to_stop_pct")
        if dist is not None and dist > -3:
            alerts.append(f"{sym} within {abs(dist)}% of stop-loss {o['stop_loss']}")
        dist_tp = o.get("dist_to_take_pct")
        if dist_tp is not None and dist_tp <= 0:
            alerts.append(f"{sym} exceeded take-profit {o['take_profit']} by {abs(dist_tp)}%")

    if today_realized_pct < -3:
        alerts.append(f"Daily loss {today_realized_pct:.1f}% exceeds -3% limit — no new buys")

    # Assemble
    result = {
        "cash": round(ledger["cash"], 0),
        "positions": positions,
        "orders": orders,
        "summary": summary,
    }
    if alerts:
        result["alerts"] = alerts
    if auto_executed:
        result["auto_executed"] = auto_executed
    if today_trades:
        result["today_trades"] = [
            {
                "action": t["action"],
                "symbol": t["symbol"],
                "quantity": t["quantity"],
                "price": t["price"],
                **({"pnl": t["pnl"]} if "pnl" in t else {}),
            }
            for t in today_trades
        ]

    return result


# ── Trade History ────────────────────────────────────────────────────────────

def get_trade_history(days: int = 7) -> str:
    ledger = _load_ledger()
    history = ledger.get("trade_history", [])

    if not history:
        return "No trade history."

    recent = history[-20:]

    lines = ["=== Recent Trade History ==="]
    for t in recent:
        pnl_str = f" PnL: {t['pnl']:+,.0f}" if "pnl" in t else ""
        lines.append(
            f"  {t['date'][:10]} {t['action']} {t['symbol']} "
            f"x{t['quantity']} @ {t['price']:.2f}{pnl_str}"
            + (f" — {t['reason']}" if t.get('reason') else "")
        )

    return "\n".join(lines)


# ── Equity Snapshots ─────────────────────────────────────────────────────────

def record_daily_snapshot(snapshot_date: Optional[str] = None) -> str:
    status = build_status()

    snapshot_day = snapshot_date or date.today().isoformat()
    recorded_at = datetime.now().isoformat(timespec="seconds")
    summary = status["summary"]

    entry = {
        "date": snapshot_day,
        "recorded_at": recorded_at,
        "account_value": summary["account_value"],
        "cash": status["cash"],
        "market_value": summary["market_value"],
        "realized_pnl": summary["realized_pnl"],
        "unrealized_pnl": summary["unrealized_pnl"],
        "exposure_pct": summary["exposure_pct"],
        "cash_pct": summary["cash_pct"],
        "positions_count": len(status.get("positions", [])),
    }

    curve = [item for item in _load_equity_curve() if item.get("date") != snapshot_day]
    curve.append(entry)
    curve.sort(key=lambda item: item.get("date", ""))
    _save_equity_curve(curve)

    return (
        f"Recorded equity snapshot for {snapshot_day}: "
        f"account_value={entry['account_value']}, cash={entry['cash']}, market_value={entry['market_value']}."
    )


def get_equity_curve(days: Optional[int] = None) -> List[Dict[str, Any]]:
    curve = _load_equity_curve()
    if days is None or days <= 0:
        return curve
    return curve[-days:]


# ── Ledger Init ──────────────────────────────────────────────────────────────

def initialize_ledger(initial_cash: float = DEFAULT_INITIAL_CASH, force: bool = False) -> str:
    if initial_cash <= 0:
        return "Error: Initial cash must be greater than 0."
    ensure_account_dirs()
    if LEDGER_FILE.exists() and not force:
        return (
            f"Error: {LEDGER_FILE.name} already exists. "
            "Use --force to replace it."
        )

    ledger = _default_ledger()
    ledger["cash"] = float(initial_cash)
    _save_ledger(ledger)
    _save_equity_curve([])

    return (
        f"Initialized ledger at {LEDGER_FILE} with cash {initial_cash:.2f}. "
        f"Equity file: {EQUITY_FILE}."
    )
