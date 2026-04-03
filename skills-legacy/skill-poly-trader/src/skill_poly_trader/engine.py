from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .api import build_event_candidates, build_snapshots, fetch_market_by_slug, market_to_snapshot
from .llm import estimate_yes_probability, validate_llm_config
from .models import MarketSnapshot, TradeDecision

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER_PATH = APP_ROOT / "data" / "ledger.json"
DEFAULT_INITIAL_CASH = 10_000.0
MIN_VOLUME_24H = 50_000.0
MIN_LIQUIDITY = 50_000.0
MAX_SPREAD = 0.08
EDGE_THRESHOLD = 0.015
# Insurance model: lower edge threshold for high-probability NO trades (NO >= 0.88)
INSURANCE_NO_FLOOR = 0.88
INSURANCE_EDGE_THRESHOLD = 0.03


def initialize_ledger(initial_cash: float = DEFAULT_INITIAL_CASH, force: bool = False, ledger_path: Path | None = None) -> str:
    path = ledger_path or DEFAULT_LEDGER_PATH
    if path.exists() and not force:
        return f"Ledger already exists at {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "version": 1,
        "starting_cash": float(initial_cash),
        "cash": float(initial_cash),
        "open_positions": [],
        "history": [],
        "last_run_at": None,
    }
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return f"Initialized ledger at {path} with cash=${initial_cash:.2f}"


def load_ledger(ledger_path: Path | None = None) -> dict:
    path = ledger_path or DEFAULT_LEDGER_PATH
    if not path.exists():
        initialize_ledger(ledger_path=path)
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(ledger: dict, ledger_path: Path | None = None) -> None:
    path = ledger_path or DEFAULT_LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def decide_trade(
    snapshot: MarketSnapshot,
    *,
    paper_size: float = 25.0,
    probability_fn: Callable[[MarketSnapshot], tuple[float, str]] | None = None,
) -> TradeDecision:
    scorer = probability_fn or estimate_yes_probability
    model_yes, model_name = scorer(snapshot)
    return decision_from_probability(
        snapshot,
        model_yes=model_yes,
        paper_size=paper_size,
        reason=f"LLM ({model_name}) estimated YES at {model_yes:.3f} from market snapshot",
    )


def decision_from_probability(
    snapshot: MarketSnapshot,
    *,
    model_yes: float,
    paper_size: float = 25.0,
    reason: str,
) -> TradeDecision:
    market_yes = snapshot.yes_price
    market_no = snapshot.no_price

    if snapshot.volume_24h < MIN_VOLUME_24H:
        return _no_trade(snapshot, market_yes, reason=f"NO_TRADE: 24h volume below floor ({snapshot.volume_24h:.0f})")
    if snapshot.liquidity < MIN_LIQUIDITY:
        return _no_trade(snapshot, market_yes, reason=f"NO_TRADE: liquidity below floor ({snapshot.liquidity:.0f})")
    if snapshot.spread is not None and snapshot.spread > MAX_SPREAD:
        return _no_trade(snapshot, market_yes, reason=f"NO_TRADE: spread too wide ({snapshot.spread:.3f})")

    edge_yes = model_yes - market_yes
    edge_no = (1.0 - model_yes) - market_no

    # Insurance model: when NO price >= 0.88 (YES <= 0.12), use a lower
    # edge threshold.  These trades have 88%+ win rate by construction,
    # so even a small edge compounds well.
    is_insurance = market_no >= INSURANCE_NO_FLOOR
    effective_threshold = INSURANCE_EDGE_THRESHOLD if is_insurance else EDGE_THRESHOLD

    if edge_yes >= EDGE_THRESHOLD and edge_yes >= edge_no:
        shares = round(paper_size / max(market_yes, 0.01), 4)
        return TradeDecision(
            action="BUY_YES",
            market_id=snapshot.market_id,
            slug=snapshot.slug,
            question=snapshot.question,
            market_yes=market_yes,
            model_yes=model_yes,
            edge=edge_yes,
            paper_size=paper_size,
            shares=shares,
            reason=reason,
        )

    if edge_no >= effective_threshold:
        tag = " [insurance]" if is_insurance else ""
        shares = round(paper_size / max(market_no, 0.01), 4)
        return TradeDecision(
            action="BUY_NO",
            market_id=snapshot.market_id,
            slug=snapshot.slug,
            question=snapshot.question,
            market_yes=market_yes,
            model_yes=model_yes,
            edge=edge_no,
            paper_size=paper_size,
            shares=shares,
            reason=reason + tag,
        )

    return _no_trade(snapshot, model_yes, reason=f"NO_TRADE: edge below threshold (yes={edge_yes:.3f}, no={edge_no:.3f}, threshold={effective_threshold:.3f})")


