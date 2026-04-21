from __future__ import annotations

from market_core.broker.engine import (
    cancel_order,
    evaluate_orders,
    place_order,
)
from market_core.models import Bar, OrderRequest, Quote, TradingState
from market_core.policies import get_market_profile

TW = get_market_profile("tw_equity")
US = get_market_profile("us_equity")


def _state(cash: float = 1_000_000.0) -> TradingState:
    return TradingState(cash=cash)


def _quote(symbol: str, price: float, *, change_pct: float = 0.0, is_limit_up: bool = False, is_limit_down: bool = False) -> Quote:
    return Quote(
        symbol=symbol,
        market_profile="tw_equity",
        price=price,
        source="test",
        change_pct=change_pct,
        is_limit_up=is_limit_up,
        is_limit_down=is_limit_down,
    )


def _bar(symbol: str, time: str, *, o: float, h: float, l: float, c: float) -> Bar:
    return Bar(
        symbol=symbol,
        market_profile="tw_equity",
        bar_time=time,
        open=o,
        high=h,
        low=l,
        close=c,
        source="test",
    )


# ─── MARKET orders ──────────────────────────────────────────────────────────


def test_market_buy_fills_immediately_at_quote_price():
    state = _state()
    order = place_order(
        state,
        TW,
        OrderRequest(symbol="2330.TW", side="BUY", type="MARKET", quantity=1000, stop_loss=550.0, reason="test"),
    )
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    assert len(trades) == 1
    assert trades[0].price == 600.0
    assert trades[0].quantity == 1000
    assert order.status == "FILLED"
    assert order.fill_price == 600.0
    assert "2330.TW" in state.positions
    # attached stop_loss order was created
    stops = [o for o in state.orders if o.type == "STOP_LOSS"]
    assert len(stops) == 1 and stops[0].trigger_price == 550.0 and stops[0].status == "PENDING"


def test_market_buy_blocked_on_limit_up():
    state = _state()
    place_order(
        state,
        TW,
        OrderRequest(symbol="3189.TW", side="BUY", type="MARKET", quantity=100, stop_loss=400.0, reason="test"),
    )
    trades = evaluate_orders(
        state, TW, {"3189.TW": _quote("3189.TW", 470.0, change_pct=9.99, is_limit_up=True)}
    )

    assert trades == []
    assert state.orders[0].status == "PENDING"
    assert state.cash == 1_000_000.0


def test_market_sell_blocked_on_limit_down():
    state = _state()
    place_order(state, TW, OrderRequest(symbol="2330.TW", side="BUY", type="MARKET", quantity=1000, stop_loss=550.0, reason="test"))
    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    sell_order = place_order(state, TW, OrderRequest(symbol="2330.TW", side="SELL", type="MARKET", quantity=1000))
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 540.0, change_pct=-9.95, is_limit_down=True)})

    assert trades == []
    assert sell_order.status == "PENDING"


def test_market_buy_cancelled_on_insufficient_cash():
    state = _state(cash=10_000.0)
    order = place_order(
        state,
        TW,
        OrderRequest(symbol="2330.TW", side="BUY", type="MARKET", quantity=100, stop_loss=550.0, reason="test"),
    )
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    assert trades == []
    assert order.status == "CANCELLED"
    assert "insufficient cash" in (order.cancelled_reason or "")
    assert state.cash == 10_000.0


# ─── LIMIT orders ───────────────────────────────────────────────────────────


def test_limit_buy_fills_when_bar_low_crosses():
    state = _state()
    order = place_order(
        state,
        TW,
        OrderRequest(
            symbol="2330.TW", side="BUY", type="LIMIT", quantity=1000, limit_price=580.0,
            stop_loss=550.0, reason="test",
        ),
    )
    bars = [_bar("2330.TW", "2026-04-21T01:00:00Z", o=590, h=592, l=585, c=588)]
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 588.0)}, {"2330.TW": bars})
    assert trades == []  # didn't reach 580
    assert order.status == "PENDING"

    bars2 = bars + [_bar("2330.TW", "2026-04-21T02:00:00Z", o=585, h=586, l=575, c=580)]
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 580.0)}, {"2330.TW": bars2})
    assert len(trades) == 1
    assert trades[0].price == 580.0
    assert order.status == "FILLED"


def test_limit_buy_gap_down_fills_at_open():
    state = _state()
    order = place_order(
        state,
        TW,
        OrderRequest(
            symbol="2330.TW", side="BUY", type="LIMIT", quantity=1000, limit_price=580.0,
            stop_loss=550.0, reason="test",
        ),
    )
    # bar opens below limit — fill at open, not limit
    bars = [_bar("2330.TW", "2026-04-21T01:00:00Z", o=570, h=575, l=565, c=568)]
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 568.0)}, {"2330.TW": bars})
    assert len(trades) == 1
    assert trades[0].price == 570.0
    assert order.fill_price == 570.0


def test_limit_expires_after_configured_days():
    from datetime import datetime, timedelta, timezone

    state = _state()
    order = place_order(
        state,
        TW,
        OrderRequest(
            symbol="2330.TW", side="BUY", type="LIMIT", quantity=1000, limit_price=580.0,
            stop_loss=550.0, reason="test",
        ),
    )
    # Backdate placed_at beyond the expiry window.
    order.placed_at = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat().replace("+00:00", "Z")

    trades = evaluate_orders(
        state, TW, {"2330.TW": _quote("2330.TW", 600.0)}, {},
        expire_limit_after_days=3,
    )

    assert trades == []
    assert order.status == "CANCELLED"
    assert "expired" in (order.cancelled_reason or "")


