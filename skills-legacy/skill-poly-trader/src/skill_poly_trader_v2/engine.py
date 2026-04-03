from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .api import derive_terminal_payoffs, fetch_market_detail, fetch_market_by_slug
from .discovery import discover_markets
from .profiles import get_profile_spec

APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER_PATH = APP_ROOT / "data" / "ledger_v2.json"
DEFAULT_EQUITY_CURVE_PATH = APP_ROOT / "data" / "equity_curve_v2.json"
DEFAULT_INITIAL_CASH = 10_000.0


def initialize_ledger(initial_cash: float = DEFAULT_INITIAL_CASH, force: bool = False, ledger_path: Path | None = None) -> str:
    path = ledger_path or DEFAULT_LEDGER_PATH
    if path.exists() and not force:
        return f"Ledger already exists at {path}"
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger = {
        "version": 2,
        "starting_cash": float(initial_cash),
        "cash": float(initial_cash),
        "open_positions": [],
        "history": [],
        "last_run_at": None,
    }
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")
    return f"Initialized v2 ledger at {path} with cash=${initial_cash:.2f}"


def load_ledger(ledger_path: Path | None = None) -> dict[str, Any]:
    path = ledger_path or DEFAULT_LEDGER_PATH
    if not path.exists():
        initialize_ledger(ledger_path=path)
    return json.loads(path.read_text(encoding="utf-8"))