def build_scan_report(*, limit: int = 12, candidate_count: int = 6) -> dict:
    events = build_event_candidates(limit=limit, max_markets_per_event=candidate_count)
    # Drop events with no tradeable markets to keep output lean
    tradeable = [e for e in events if e["markets"]]
    total_markets = sum(len(e["markets"]) for e in tradeable)
    return {
        "timestamp": _now_iso(),
        "scanned": total_markets,
        "event_count": len(tradeable),
        "events": [
            {
                "event_id": event["event_id"],
                "title": event["title"],
                "category": event["category"],
                "markets": [snapshot.to_dict() for snapshot in event["markets"]],
            }
            for event in tradeable
        ],
    }


def run_cycle(
    *,
    limit: int = 12,
    candidate_count: int = 6,
    paper_size: float = 25.0,
    dry_run: bool = False,
    ledger_path: Path | None = None,
    probability_fn: Callable[[MarketSnapshot], tuple[float, str]] | None = None,
) -> dict:
    if probability_fn is None:
        validate_llm_config()

    ledger = load_ledger(ledger_path=ledger_path)
    run_timestamp = _now_iso()
    ledger["last_run_at"] = run_timestamp
    snapshots = build_snapshots(limit=limit, max_candidates=candidate_count)
    decisions: list[TradeDecision] = []
    for snapshot in snapshots:
        try:
            decisions.append(decide_trade(snapshot, paper_size=paper_size, probability_fn=probability_fn))
        except Exception as exc:
            decisions.append(_no_trade(snapshot, snapshot.yes_price, reason=f"NO_TRADE: forecast failed ({exc})"))
    trade_candidates = [decision for decision in decisions if decision.action != "NO_TRADE"]
    selected = max(trade_candidates, key=lambda item: item.edge, default=None)

    trade_record = None
    if selected and not dry_run and ledger["cash"] >= selected.paper_size:
        trade_record = _apply_paper_trade(ledger, selected)
        save_ledger(ledger, ledger_path=ledger_path)
    else:
        save_ledger(ledger, ledger_path=ledger_path)

    return {
        "timestamp": run_timestamp,
        "scanned": len(snapshots),
        "qualified": len(trade_candidates),
        "selected_trade": selected.to_dict() if selected else None,
        "decision_log": [decision.to_dict() for decision in decisions],
        "trade_record": trade_record,
        "ledger_summary": {
            "cash": round(ledger["cash"], 2),
            "open_positions": len(ledger["open_positions"]),
            "history": len(ledger["history"]),
        },
    }


def record_agent_decision(
    *,
    slug: str,
    model_yes: float,
    paper_size: float = 25.0,
    reason: str = "Agent judged from market snapshot",
    dry_run: bool = False,
    ledger_path: Path | None = None,
) -> dict:
    market = fetch_market_by_slug(slug)
    if not market:
        raise RuntimeError(f"Market not found for slug: {slug}")

    snapshot = market_to_snapshot(market)
    if snapshot is None:
        raise RuntimeError(f"Market is not a supported binary YES/NO market: {slug}")

    ledger = load_ledger(ledger_path=ledger_path)
    decision = decision_from_probability(snapshot, model_yes=model_yes, paper_size=paper_size, reason=reason)

    trade_record = None
    if decision.action != "NO_TRADE" and not dry_run and ledger["cash"] >= decision.paper_size:
        trade_record = _apply_paper_trade(ledger, decision)
        save_ledger(ledger, ledger_path=ledger_path)
    else:
        save_ledger(ledger, ledger_path=ledger_path)

    return {
        "timestamp": _now_iso(),
        "selected_trade": decision.to_dict(),
        "trade_record": trade_record,
        "ledger_summary": {
            "cash": round(ledger["cash"], 2),
            "open_positions": len(ledger["open_positions"]),
            "history": len(ledger["history"]),
        },
    }