def test_limit_within_expiry_window_still_fills():
    state = _state()
    order = place_order(
        state,
        TW,
        OrderRequest(
            symbol="2330.TW", side="BUY", type="LIMIT", quantity=1000, limit_price=580.0,
            stop_loss=550.0, reason="test",
        ),
    )
    bars = [_bar("2330.TW", "2026-04-21T01:00:00Z", o=585, h=586, l=575, c=580)]
    trades = evaluate_orders(
        state, TW, {"2330.TW": _quote("2330.TW", 580.0)}, {"2330.TW": bars},
        expire_limit_after_days=3,
    )
    assert len(trades) == 1
    assert order.status == "FILLED"


def test_stop_loss_does_not_expire():
    """STOP_LOSS/TAKE_PROFIT are tied to position lifetime, never expire."""
    from datetime import datetime, timedelta, timezone

    state = _state()
    place_order(state, TW, OrderRequest(symbol="2330.TW", side="BUY", type="MARKET", quantity=1000, stop_loss=550.0, reason="test"))
    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    stop = next(o for o in state.orders if o.type == "STOP_LOSS")
    stop.placed_at = (datetime.now(timezone.utc) - timedelta(days=99)).isoformat().replace("+00:00", "Z")

    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)}, {}, expire_limit_after_days=3)
    assert stop.status == "PENDING"


# ─── STOP_LOSS / TAKE_PROFIT ────────────────────────────────────────────────


def test_stop_loss_triggers_when_bar_low_breaches():
    state = _state()
    place_order(state, TW, OrderRequest(symbol="2330.TW", side="BUY", type="MARKET", quantity=1000, stop_loss=550.0, reason="test"))
    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    stop = next(o for o in state.orders if o.type == "STOP_LOSS")
    bars = [_bar("2330.TW", "2026-04-21T03:00:00Z", o=545, h=548, l=540, c=542)]
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 542.0)}, {"2330.TW": bars})

    assert len(trades) == 1
    assert trades[0].action == "SELL"
    assert trades[0].price == 545.0  # gap-down: open below trigger → fill at open
    assert "2330.TW" not in state.positions
    assert stop.status == "FILLED"


def test_position_close_cancels_remaining_take_profit():
    state = _state()
    place_order(
        state, TW,
        OrderRequest(
            symbol="2330.TW", side="BUY", type="MARKET", quantity=1000,
            stop_loss=550.0, take_profit=700.0, reason="test",
        ),
    )
    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    bars = [_bar("2330.TW", "2026-04-21T03:00:00Z", o=545, h=548, l=540, c=542)]
    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 542.0)}, {"2330.TW": bars})

    take = next(o for o in state.orders if o.type == "TAKE_PROFIT")
    assert take.status == "CANCELLED"
    assert take.cancelled_reason == "position closed"


def test_stop_loss_priority_over_take_profit_in_same_sweep():
    """If a single bar would breach both stop and take, stop fires first (conservative)."""
    state = _state()
    place_order(
        state, TW,
        OrderRequest(
            symbol="2330.TW", side="BUY", type="MARKET", quantity=1000,
            stop_loss=550.0, take_profit=700.0, reason="test",
        ),
    )
    evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 600.0)})

    # wide-range bar: low breaches stop, high breaches take
    bars = [_bar("2330.TW", "2026-04-21T03:00:00Z", o=600, h=720, l=540, c=560)]
    trades = evaluate_orders(state, TW, {"2330.TW": _quote("2330.TW", 560.0)}, {"2330.TW": bars})

    assert len(trades) == 1
    stop = next(o for o in state.orders if o.type == "STOP_LOSS")
    take = next(o for o in state.orders if o.type == "TAKE_PROFIT")
    assert stop.status == "FILLED"
    assert trades[0].order_id == stop.id  # stop fired, not take
    assert trades[0].price == 550.0  # open above trigger → fill at trigger (best case)
    assert take.status == "CANCELLED"  # position closed by stop


# ─── cancellation ───────────────────────────────────────────────────────────


def test_cancel_pending_order():
    state = _state()
    order = place_order(
        state, TW,
        OrderRequest(symbol="2330.TW", side="BUY", type="LIMIT", quantity=1000, limit_price=500.0, stop_loss=480.0, reason="test"),
    )
    cancelled = cancel_order(state, order.id, reason="changed mind")
    assert cancelled.status == "CANCELLED"
    assert cancelled.cancelled_reason == "changed mind"


# ─── validation ─────────────────────────────────────────────────────────────


def test_buy_without_stop_loss_rejected_for_new_position():
    state = _state()
    try:
        place_order(state, TW, OrderRequest(symbol="2330.TW", side="BUY", type="MARKET", quantity=1000, reason="test"))
    except ValueError as exc:
        assert "stop_loss" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_sell_without_position_rejected():
    state = _state()
    try:
        place_order(state, TW, OrderRequest(symbol="2330.TW", side="SELL", type="MARKET", quantity=1000))
    except ValueError as exc:
        assert "insufficient quantity" in str(exc)
    else:
        raise AssertionError("expected ValueError")