def save_ledger(ledger: dict[str, Any], ledger_path: Path | None = None) -> None:
    path = ledger_path or DEFAULT_LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def build_markets_report(
    *,
    limit: int | None = None,
    profile_name: str | None = None,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    spec = get_profile_spec(profile_name)
    resolved_limit = max(1, int(limit or spec["default_limit"]))
    markets = discover_markets(
        limit=resolved_limit,
        profile_name=spec["name"],
        excluded_slugs=_load_open_position_slugs(ledger_path=ledger_path),
    )
    return {
        "profile": spec["name"],
        "limit": resolved_limit,
        "count": len(markets),
        "markets": markets,
    }


def build_market_report(*, slug: str) -> dict[str, Any]:
    return fetch_market_detail(slug)


def sync_tags(*, tag_index_path: Path | None = None) -> dict[str, Any]:
    from .tags import sync_tag_index

    index = sync_tag_index(tag_index_path=tag_index_path)
    return {
        "tagIndexPath": str(tag_index_path or (APP_ROOT / "data" / "tags.json")),
        "fetchedAt": index.get("fetchedAt"),
        "count": index.get("count", 0),
    }


def buy_position(
    *,
    slug: str,
    outcome_index: int,
    probability: float | None = None,
    size: float = 25.0,
    reason: str = "Agent judged from external research",
    dry_run: bool = False,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    market = fetch_market_detail(slug)
    if market["closed"]:
        raise RuntimeError(f"Market is already closed: {slug}")

    outcomes = market["outcomes"]
    prices = market["outcomePrices"]
    if outcome_index < 0 or outcome_index >= len(outcomes):
        raise RuntimeError(f"outcome_index out of range for: {slug}")

    entry_price = prices[outcome_index]
    if entry_price <= 0:
        raise RuntimeError(f"Cannot open a position at non-positive price for: {slug}")

    ledger = load_ledger(ledger_path=ledger_path)
    if any(position["slug"] == slug for position in ledger["open_positions"]):
        raise RuntimeError(f"Already have an open position for: {slug}")
    if not dry_run and ledger["cash"] < size:
        raise RuntimeError(f"Insufficient cash to open position for: {slug}")

    shares = round(size / entry_price, 4)
    edge = None
    if probability is not None:
        edge = round(probability - entry_price, 4)

    record = {
        "timestamp": _now_iso(),
        "action": "BUY",
        "market_id": market["id"],
        "slug": market["slug"],
        "question": market["question"],
        "outcomes": outcomes,
        "outcome_index": outcome_index,
        "outcome_name": outcomes[outcome_index],
        "market_price": round(entry_price, 4),
        "probability": probability,
        "edge": edge,
        "size": round(size, 2),
        "shares": shares,
        "reason": reason,
    }

    if not dry_run:
        ledger["cash"] = round(ledger["cash"] - size, 2)
        ledger["open_positions"].append(
            {
                "market_id": market["id"],
                "slug": market["slug"],
                "question": market["question"],
                "outcomes": outcomes,
                "outcome_index": outcome_index,
                "outcome_name": outcomes[outcome_index],
                "entry_price": round(entry_price, 4),
                "shares": shares,
                "cost_basis": round(size, 2),
                "opened_at": record["timestamp"],
                "reason": reason,
            }
        )
        ledger["history"].append(record)
        ledger["last_run_at"] = record["timestamp"]
        save_ledger(ledger, ledger_path=ledger_path)

    return {
        "selected_trade": record,
        "trade_record": None if dry_run else record,
        "ledger_summary": {
            "cash": round(ledger["cash"], 2) if not dry_run else round(ledger["cash"], 2),
            "open_positions": len(ledger["open_positions"]) if not dry_run else len(ledger["open_positions"]),
            "history": len(ledger["history"]) if not dry_run else len(ledger["history"]),
        },
    }


record_trade = buy_position


def sell_position(*, slug: str, reason: str = "Thesis changed", ledger_path: Path | None = None) -> dict[str, Any]:
    ledger = load_ledger(ledger_path=ledger_path)
    index = next((i for i, position in enumerate(ledger["open_positions"]) if position["slug"] == slug), None)
    if index is None:
        raise RuntimeError(f"No open position found for slug: {slug}")

    position = ledger["open_positions"].pop(index)
    market = fetch_market_detail(slug)
    current_price = market["outcomePrices"][position["outcome_index"]]
    proceeds = round(position["shares"] * current_price, 2)
    pnl = round(proceeds - position["cost_basis"], 2)
    ledger["cash"] = round(ledger["cash"] + proceeds, 2)

    record = {
        "timestamp": _now_iso(),
        "action": "SELL",
        "market_id": position["market_id"],
        "slug": position["slug"],
        "question": position["question"],
        "outcome_index": position["outcome_index"],
        "outcome_name": position["outcome_name"],
        "entry_price": position["entry_price"],
        "exit_price": round(current_price, 4),
        "shares": position["shares"],
        "cost_basis": position["cost_basis"],
        "proceeds": proceeds,
        "pnl": pnl,
        "opened_at": position["opened_at"],
        "reason": reason,
        "exit_type": "MANUAL_SELL",
    }
    ledger["history"].append(record)
    ledger["last_run_at"] = record["timestamp"]
    save_ledger(ledger, ledger_path=ledger_path)
    return record


def build_status(*, ledger_path: Path | None = None) -> dict[str, Any]:
    ledger = load_ledger(ledger_path=ledger_path)
    auto_settled, closed_pending = reconcile_settlements(ledger, ledger_path=ledger_path)

    marked_positions = []
    equity_estimate = ledger["cash"]
    for position in ledger["open_positions"]:
        current_value = position["cost_basis"]
        current_price = position["entry_price"]
        market_state = "OPEN"
        try:
            market = fetch_market_detail(position["slug"])
        except Exception:
            market = None

        if market:
            current_price = market["outcomePrices"][position["outcome_index"]]
            current_value = round(position["shares"] * current_price, 2)
            if market["closed"]:
                market_state = "CLOSED_PENDING"
        pnl = round(current_value - position["cost_basis"], 2)
        equity_estimate += current_value
        marked_positions.append(
            {
                **position,
                "current_price": round(current_price, 4),
                "current_value": current_value,
                "pnl": pnl,
                "market_state": market_state,
            }
        )

    return {
        "cash": round(ledger["cash"], 2),
        "starting_cash": round(ledger["starting_cash"], 2),
        "last_run_at": ledger.get("last_run_at"),
        "open_positions": marked_positions,
        "closed_pending": closed_pending,
        "auto_settled": auto_settled,
        "history_count": len(ledger["history"]),
        "equity_estimate": round(equity_estimate, 2),
    }


def snapshot_equity(*, ledger_path: Path | None = None) -> dict[str, Any]:
    status = build_status(ledger_path=ledger_path)
    snapshot = {
        "timestamp": _now_iso(),
        "cash": status["cash"],
        "positions_value": round(status["equity_estimate"] - status["cash"], 2),
        "equity": status["equity_estimate"],
        "open_positions": len(status["open_positions"]),
    }
    curve_path = DEFAULT_EQUITY_CURVE_PATH if ledger_path is None else ledger_path.parent / "equity_curve_v2.json"
    curve: list[dict[str, Any]] = []
    if curve_path.exists():
        curve = json.loads(curve_path.read_text(encoding="utf-8"))
    curve.append(snapshot)
    curve_path.write_text(json.dumps(curve, indent=2), encoding="utf-8")
    return snapshot


def reconcile_settlements(ledger: dict[str, Any], *, ledger_path: Path | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    auto_settled: list[dict[str, Any]] = []
    closed_pending: list[dict[str, Any]] = []
    remaining_positions: list[dict[str, Any]] = []

    for position in ledger["open_positions"]:
        raw_market = fetch_market_by_slug(position["slug"])
        if not raw_market:
            remaining_positions.append(position)
            continue

        terminal_payoffs = derive_terminal_payoffs(raw_market)
        if terminal_payoffs is None:
            if bool(raw_market.get("closed", False)):
                closed_pending.append(
                    {
                        "slug": position["slug"],
                        "question": position["question"],
                        "reason": "market closed but terminal payoff is unavailable from API response",
                    }
                )
            remaining_positions.append(position)
            continue

        exit_price = terminal_payoffs[position["outcome_index"]]
        proceeds = round(position["shares"] * exit_price, 2)
        pnl = round(proceeds - position["cost_basis"], 2)
        ledger["cash"] = round(ledger["cash"] + proceeds, 2)
        record = {
            "timestamp": _now_iso(),
            "action": "SETTLE",
            "market_id": position["market_id"],
            "slug": position["slug"],
            "question": position["question"],
            "outcome_index": position["outcome_index"],
            "outcome_name": position["outcome_name"],
            "entry_price": position["entry_price"],
            "exit_price": round(exit_price, 4),
            "shares": position["shares"],
            "cost_basis": position["cost_basis"],
            "proceeds": proceeds,
            "pnl": pnl,
            "opened_at": position["opened_at"],
            "exit_type": "AUTO_SETTLE",
        }
        ledger["history"].append(record)
        auto_settled.append(record)

    if auto_settled:
        ledger["open_positions"] = remaining_positions
        ledger["last_run_at"] = auto_settled[-1]["timestamp"]
        save_ledger(ledger, ledger_path=ledger_path)
    else:
        ledger["open_positions"] = remaining_positions

    return auto_settled, closed_pending


def _load_open_position_slugs(*, ledger_path: Path | None = None) -> set[str]:
    path = ledger_path or DEFAULT_LEDGER_PATH
    if not path.exists():
        return set()
    ledger = json.loads(path.read_text(encoding="utf-8"))
    slugs: set[str] = set()
    for position in ledger.get("open_positions", []):
        if not isinstance(position, dict):
            continue
        slug = str(position.get("slug", "") or "").strip()
        if slug:
            slugs.add(slug)
    return slugs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