def close_position(
    *,
    slug: str,
    outcome: str,
    ledger_path: Path | None = None,
) -> dict:
    """Close an open position by market resolution or manual exit.

    Args:
        slug: Market slug to close.
        outcome: "YES", "NO", or "SELL" (manual exit at current market price).
    """
    outcome = outcome.upper()
    if outcome not in ("YES", "NO", "SELL"):
        raise ValueError(f"outcome must be YES, NO, or SELL, got: {outcome}")

    ledger = load_ledger(ledger_path=ledger_path)
    idx = next(
        (i for i, p in enumerate(ledger["open_positions"]) if p["slug"] == slug),
        None,
    )
    if idx is None:
        raise RuntimeError(f"No open position found for slug: {slug}")

    position = ledger["open_positions"].pop(idx)

    if outcome == "SELL":
        market = fetch_market_by_slug(slug)
        snapshot = market_to_snapshot(market) if market else None
        if snapshot is None:
            raise RuntimeError(f"Cannot fetch current price for slug: {slug}")
        exit_price = snapshot.yes_price if position["side"] == "YES" else snapshot.no_price
    else:
        # Market resolved: winning side pays 1.0, losing side pays 0.0
        won = (position["side"] == outcome)
        exit_price = 1.0 if won else 0.0

    proceeds = round(position["shares"] * exit_price, 2)
    pnl = round(proceeds - position["cost_basis"], 2)
    ledger["cash"] = round(ledger["cash"] + proceeds, 2)

    close_record = {
        "timestamp": _now_iso(),
        "action": "CLOSE",
        "market_id": position["market_id"],
        "slug": position["slug"],
        "question": position.get("question", ""),
        "side": position["side"],
        "outcome": outcome,
        "entry_price": position["entry_price"],
        "exit_price": round(exit_price, 4),
        "shares": position["shares"],
        "cost_basis": position["cost_basis"],
        "proceeds": proceeds,
        "pnl": pnl,
        "opened_at": position.get("opened_at"),
    }
    ledger["history"].append(close_record)
    save_ledger(ledger, ledger_path=ledger_path)
    return close_record


def snapshot_equity(ledger_path: Path | None = None) -> dict:
    """Take an equity curve snapshot and append it to equity_curve.json."""
    status = build_status(ledger_path=ledger_path)
    snapshot = {
        "timestamp": _now_iso(),
        "cash": status["cash"],
        "positions_value": round(status["equity_estimate"] - status["cash"], 2),
        "equity": status["equity_estimate"],
        "open_positions": len(status["open_positions"]),
    }
    curve_path = (ledger_path or DEFAULT_LEDGER_PATH).parent / "equity_curve.json"
    curve: list[dict] = []
    if curve_path.exists():
        curve = json.loads(curve_path.read_text(encoding="utf-8"))
    curve.append(snapshot)
    curve_path.write_text(json.dumps(curve, indent=2), encoding="utf-8")
    return snapshot


def build_status(ledger_path: Path | None = None) -> dict:
    ledger = load_ledger(ledger_path=ledger_path)
    marked_positions = []
    equity_estimate = ledger["cash"]

    for position in ledger["open_positions"]:
        current_value = position["cost_basis"]
        try:
            snapshot = fetch_market_by_slug(position["slug"])
        except Exception:
            snapshot = None
        if snapshot:
            market_snapshot = market_to_snapshot(snapshot)
            if market_snapshot:
                current_price = market_snapshot.yes_price if position["side"] == "YES" else market_snapshot.no_price
                current_value = round(position["shares"] * current_price, 2)
        pnl = round(current_value - position["cost_basis"], 2)
        equity_estimate += current_value
        marked_positions.append({**position, "current_value": current_value, "pnl": pnl})

    return {
        "cash": round(ledger["cash"], 2),
        "starting_cash": round(ledger["starting_cash"], 2),
        "last_run_at": ledger.get("last_run_at"),
        "open_positions": marked_positions,
        "history_count": len(ledger["history"]),
        "equity_estimate": round(equity_estimate, 2),
    }


def _apply_paper_trade(ledger: dict, decision: TradeDecision) -> dict:
    if any(p["slug"] == decision.slug for p in ledger["open_positions"]):
        raise RuntimeError(f"Already have an open position for: {decision.slug}")
    side = "YES" if decision.action == "BUY_YES" else "NO"
    price = decision.market_yes if side == "YES" else (1.0 - decision.market_yes)
    record = {
        "timestamp": _now_iso(),
        "market_id": decision.market_id,
        "slug": decision.slug,
        "question": decision.question,
        "side": side,
        "market_yes": decision.market_yes,
        "model_yes": decision.model_yes,
        "edge": decision.edge,
        "price": round(price, 4),
        "shares": decision.shares,
        "paper_size": round(decision.paper_size, 2),
        "reason": decision.reason,
    }
    ledger["cash"] = round(ledger["cash"] - decision.paper_size, 2)
    ledger["open_positions"].append(
        {
            "market_id": decision.market_id,
            "slug": decision.slug,
            "question": decision.question,
            "side": side,
            "entry_price": round(price, 4),
            "shares": decision.shares,
            "cost_basis": round(decision.paper_size, 2),
            "opened_at": record["timestamp"],
        }
    )
    ledger["history"].append(record)
    ledger["last_run_at"] = record["timestamp"]
    return record


def _no_trade(snapshot: MarketSnapshot, model_yes: float, *, reason: str) -> TradeDecision:
    return TradeDecision(
        action="NO_TRADE",
        market_id=snapshot.market_id,
        slug=snapshot.slug,
        question=snapshot.question,
        market_yes=snapshot.yes_price,
        model_yes=model_yes,
        edge=0.0,
        paper_size=0.0,
        shares=0.0,
        reason=reason,
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
